import json
import os
import sys
import time
import threading
import urllib.request
import urllib.parse
import urllib.error
import http.server
import socketserver
import subprocess
import mimetypes
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent))

from app.client import create_client
from app.llm_client import LLMClient

STATIC_DIR = ROOT / "static"
EXTENSIONS_DIR = ROOT / "extensions"
STATE_FILE = ROOT / "workspace_state.json"
OLLAMA_BASE_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
OLLAMA_MODEL_DEFAULT = os.environ.get("OLLAMA_MODEL", "qwen2.5-coder:14b")
LISTEN_HOST = os.environ.get("IDE_HOST", "127.0.0.1")
LISTEN_PORT = int(os.environ.get("IDE_PORT", "8001"))

WORKSPACE_STATE = {
    "openEditors": [],
    "activeEditor": None,
    "editorGroups": [],
    "sidebarVisible": True,
    "sidebarActiveView": "explorer",
    "sidebarWidth": 300,
    "bottomPanelHeight": 200,
    "bottomPanelVisible": False,
    "selectedFile": None,
    "theme": "dark",
    "chatHistory": [],
    "updated": time.time(),
}
FILE_WATCHERS = {}
EVENT_LOG = []
COMMAND_LOCK = threading.Lock()
COMMAND_TASKS = []
COMMAND_COUNTER = {'next': 1}

mimetypes.init()


def log_event(message: str) -> None:
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {message}"
    EVENT_LOG.append(line)
    if len(EVENT_LOG) > 200:
        del EVENT_LOG[:-200]


def load_state() -> None:
    global WORKSPACE_STATE
    if STATE_FILE.exists():
        try:
            content = STATE_FILE.read_text(encoding='utf-8')
            data = json.loads(content)
            if isinstance(data, dict):
                WORKSPACE_STATE.update(data)
        except Exception as exc:
            log_event(f"Failed to load state: {exc}")


def save_state() -> None:
    try:
        STATE_FILE.write_text(json.dumps(WORKSPACE_STATE, indent=2), encoding='utf-8')
    except Exception as exc:
        log_event(f"Failed to persist state: {exc}")


def safe_path(path: str) -> Path:
    if not path:
        return ROOT
    normalized = path.replace('\\', '/').lstrip('/')
    resolved = (ROOT / normalized).resolve()
    if not str(resolved).startswith(str(ROOT)):
        raise ValueError('Path escapes workspace root')
    return resolved


def read_json_body(request_handler):
    length = int(request_handler.headers.get('Content-Length', '0'))
    body = request_handler.rfile.read(length).decode('utf-8') if length else ''
    if not body:
        return {}
    return json.loads(body)


def request_json(url: str, method: str = 'GET', payload: dict | None = None, timeout: int = 30) -> dict:
    data = None
    headers = {'Content-Type': 'application/json'}
    if payload is not None:
        data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            raw = response.read().decode('utf-8', errors='replace')
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                return {'ok': False, 'error': 'Invalid JSON', 'payload': raw}
    except Exception as exc:
        return {'ok': False, 'error': str(exc)}


def create_llm_client() -> LLMClient:
    config = create_client()
    return LLMClient(config)


def generate_chat_response(message: str) -> dict:
    try:
        client = create_llm_client()
        # Simple assistant prompt for IDE chat
        system_prompt = (
            'You are the Sovereign IDE assistant. Answer developer questions about the workspace, code, and local environment. '
            'Keep responses concise and helpful.'
        )
        response_text = client.generate_text(message, system=system_prompt)
        return {'ok': True, 'response': response_text}
    except Exception as exc:
        return {'ok': False, 'error': str(exc)}


def get_market_models() -> dict:
    models = []
    if OLLAMA_BASE_URL:
        result = request_json(f'{OLLAMA_BASE_URL.rstrip("/")}/api/models', 'GET')
        if result.get('ok') and isinstance(result.get('models'), list):
            for model in result['models']:
                models.append({
                    'name': model.get('name', str(model)),
                    'description': model.get('description', 'Ollama model'),
                })
    if not models:
        models = [
            {'name': OLLAMA_MODEL_DEFAULT, 'description': 'Default local Ollama-compatible model'},
        ]
    return {'ok': True, 'models': models}


def install_market_model(model_name: str) -> dict:
    if not model_name:
        return {'ok': False, 'error': 'Missing model name'}
    if not OLLAMA_BASE_URL:
        return {'ok': False, 'error': 'Ollama URL is not configured'}
    return request_json(f'{OLLAMA_BASE_URL.rstrip("/")}/api/pull', 'POST', {'image': model_name}, timeout=120)


def list_files(path: str = '', include_hidden: bool = False) -> dict:
    try:
        target = safe_path(path)
        if not target.is_dir():
            return {'ok': False, 'error': 'Not a directory'}
        entries = []
        for item in sorted(target.iterdir()):
            if item.name.startswith('.') and not include_hidden:
                continue
            entry = {
                'name': item.name,
                'path': str(item.relative_to(ROOT)).replace('\\', '/'),
                'isDirectory': item.is_dir(),
                'isFile': item.is_file(),
                'size': item.stat().st_size if item.is_file() else 0,
                'modified': int(item.stat().st_mtime),
            }
            entries.append(entry)
        return {'ok': True, 'entries': entries}
    except Exception as exc:
        return {'ok': False, 'error': str(exc)}


def read_file(path: str) -> dict:
    try:
        target = safe_path(path)
        if not target.is_file():
            return {'ok': False, 'error': 'Not a file'}
        content = target.read_text(encoding='utf-8', errors='replace')
        return {'ok': True, 'content': content, 'language': infer_language(target.suffix)}
    except Exception as exc:
        return {'ok': False, 'error': str(exc)}


def write_file(path: str, content: str) -> dict:
    try:
        target = safe_path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding='utf-8')
        return {'ok': True, 'path': str(target.relative_to(ROOT)).replace('\\', '/')}
    except Exception as exc:
        return {'ok': False, 'error': str(exc)}


def infer_language(suffix: str) -> str:
    languages = {
        '.py': 'python', '.js': 'javascript', '.ts': 'typescript', '.tsx': 'typescript',
        '.jsx': 'javascript', '.json': 'json', '.md': 'markdown', '.html': 'html',
        '.css': 'css', '.sh': 'bash', '.bat': '.bat', '.yaml': 'yaml', '.yml': 'yaml',
        '.xml': 'xml', '.sql': 'sql', '.rb': 'ruby', '.go': 'go', '.java': 'java',
        '.c': 'c', '.cpp': 'cpp', '.rs': 'rust', '.toml': 'toml',
    }
    return languages.get(suffix.lower(), 'plaintext')


def search_files(query: str, path: str = '') -> dict:
    try:
        target = safe_path(path)
        results = []
        for item in target.rglob('*'):
            if item.is_file() and not item.name.startswith('.'):
                try:
                    content = item.read_text(encoding='utf-8', errors='replace')
                    if query.lower() in content.lower():
                        matches = []
                        for idx, line in enumerate(content.split('\n'), 1):
                            if query.lower() in line.lower():
                                matches.append({'line': idx, 'text': line.strip()})
                        if matches:
                            results.append({
                                'path': str(item.relative_to(ROOT)).replace('\\', '/'),
                                'matches': matches[:5],
                            })
                except Exception:
                    pass
        return {'ok': True, 'results': results[:50]}
    except Exception as exc:
        return {'ok': False, 'error': str(exc)}


def find_files(query: str, path: str = '') -> dict:
    try:
        target = safe_path(path)
        if not target.is_dir():
            return {'ok': False, 'error': 'Not a directory'}
        query_lower = query.lower().strip()
        if not query_lower:
            return {'ok': True, 'results': []}
        matches = []
        for item in target.rglob('*'):
            if item.is_file() and query_lower in item.name.lower():
                matches.append({
                    'name': item.name,
                    'path': str(item.relative_to(ROOT)).replace('\\', '/'),
                })
                if len(matches) >= 100:
                    break
        return {'ok': True, 'results': matches}
    except Exception as exc:
        return {'ok': False, 'error': str(exc)}


def run_shell_command(command: str) -> dict:
    with COMMAND_LOCK:
        task_id = COMMAND_COUNTER['next']
        COMMAND_COUNTER['next'] += 1
    task = {
        'id': task_id,
        'command': command,
        'status': 'running',
        'output': '',
        'started': int(time.time() * 1000),
        'finished': None,
    }
    COMMAND_TASKS.append(task)

    def worker():
        try:
            result = subprocess.run(command, shell=True, cwd=str(ROOT), capture_output=True, text=True, timeout=30)
            task['output'] = result.stdout + result.stderr
            task['status'] = 'completed' if result.returncode == 0 else 'failed'
        except Exception as exc:
            task['output'] = str(exc)
            task['status'] = 'failed'
        finally:
            task['finished'] = int(time.time() * 1000)
    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    return {'ok': True, 'task': task}


def get_git_status() -> dict:
    try:
        result = subprocess.run('git status --porcelain', shell=True, cwd=str(ROOT), capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            changes = []
            for line in result.stdout.strip().split('\n'):
                if line:
                    status = line[:2]
                    filepath = line[3:]
                    changes.append({'status': status, 'path': filepath})
            return {'ok': True, 'changes': changes}
        return {'ok': False, 'error': 'Not a git repo'}
    except Exception as exc:
        return {'ok': False, 'error': str(exc)}


class IDERequestHandler(http.server.BaseHTTPRequestHandler):
    server_version = 'SovereignIDE/2.0'

    def send_json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload, indent=2).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)

    def send_text(self, content: str, status: int = 200, content_type: str = 'text/plain; charset=utf-8') -> None:
        body = content.encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path.startswith('/api/'):
            self.handle_api_get(parsed)
            return
        if parsed.path == '/' or parsed.path == '/index.html':
            self.serve_file('index.html', 'text/html; charset=utf-8')
            return
        if parsed.path.startswith('/static/'):
            self.serve_file(parsed.path[len('/static/'):])
            return
        if parsed.path.startswith('/extensions/'):
            file_path = parsed.path[len('/extensions/'):]
            self.serve_extension_file(file_path)
            return
        self.send_error(404)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path.startswith('/api/'):
            self.handle_api_post(parsed)
            return
        self.send_error(404)

    def serve_file(self, relative_path: str, content_type: str | None = None) -> None:
        try:
            file_path = (STATIC_DIR / relative_path).resolve()
            if not str(file_path).startswith(str(STATIC_DIR)) or not file_path.exists():
                self.send_error(404)
                return
            if content_type is None:
                content_type, _ = mimetypes.guess_type(str(file_path))
            self.send_text(file_path.read_text(encoding='utf-8'), content_type=content_type or 'application/octet-stream')
        except Exception:
            self.send_error(404)

    def serve_extension_file(self, relative_path: str) -> None:
        try:
            file_path = (EXTENSIONS_DIR / relative_path).resolve()
            if not str(file_path).startswith(str(EXTENSIONS_DIR)) or not file_path.exists():
                self.send_error(404)
                return
            content_type, _ = mimetypes.guess_type(str(file_path))
            self.send_text(file_path.read_text(encoding='utf-8'), content_type=content_type or 'application/javascript')
        except Exception:
            self.send_error(404)

    def handle_api_get(self, parsed):
        query = urllib.parse.parse_qs(parsed.query)
        path = parsed.path
        if path == '/api/fs/list':
            self.send_json(list_files(query.get('path', [''])[0]))
        elif path == '/api/fs/read':
            self.send_json(read_file(query.get('path', [''])[0]))
        elif path == '/api/workspace/state':
            self.send_json({'ok': True, 'state': WORKSPACE_STATE, 'events': EVENT_LOG[-100:], 'commands': COMMAND_TASKS[-20:]})
        elif path == '/api/scm/status':
            self.send_json(get_git_status())
        elif path == '/api/search':
            self.send_json(search_files(query.get('q', [''])[0], query.get('path', [''])[0]))
        elif path == '/api/fs/find':
            self.send_json(find_files(query.get('q', [''])[0], query.get('path', [''])[0]))
        elif path == '/api/extensions/list':
            try:
                extensions = []
                for ext in sorted((EXTENSIONS_DIR / 'js').glob('*.js')):
                    extensions.append({'name': ext.stem, 'path': str(ext.relative_to(ROOT)).replace('\\', '/')})
                self.send_json({'ok': True, 'extensions': extensions})
            except Exception as exc:
                self.send_json({'ok': False, 'error': str(exc)}, status=500)
        elif path == '/api/market/models':
            self.send_json(get_market_models())
        elif path == '/api/chat/history':
            self.send_json({'ok': True, 'messages': WORKSPACE_STATE.get('chatHistory', [])})
        elif path == '/api/command':
            self.send_json({'ok': True, 'commands': COMMAND_TASKS[-20:]})
        else:
            self.send_error(404)

    def handle_api_post(self, parsed):
        path = parsed.path
        try:
            payload = read_json_body(self)
        except Exception as exc:
            self.send_json({'ok': False, 'error': str(exc)}, status=400)
            return
        if path == '/api/fs/read':
            self.send_json(read_file(payload.get('path', '')))
        elif path == '/api/fs/write':
            self.send_json(write_file(payload.get('path', ''), payload.get('content', '')))
        elif path == '/api/editor/open':
            path_to_open = payload.get('path')
            if not path_to_open:
                self.send_json({'ok': False, 'error': 'Missing path'}, status=400)
                return
            existing = next((e for e in WORKSPACE_STATE['openEditors'] if e['id'] == path_to_open), None)
            if existing:
                WORKSPACE_STATE['activeEditor'] = path_to_open
                save_state()
                self.send_json({'ok': True, 'editor': existing})
                return
            editor = {
                'id': path_to_open,
                'path': path_to_open,
                'language': payload.get('language', 'plaintext'),
                'dirty': False,
                'modified': int(time.time() * 1000),
            }
            WORKSPACE_STATE['openEditors'].append(editor)
            WORKSPACE_STATE['activeEditor'] = editor['id']
            save_state()
            self.send_json({'ok': True, 'editor': editor})
        elif path == '/api/editor/close':
            path_to_close = payload.get('path')
            WORKSPACE_STATE['openEditors'] = [e for e in WORKSPACE_STATE['openEditors'] if e['id'] != path_to_close]
            if WORKSPACE_STATE['activeEditor'] == path_to_close:
                WORKSPACE_STATE['activeEditor'] = WORKSPACE_STATE['openEditors'][0]['id'] if WORKSPACE_STATE['openEditors'] else None
            save_state()
            self.send_json({'ok': True})
        elif path == '/api/editor/setActive':
            WORKSPACE_STATE['activeEditor'] = payload.get('path')
            save_state()
            self.send_json({'ok': True})
        elif path == '/api/editor/markDirty':
            for editor in WORKSPACE_STATE['openEditors']:
                if editor['id'] == payload.get('path'):
                    editor['dirty'] = payload.get('dirty', True)
            save_state()
            self.send_json({'ok': True})
        elif path == '/api/workspace/setSidebar':
            WORKSPACE_STATE['sidebarVisible'] = payload.get('visible', True)
            WORKSPACE_STATE['sidebarActiveView'] = payload.get('activeView', 'explorer')
            WORKSPACE_STATE['sidebarWidth'] = payload.get('width', 300)
            save_state()
            self.send_json({'ok': True})
        elif path == '/api/workspace/setPanel':
            WORKSPACE_STATE['bottomPanelVisible'] = payload.get('visible', False)
            WORKSPACE_STATE['bottomPanelHeight'] = payload.get('height', 200)
            save_state()
            self.send_json({'ok': True})
        elif path == '/api/chat/send':
            message = payload.get('message', '').strip()
            if not message:
                self.send_json({'ok': False, 'error': 'Missing message'}, status=400)
                return
            chat_history = WORKSPACE_STATE.setdefault('chatHistory', [])
            chat_history.append({'role': 'user', 'text': message, 'timestamp': int(time.time() * 1000)})
            result = generate_chat_response(message)
            if result.get('ok'):
                assistant_text = result.get('response', '')
                chat_history.append({'role': 'assistant', 'text': assistant_text, 'timestamp': int(time.time() * 1000)})
                save_state()
            self.send_json(result)
        elif path == '/api/market/install':
            model_name = payload.get('model', '')
            self.send_json(install_market_model(model_name))
        elif path == '/api/command':
            action = payload.get('action')
            if action == 'run_shell':
                command = payload.get('command', '')
                if not command:
                    self.send_json({'ok': False, 'error': 'Missing command'}, status=400)
                    return
                self.send_json(run_shell_command(command))
            else:
                self.send_json({'ok': False, 'error': 'Unknown command action'}, status=400)
        else:
            self.send_error(404)

    def log_message(self, format: str, *args) -> None:
        pass


def bootstrap() -> None:
    STATIC_DIR.mkdir(exist_ok=True)
    (EXTENSIONS_DIR / 'js').mkdir(parents=True, exist_ok=True)


def main() -> None:
    load_state()
    bootstrap()
    log_event('Sovereign IDE v2 starting.')
    socketserver.ThreadingTCPServer.allow_reuse_address = True
    with socketserver.ThreadingTCPServer((LISTEN_HOST, LISTEN_PORT), IDERequestHandler) as httpd:
        httpd.daemon_threads = True
        print(f'Sovereign IDE running on http://{LISTEN_HOST}:{LISTEN_PORT}')
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print('Shutdown.')


if __name__ == '__main__':
    main()
