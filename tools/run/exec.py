import ast
import os
import shutil
import subprocess
import sys
import tempfile

BLOCKED_BUILTINS = {
    "__import__",
    "open",
    "eval",
    "exec",
    "compile",
    "globals",
    "locals",
    "getattr",
    "setattr",
    "delattr",
}
ALLOWED_BUILTINS = {
    "print",
    "len",
    "range",
    "int",
    "str",
    "float",
    "list",
    "dict",
    "set",
    "tuple",
    "bool",
    "enumerate",
    "zip",
    "map",
    "filter",
    "sorted",
    "min",
    "max",
    "sum",
    "abs",
    "round",
    "type",
    "isinstance",
    "hasattr",
}
BLOCKED_DUNDER_ATTRS = {
    "__class__",
    "__bases__",
    "__subclasses__",
    "__globals__",
    "__builtins__",
}
RESTRICTED_IMPORTS = ("socket", "requests", "urllib", "http", "ftplib")


def _reject(message: str) -> None:
    print(f"[SANDBOX BLOCKED] {message}")


def _validate_ast(tree: ast.AST) -> None:
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            module_names = []
            if isinstance(node, ast.Import):
                module_names = [alias.name for alias in node.names]
            else:
                if node.module:
                    module_names = [node.module]
            for module_name in module_names:
                for restricted in RESTRICTED_IMPORTS:
                    if module_name == restricted or module_name.startswith(f"{restricted}."):
                        raise ValueError(f"Import of restricted module '{module_name}' is not allowed")
            raise ValueError("Import statements are not allowed")

        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in BLOCKED_BUILTINS:
                raise ValueError(f"Use of builtin '{node.func.id}' is not allowed")

        if isinstance(node, ast.Attribute):
            if node.attr in BLOCKED_DUNDER_ATTRS:
                raise ValueError(f"Access to dunder attribute '{node.attr}' is not allowed")


def _build_sandbox_code() -> str:
    allowed_defs = []
    for name in sorted(ALLOWED_BUILTINS):
        allowed_defs.append(f'"{name}": getattr(builtins, "{name}")')
    allowed = ", ".join(allowed_defs)
    return (
        "import builtins, sys\n"
        f"safe = {{{allowed}}}\n"
        "globals_dict = {'__builtins__': safe}\n"
        "code = sys.stdin.read()\n"
        "exec(compile(code, '<exec>', 'exec'), globals_dict)\n"
    )


code = sys.stdin.read()
try:
    tree = ast.parse(code, filename="<exec>")
    _validate_ast(tree)
except SyntaxError as error:
    print(f"[EXEC ERROR] {error}")
    sys.exit(0)
except ValueError as error:
    _reject(error)
    sys.exit(0)

sandbox_dir = tempfile.mkdtemp()
try:
    timeout = int(os.getenv("J_EXEC_TIMEOUT", "10"))
    result = subprocess.run(
        [sys.executable, "-c", _build_sandbox_code()],
        input=code,
        capture_output=True,
        text=True,
        cwd=sandbox_dir,
        env=os.environ.copy(),
        timeout=timeout,
        check=False,
    )
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="")
except subprocess.TimeoutExpired:
    _reject(f"Execution timed out after {timeout} seconds")
except Exception as error:
    print(f"[EXEC ERROR] {error}")
finally:
    shutil.rmtree(sandbox_dir, ignore_errors=True)
    # Future: impose Linux memory limits with resource.setrlimit().
