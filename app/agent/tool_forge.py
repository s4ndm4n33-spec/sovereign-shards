# Copyright (c) 2024-2026 Reed Richards (s4ndm4n33). Licensed under BSL 1.1.
"""Tool forge: generate, validate, and register new tools at runtime.

Takes a ToolSpec from the researcher, asks the model to fill in the
implementation, validates it through the sandbox, and hot-registers
it into the ToolRegistry — all in one turn.

Zero external deps.  FAT32-safe writes.  Atomic file placement.
"""

from __future__ import annotations

import json
import os
import py_compile
import re
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from app.agent.tool_researcher import ToolSpec

if TYPE_CHECKING:
    from app.agent.tool_registry import ToolRegistry


# ── Constants ────────────────────────────────────────────

MAX_RETRIES = 3               # circuit-breaker: max fix attempts
TOOL_DIR = "tools/run"        # active tools — human-reviewed only
QUARANTINE_DIR = "tools/quarantine"  # generated tools await human approval here
LOG_FILE = "logs/tool_forge.jsonl"


# ── Result types ─────────────────────────────────────────

@dataclass
class ForgeResult:
    """Outcome of one forge attempt."""
    tool_name: str
    success: bool
    file_path: str = ""
    code: str = ""
    error: str = ""
    attempts: int = 0
    elapsed_s: float = 0.0


# ── Code generation template ─────────────────────────────

TOOL_TEMPLATE = '''\
"""Auto-generated tool: {purpose}

Built by J's tool forge.  Follows the standard tool contract:
TOOL_NAME, TOOL_DESC, and a run() function that returns a string.
"""

import os
import sys

TOOL_NAME = "run_{tool_name}"
TOOL_DESC = """{purpose}"""

{implementation}


# ── CLI entry point (tools/run convention) ───────────────
if __name__ == "__main__":
    args = sys.argv[1:]
    try:
        print(run(*args))
    except Exception as exc:
        print(f"[TOOL ERROR] {{exc}}")
        sys.exit(1)
'''

FORGE_PROMPT = """\
Write the Python implementation for this tool.  Follow these rules EXACTLY:

1. Define a function: def run({args_sig}) -> str:
2. The function MUST return a string (the tool output).
3. Use ONLY Python stdlib.  {dep_note}
4. Handle errors gracefully — return "[TOOL ERROR] ..." on failure.
5. Do NOT import anything outside stdlib unless listed in dependencies.
6. Do NOT print anything inside run() — return the result string.
7. Keep it under 80 lines.  Lean and correct.

Tool spec:
  Name: {tool_name}
  Purpose: {purpose}
  Inputs: {inputs}
  Outputs: {outputs}
  Example: {example_call}

Respond with ONLY the Python code for the run() function and any helper
functions it needs.  No imports of os/sys (already at top).  No class
definitions.  No markdown fences.  Just the raw Python.
"""


# ── Code generation ──────────────────────────────────────

def build_forge_prompt(spec: ToolSpec) -> str:
    """Build the prompt sent to the model for implementation."""
    args_sig = ", ".join(
        a.split(":")[0].strip() for a in spec.inputs
    ) if spec.inputs else ""

    dep_note = ""
    if spec.dependencies:
        dep_note = (
            f"These non-stdlib packages are allowed: {', '.join(spec.dependencies)}. "
            "If any are unavailable, degrade gracefully."
        )
    else:
        dep_note = "No non-stdlib packages allowed."

    return FORGE_PROMPT.format(
        args_sig=args_sig,
        tool_name=spec.tool_name,
        purpose=spec.purpose,
        inputs=", ".join(spec.inputs) or "none",
        outputs=", ".join(spec.outputs) or "result string",
        example_call=spec.example_call or f"run_{spec.tool_name}(...)",
        dep_note=dep_note,
    )


def assemble_tool_code(spec: ToolSpec, implementation: str) -> str:
    """Wrap model-generated implementation in the standard template."""
    # Strip markdown fences if model included them
    impl = re.sub(r"```python?\s*", "", implementation)
    impl = re.sub(r"```", "", impl).strip()

    return TOOL_TEMPLATE.format(
        tool_name=spec.tool_name,
        purpose=spec.purpose,
        implementation=impl,
    )


# ── Validation ───────────────────────────────────────────

def validate_tool(code: str, spec: ToolSpec, project_dir: str) -> tuple[bool, str]:
    """Validate generated tool code.  Returns (passed, error_msg)."""

    # 1. Syntax check — write to temp file and py_compile
    fd, tmp_path = tempfile.mkstemp(suffix=".py", dir=project_dir)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(code)

        try:
            py_compile.compile(tmp_path, doraise=True)
        except py_compile.PyCompileError as exc:
            return False, f"Syntax error: {exc.msg}"

        # 2. AST parse — redundant but catches edge cases
        try:
            import ast
            ast.parse(code)
        except SyntaxError as exc:
            return False, f"AST parse error line {exc.lineno}: {exc.msg}"

        # 3. Has a run() function
        if not re.search(r"^def run\(", code, re.MULTILINE):
            return False, "Missing required run() function"

        # 4. Has TOOL_NAME
        if "TOOL_NAME" not in code:
            return False, "Missing TOOL_NAME constant"

        # 5. Dry run — execute the file with a synthetic test input
        # Strip the environment so generated code cannot exfiltrate tokens or
        # API keys that exist in the parent process (GITHUB_TOKEN, ANTHROPIC_API_KEY, etc.)
        clean_env = {
            k: os.environ[k]
            for k in ("PATH", "PYTHONPATH", "SYSTEMROOT", "TEMP", "TMP", "HOME", "LANG", "TERM")
            if k in os.environ
        }
        test_args = _make_test_args(spec)
        try:
            result = subprocess.run(
                [sys.executable, tmp_path] + test_args,
                capture_output=True, text=True,
                timeout=10,
                cwd=project_dir,
                env=clean_env,
            )
            if result.returncode != 0:
                err = (result.stderr or result.stdout or "").strip()
                # Allow [TOOL ERROR] returns — that means error handling works
                if "[TOOL ERROR]" in (result.stdout or ""):
                    pass  # Graceful error handling — acceptable
                else:
                    return False, f"Dry run failed (exit {result.returncode}): {err[:300]}"
        except subprocess.TimeoutExpired:
            return False, "Dry run timed out (10s)"
        except Exception as exc:
            return False, f"Dry run error: {exc}"

    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

    return True, ""


def _make_test_args(spec: ToolSpec) -> list[str]:
    """Generate synthetic CLI args for a dry run based on spec inputs."""
    args = []
    for inp in spec.inputs:
        parts = inp.split(":")
        type_hint = parts[1].strip().lower() if len(parts) > 1 else "str"
        if "int" in type_hint:
            args.append("1")
        elif "float" in type_hint:
            args.append("1.0")
        elif "bool" in type_hint:
            args.append("true")
        elif "path" in parts[0].lower() or "file" in parts[0].lower():
            args.append("__test_nonexistent__")
        else:
            args.append("test_input")
    return args


# ── File placement ───────────────────────────────────────

def place_tool_file(
    code: str,
    spec: ToolSpec,
    project_dir: str,
) -> str:
    """Write generated tool to quarantine. Returns the relative quarantine path.

    Tools in quarantine/ are NOT executed and NOT registered.  A human must
    review the file and explicitly move it to tools/run/ to activate it.
    """
    quarantine_dir = os.path.join(project_dir, QUARANTINE_DIR)
    os.makedirs(quarantine_dir, exist_ok=True)

    filename = f"{spec.tool_name}.py.pending"
    final_path = os.path.join(quarantine_dir, filename)

    # Atomic write: tmp → rename (FAT32-safe)
    tmp_path = final_path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        f.write(code)
    os.replace(tmp_path, final_path)

    return os.path.join(QUARANTINE_DIR, filename)


# ── Logging ──────────────────────────────────────────────

def log_forge_event(
    result: ForgeResult,
    spec: ToolSpec,
    project_dir: str,
) -> None:
    """Append a JSONL entry to the forge log."""
    log_dir = os.path.join(project_dir, "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(project_dir, LOG_FILE)

    entry = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "tool_name": f"run_{spec.tool_name}",
        "purpose": spec.purpose,
        "success": result.success,
        "attempts": result.attempts,
        "elapsed_s": round(result.elapsed_s, 2),
        "file": result.file_path,
        "deps": spec.dependencies,
    }
    if result.error:
        entry["error"] = result.error[:300]

    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


# ── Forge pipeline (the main entry) ─────────────────────

def forge_tool(
    spec: ToolSpec,
    generate_fn,
    project_dir: str,
    registry: Optional["ToolRegistry"] = None,
) -> ForgeResult:
    """Full forge pipeline: generate → validate → place → register.

    Args:
        spec: Tool blueprint from the researcher.
        generate_fn: Callable(prompt: str) -> str.
            Calls the local model and returns raw text.
        project_dir: Absolute path to the project root.
        registry: If provided, hot-registers the tool immediately.

    Returns:
        ForgeResult with success/failure details.
    """
    t0 = time.time()
    prompt = build_forge_prompt(spec)

    last_error = ""
    code = ""

    for attempt in range(1, MAX_RETRIES + 1):
        # Generate (or re-generate with error context)
        if attempt > 1:
            fix_prompt = (
                f"{prompt}\n\n"
                f"PREVIOUS ATTEMPT FAILED: {last_error}\n"
                "Fix the issue and try again.  Return ONLY the corrected code."
            )
            raw = generate_fn(fix_prompt)
        else:
            raw = generate_fn(prompt)

        code = assemble_tool_code(spec, raw)
        passed, error = validate_tool(code, spec, project_dir)

        if passed:
            file_path = place_tool_file(code, spec, project_dir)
            result = ForgeResult(
                tool_name=f"run_{spec.tool_name}",
                success=True,
                file_path=file_path,
                code=code,
                attempts=attempt,
                elapsed_s=time.time() - t0,
            )
            # Tool is in quarantine — human must review and activate.
            # Hot-registration is intentionally removed: the registry parameter
            # is accepted for API compatibility but ignored.  To activate:
            #   1. Review tools/quarantine/<name>.py.pending
            #   2. mv tools/quarantine/<name>.py.pending tools/run/<name>.py
            #   3. Update tools/run/registry.json
            log_forge_event(result, spec, project_dir)
            return result

        last_error = error

    # All retries exhausted
    result = ForgeResult(
        tool_name=f"run_{spec.tool_name}",
        success=False,
        error=last_error,
        code=code,
        attempts=MAX_RETRIES,
        elapsed_s=time.time() - t0,
    )
    log_forge_event(result, spec, project_dir)
    return result


def activate_quarantined_tool(
    pending_path: str,
    project_dir: str,
    registry: Optional["ToolRegistry"] = None,
) -> str:
    """Move a reviewed tool from quarantine to tools/run/ and optionally register it.

    This is the human-gated activation step.  Call it explicitly after
    reviewing the quarantined file.

    Args:
        pending_path: Relative path to the .py.pending file in tools/quarantine/.
        project_dir:  Absolute path to the project root.
        registry:     If provided, registers the tool in the live registry.

    Returns:
        The relative path of the activated tool in tools/run/.
    """
    from app.agent.tool_registry import ScriptTool, ToolSpec as RegSpec

    src = Path(project_dir) / pending_path
    if not src.exists():
        raise FileNotFoundError(f"Quarantined tool not found: {src}")
    if not src.name.endswith(".py.pending"):
        raise ValueError(f"Not a quarantine file: {src.name}")

    tool_filename = src.name[: -len(".pending")]  # strip .pending
    dst = Path(project_dir) / TOOL_DIR / tool_filename

    dst.parent.mkdir(parents=True, exist_ok=True)
    import shutil
    shutil.move(str(src), str(dst))

    if registry is not None:
        tool_name = f"run_{dst.stem}"
        reg_spec = RegSpec(
            name=tool_name,
            description=f"Activated from quarantine: {dst.name}",
            args=[],
            side_effect="exec",
            timeout_seconds=30,
        )
        runner = ScriptTool(name=dst.stem, script_path=dst, spec=reg_spec)
        registry._register(reg_spec, runner.run)

    return str(Path(TOOL_DIR) / tool_filename)
