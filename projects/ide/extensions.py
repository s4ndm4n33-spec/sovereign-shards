# Copyright (c) 2026 Mike McCollum
#
# Licensed under the Sovereign Shards License.
# See LICENSE.md for details.

import json
import os
import sys
import time
import urllib.request
import urllib.parse
import urllib.error
import subprocess
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent
EXT_DIR = ROOT / 'extensions'
PY_EXT_DIR = EXT_DIR / 'python'
JS_EXT_DIR = EXT_DIR / 'js'
OLLAMA_BASE_URL = os.environ.get('OLLAMA_URL', 'http://127.0.0.1:11434')


class ExtensionAPI:
    def __init__(self, workspace_root: Path):
        self.workspace_root = workspace_root

    def _resolve(self, relative_path: str) -> Path:
        candidate = (self.workspace_root / relative_path).resolve()
        if not str(candidate).startswith(str(self.workspace_root)):
            raise ValueError('Path escapes workspace root')
        return candidate

    def read_file(self, path: str) -> str:
        target = self._resolve(path)
        if not target.exists() or not target.is_file():
            raise FileNotFoundError(path)
        return target.read_text(encoding='utf-8')

    def write_file(self, path: str, content: str) -> None:
        target = self._resolve(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding='utf-8')

    def list_dir(self, path: str = '') -> list[dict]:
        target = self._resolve(path)
        if not target.exists() or not target.is_dir():
            raise FileNotFoundError(path)
        result = []
        for item in sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
            result.append({
                'name': item.name,
                'path': str(item.relative_to(self.workspace_root)).replace('\\', '/'),
                'directory': item.is_dir(),
            })
        return result

    def run_shell(self, command: str, cwd: str | None = None, timeout: int = 60) -> dict:
        working_dir = self._resolve(cwd) if cwd else self.workspace_root
        result = subprocess.run(command, shell=True, cwd=str(working_dir), capture_output=True, text=True, timeout=timeout)
        return {
            'ok': True,
            'returncode': result.returncode,
            'stdout': result.stdout.strip(),
            'stderr': result.stderr.strip(),
        }

    def pull_model(self, model_name: str) -> dict:
        payload = {'image': model_name}
        return self._ollama_request('/api/pull', payload)

    def _ollama_request(self, path: str, payload: dict | None = None) -> dict:
        url = OLLAMA_BASE_URL.rstrip('/') + path
        data = None
        headers = {'Content-Type': 'application/json'}
        if payload is not None:
            data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(url, data=data, headers=headers, method='POST' if data else 'GET')
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode('utf-8', errors='replace')
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                return {'ok': False, 'error': raw}


class ExtensionHost:
    def __init__(self, api: ExtensionAPI):
        self.api = api
        self.registry: dict[str, dict] = {}
        self.load_builtin_extensions()
        self.load_python_extensions()

    def load_python_extensions(self) -> None:
        if not PY_EXT_DIR.exists():
            PY_EXT_DIR.mkdir(parents=True, exist_ok=True)
            return
        for path in sorted(PY_EXT_DIR.glob('*.py')):
            name = path.stem
            try:
                spec = importlib.util.spec_from_file_location(f'extensions.{name}', path)
                if not spec or not spec.loader:
                    continue
                module = importlib.util.module_from_spec(spec)
                sys.modules[spec.name] = module
                spec.loader.exec_module(module)
                if hasattr(module, 'register'):
                    module.register(self.api)
                self.registry[name] = {'type': 'python', 'path': str(path), 'loaded': True}
            except Exception as exc:
                self.registry[name] = {'type': 'python', 'path': str(path), 'loaded': False, 'error': str(exc)}

    def load_js_extensions(self) -> list[dict]:
        if not JS_EXT_DIR.exists():
            JS_EXT_DIR.mkdir(parents=True, exist_ok=True)
            return []
        extensions = []
        for path in sorted(JS_EXT_DIR.glob('*.js')):
            extensions.append({'name': path.stem, 'path': str(path.relative_to(ROOT)).replace('\\', '/'), 'type': 'js'})
        return extensions

    def register(self, name: str, metadata: dict) -> None:
        self.registry[name] = metadata

    def execute(self, name: str, command: str, args: dict | None = None) -> dict:
        if name not in self.registry:
            return {'ok': False, 'error': 'Extension not registered'}
        ext = self.registry[name]
        if ext.get('type') == 'python' and 'execute' in ext:
            try:
                return ext['execute'](command, args or {})
            except Exception as exc:
                return {'ok': False, 'error': str(exc)}
        return {'ok': False, 'error': 'Extension does not support execution'}

    def load_builtin_extensions(self) -> None:
        self.register('git', {
            'type': 'python',
            'description': 'Basic git workflow commands using local git subprocesses.',
            'execute': self.git_command,
        })
        self.register('ollama_downloader', {
            'type': 'python',
            'description': 'Pull local Ollama model weights through the local Ollama API.',
            'execute': self.pull_model_command,
        })
        self.register('slack_webhook', {
            'type': 'python',
            'description': 'Send webhook notifications to Slack-compatible endpoints.',
            'execute': self.slack_notify,
        })

    def git_command(self, command: str, args: dict) -> dict:
        repo_path = args.get('repo_path', '.')
        if command == 'status':
            return self.api.run_shell('git status --short', cwd=repo_path)
        if command == 'diff':
            return self.api.run_shell('git diff --stat', cwd=repo_path)
        if command == 'add':
            target = args.get('target', '.')
            return self.api.run_shell(f'git add {target}', cwd=repo_path)
        if command == 'commit':
            message = args.get('message', 'Update via Sovereign IDE')
            return self.api.run_shell(f'git commit -m "{message}"', cwd=repo_path)
        return {'ok': False, 'error': f'Unsupported git command {command}'}

    def pull_model_command(self, command: str, args: dict) -> dict:
        if command != 'pull':
            return {'ok': False, 'error': 'Only pull is supported for Ollama downloader'}
        model_name = args.get('model_name', '')
        if not model_name:
            return {'ok': False, 'error': 'model_name is required'}
        return self.api.pull_model(model_name)

    def slack_notify(self, command: str, args: dict) -> dict:
        if command != 'notify':
            return {'ok': False, 'error': 'Only notify is supported for Slack extension'}
        webhook_url = args.get('webhook_url')
        message = args.get('message', '')
        if not webhook_url:
            return {'ok': False, 'error': 'webhook_url is required'}
        payload = json.dumps({'text': message}).encode('utf-8')
        request = urllib.request.Request(webhook_url, data=payload, headers={'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                return {'ok': True, 'status': response.status}
        except Exception as exc:
            return {'ok': False, 'error': str(exc)}


if __name__ == '__main__':
    api = ExtensionAPI(ROOT)
    host = ExtensionHost(api)
    print('Loaded extensions:')
    for key, value in host.registry.items():
        print(f'- {key}: {value.get("description", "builtin")}')
