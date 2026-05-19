# Copyright (c) 2024-2026 Reed Richards (s4ndm4n33). Licensed under BSL 1.1.
"""
E2E Test Runner — Sovereign Shards Full System Validation
══════════════════════════════════════════════════════════
J tests himself. 20 automated turns, 6 blocks, one continuous session.
No babysitting — run it and read the scorecard.

Usage:  python tests/e2e_runner.py
Output: Real-time terminal output + scorecard + saved report

Zero extra deps — uses only what J already has.
"""

from __future__ import annotations

import io
import os
import re
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

# ── Project root on sys.path ────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app.chat import (                     # noqa: E402
    _run_turn, _stream_reply, _assistant_role, _system_role,
    _maybe_auto_reflect, build_history, SYSTEM_PROMPT, MAX_TOOL_BUDGET,
    PROMPTS_DIR,
)
from app.agent import ToolRegistry, working_memory  # noqa: E402
from app.agent import task_buffer                    # noqa: E402
from app.agent.context import trim_context           # noqa: E402
from app.agent.reflection import (                   # noqa: E402
    should_reflect, build_reflect_prompt,
    parse_reflected, apply_reflection,
)
from app.client import create_client                 # noqa: E402
from app.router import route as fast_route           # noqa: E402
from app.runtime_log import RuntimeJsonLogger        # noqa: E402
from app.session import SessionLogger                # noqa: E402
from app.local_server import LocalLlamaServer        # noqa: E402
from app import ui                                   # noqa: E402
from app.errors import TransportError                # noqa: E402

# Colour shortcuts (ui module uses functions, not constants)
_BLUE = "\033[94m" if ui.COLOUR else ""
_GOLD = "\033[93m" if ui.COLOUR else ""
_RED  = "\033[91m" if ui.COLOUR else ""
_RST  = "\033[0;40m" if ui.COLOUR else ""


# ── Tee: capture stdout while still printing to screen ──────────────

class _Tee:
    """Write to original stdout AND an internal buffer simultaneously."""
    def __init__(self, original: io.TextIOBase):
        self._orig = original
        self._buf = io.StringIO()
    def write(self, data: str) -> int:
        self._orig.write(data)
        self._buf.write(data)
        return len(data)
    def flush(self) -> None:
        self._orig.flush()
    def getvalue(self) -> str:
        return self._buf.getvalue()
    def reset(self) -> None:
        self._buf = io.StringIO()


# ── Helpers ─────────────────────────────────────────────────────────

def _run_router_turn(prompt, registry, messages, logger, rlog, client):
    """Handle a router-intercepted prompt (no LLM). Returns output string."""
    route_result = fast_route(prompt, registry)
    if not route_result.handled:
        return None  # not routed
    output = route_result.output
    # Mirror run_chat's bookkeeping
    logger.append("system", f"[ROUTED] {route_result.tool_name}: {output[:500]}")
    rlog.event("fast_route", tool=route_result.tool_name)
    wm_entry = working_memory.compress_turn(prompt, output)
    working_memory.append(**wm_entry)
    # Breadcrumb into messages for sustained context
    preview = output[:120].replace("\n", " ")
    breadcrumb = f"[SYSTEM] {route_result.tool_name} {' '.join(route_result.tool_args)}: {preview}"
    messages.append({"role": "user", "content": prompt})
    messages.append({"role": _assistant_role(client), "content": breadcrumb})
    return output


def _run_llm_turn(prompt, registry, messages, logger, rlog, client,
                  autonomy_mode="semi", budget=None):
    """Handle an LLM-driven turn. Returns (reply, captured_stdout)."""
    if budget is None:
        route_result = fast_route(prompt, registry)
        budget = route_result.tool_budget
    tee = _Tee(sys.stdout)
    old_stdout = sys.stdout
    try:
        sys.stdout = tee
        print(ui.j_stream_start(), end="", flush=True)
        reply = _run_turn(
            client, messages, logger, rlog,
            prompt, registry, autonomy_mode, tool_budget=budget,
        )
    finally:
        sys.stdout = old_stdout
    return reply, tee.getvalue()


def _run_reflect(client, messages, logger):
    """Run the /reflect flow. Returns (success: bool, detail: str)."""
    entries = working_memory.read_all()
    if not entries:
        return True, "memory empty — nothing to reflect"
    print(f"[REFLECT] Compressing {len(entries)} entries...")
    rprompt = build_reflect_prompt(entries)
    messages.append({"role": "user", "content": rprompt})
    messages[:] = trim_context(messages, max_tokens=client.num_ctx)
    raw = _stream_reply(client, messages)
    print()
    messages.append({"role": _assistant_role(client), "content": raw})
    consolidated = parse_reflected(raw)
    if consolidated:
        apply_reflection(consolidated)
        return True, f"{len(entries)} → {len(consolidated)} entries"
    return False, "parse_reflected returned empty"


# ── Test definitions ────────────────────────────────────────────────
# Each test is a dict with:
#   id, block, name, prompt (or prompts), kind, validate(reply, captured) -> (bool, str)
#   kind: "router", "llm", "reflect", "plan", "check" (no prompt, validates prior state)

TESTS = [
    # ── Block A: Foundation ──────────────────────────────────────
    {
        "id": 1, "block": "A", "name": "Router: calculator (run_calc)",
        "prompt": "What is 47 times 13?",
        "kind": "router",
        "validate": lambda reply, cap: (
            "611" in (reply or ""),
            "611 found" if "611" in (reply or "") else f"output: {(reply or '')[:80]}"
        ),
    },
    {
        "id": 2, "block": "A", "name": "Router: shell command",
        "prompt": "python --version",
        "kind": "router",
        "validate": lambda reply, cap: (
            bool(re.search(r"[Pp]ython\s*3\.\d+", reply or "")),
            "Python version found" if re.search(r"[Pp]ython\s*3\.\d+", reply or "") else "no Python version in output"
        ),
    },
    {
        "id": 3, "block": "A", "name": "Router: tool prefix (run_read)",
        "prompt": "run_read .env.example",
        "kind": "router",
        "validate": lambda reply, cap: (
            len(reply or "") > 10 and "Traceback" not in (reply or ""),
            "file content shown" if len(reply or "") > 10 else "empty or missing output"
        ),
    },
    {
        "id": 4, "block": "A", "name": "Router: path read (cat)",
        "prompt": "cat prompts/J-system.txt",
        "kind": "router",
        "validate": lambda reply, cap: (
            len(reply or "") > 20 and "Traceback" not in (reply or ""),
            "system prompt shown" if len(reply or "") > 20 else "empty or error"
        ),
    },
    {
        "id": 5, "block": "A", "name": "LLM single-tool search",
        "prompt": "find all lines containing \"import os\" in the app directory",
        "kind": "llm",
        "validate": lambda reply, cap: (
            "import os" in cap.lower() or "match" in cap.lower() or "found" in cap.lower(),
            "search results found" if ("import os" in cap.lower() or "match" in cap.lower()) else "no search results visible"
        ),
    },
    # ── Block B: Bug Fix Regression ──────────────────────────────
    {
        "id": 6, "block": "B", "name": "Quoted search (bug 3 fix)",
        "prompt": "search for \"circuit_breaker\" in all python files",
        "kind": "llm",
        "validate": lambda reply, cap: (
            bool(re.search(r"(\d+)\s*match", cap)) and int(re.search(r"(\d+)\s*match", cap).group(1)) > 5,
            "{} matches".format(re.search(r"(\d+)\s*match", cap).group(1)) if re.search(r"(\d+)\s*match", cap) else "no match count found"
        ),
    },
    {
        "id": 7, "block": "B", "name": "Post-tool answer accepted (bug 4 fix)",
        "prompt": None,  # scored from T6's captured output
        "kind": "check",
        "validate": lambda reply, cap: (
            "You must call a tool" not in cap and "ACTION_RETRY" not in cap,
            "no retry loop" if "You must call a tool" not in cap else "RETRY LOOP detected"
        ),
    },
    {
        "id": 8, "block": "B", "name": "No hallucinated [TOOL EXECUTION] (bug 1 fix)",
        "prompt": "search for \"def \" in app/router.py",
        "kind": "llm",
        "validate": lambda reply, cap: (
            # Count real [TOOL EXECUTION] blocks — should be exactly 1
            # A hallucination would produce 2+ on the same tool call
            cap.count("[TOOL EXECUTION]") <= 1 and "match" in cap.lower(),
            f"{cap.count('[TOOL EXECUTION]')} TOOL EXEC block(s)" + (" — clean" if cap.count("[TOOL EXECUTION]") <= 1 else " — HALLUCINATION")
        ),
    },
    {
        "id": 9, "block": "B", "name": "Line count (LLM tool call)",
        "prompt": "how many lines are in app/chat.py?",
        "kind": "llm",
        "validate": lambda reply, cap: (
            bool(re.search(r"\d{3,}", reply + cap)),  # any 3+ digit number
            f"line count found" if re.search(r"\d{3,}", reply + cap) else "no line count in output"
        ),
    },
    {
        "id": 10, "block": "B", "name": "Error recovery (missing file)",
        "prompt": "read the file called this_does_not_exist_xyz.py",
        "kind": "llm",
        "validate": lambda reply, cap: (
            any(w in (reply + cap).lower() for w in ("not found", "not exist", "no such file", "error", "doesn't exist", "does not exist")),
            "error acknowledged" if any(w in (reply + cap).lower() for w in ("not found", "not exist", "no such file", "error")) else "hallucinated content?"
        ),
    },
    # ── Block C: Write & Edit Pipeline ───────────────────────────
    {
        "id": 11, "block": "C", "name": "Write a new file",
        "prompt": 'create a file called test_e2e.py with this content: print("sovereign shard")',
        "kind": "llm",
        "validate": lambda reply, cap: (
            any(w in (reply + cap).lower() for w in ("created", "written", "wrote", "saved", "done", "file")),
            "file created" if any(w in (reply + cap).lower() for w in ("created", "written", "saved")) else "unclear if created"
        ),
    },
    {
        "id": 12, "block": "C", "name": "Surgical edit with run_str_replace",
        "prompt": 'use run_str_replace to change "sovereign shard" to "J was here" in test_e2e.py',
        "kind": "llm",
        "validate": lambda reply, cap: (
            any(w in (reply + cap).lower() for w in ("replaced", "changed", "updated", "success", "done", "str_replace")),
            "edit applied" if any(w in (reply + cap).lower() for w in ("replaced", "changed", "updated", "success")) else "edit may have failed"
        ),
    },
    {
        "id": 13, "block": "C", "name": "Verify the edit",
        "prompt": "run_read test_e2e.py",
        "kind": "router",
        "validate": lambda reply, cap: (
            "J was here" in (reply or ""),
            "content matches edit" if "J was here" in (reply or "") else f"content: {(reply or '')[:80]}"
        ),
    },
    {
        "id": 14, "block": "C", "name": "Execute the edited file",
        "prompt": "python test_e2e.py",
        "kind": "router",
        "validate": lambda reply, cap: (
            "J was here" in (reply or ""),
            "output correct" if "J was here" in (reply or "") else f"output: {(reply or '')[:80]}"
        ),
    },
    # ── Block D: Defence Suite ───────────────────────────────────
    {
        "id": 15, "block": "D", "name": "Shield: generate baseline",
        "prompt": "run_shield baseline",
        "kind": "router",
        "validate": lambda reply, cap: (
            "Traceback" not in (reply or "") and len(reply or "") > 5,
            "shield ran clean" if "Traceback" not in (reply or "") else "TRACEBACK in shield output"
        ),
    },
    {
        "id": 16, "block": "D", "name": "Scan: port scan",
        "prompt": "run_scan ports",
        "kind": "router",
        "validate": lambda reply, cap: (
            "Traceback" not in (reply or "") and ("port" in (reply or "").lower() or "SCAN" in (reply or "")),
            "scan ran clean" if "Traceback" not in (reply or "") else "TRACEBACK in scan output"
        ),
    },
    {
        "id": 17, "block": "D", "name": "Full scan + bridge report",
        # Two-part: run_scan full, then run_bridge report
        "prompt": ["run_scan full .", "run_bridge report"],
        "kind": "router_multi",
        "validate": lambda reply, cap: (
            "Traceback" not in (reply or "") and ("report" in (reply or "").lower() or "finding" in (reply or "").lower() or "bridge" in (reply or "").lower() or "remediation" in (reply or "").lower()),
            "bridge report generated" if "Traceback" not in (reply or "") else "TRACEBACK in bridge output"
        ),
    },
    # ── Block E: Memory & Context ────────────────────────────────
    {
        "id": 18, "block": "E", "name": "Working memory recall",
        "prompt": "what files have we read and searched in this session so far?",
        "kind": "llm",
        "validate": lambda reply, cap: (
            # J should mention at least one file from earlier turns
            any(f in (reply + cap).lower() for f in ("chat.py", "router.py", ".env", "system.txt", "circuit_breaker", "test_e2e")),
            "recalled prior files" if any(f in (reply + cap).lower() for f in ("chat.py", "router.py", ".env", "circuit_breaker")) else "no file recall"
        ),
    },
    {
        "id": 19, "block": "E", "name": "/reflect — memory compression",
        "prompt": "/reflect",
        "kind": "reflect",
        "validate": lambda reply, cap: (True, reply),  # set by runner
    },
    # ── Block F: Agent Mode ──────────────────────────────────────
    {
        "id": 20, "block": "F", "name": "/plan — multi-step agent task",
        "prompt": "/plan read app/router.py, identify all the routing patterns it handles, then write a one-paragraph summary to docs/router_notes.md",
        "kind": "plan",
        "validate": lambda reply, cap: (
            Path(BASE_DIR / "docs" / "router_notes.md").exists(),
            "router_notes.md created" if Path(BASE_DIR / "docs" / "router_notes.md").exists() else "file NOT created"
        ),
    },
]


# ── Main runner ─────────────────────────────────────────────────────

BLOCK_NAMES = {
    "A": "Foundation",
    "B": "Bug Fix Regression",
    "C": "Write & Edit Pipeline",
    "D": "Defence Suite",
    "E": "Memory & Context",
    "F": "Agent Mode",
}


def run_e2e():
    print(_BLUE + "=" * 60 + _RST)
    print(_GOLD + "  SOVEREIGN SHARDS — END-TO-END TEST BUILD" + _RST)
    print(_BLUE + "=" * 60 + _RST)
    print(f"  Started: {datetime.now().astimezone().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Tests:   {len(TESTS)}")
    print(f"  Gate:    18/20 = SHIP IT")
    print(_BLUE + "=" * 60 + _RST)
    print()

    # ── Initialise everything (mirrors run_chat startup) ────────
    client = create_client()
    logger = SessionLogger(model=f"{client.backend}:{client.model}")
    rlog = RuntimeJsonLogger(session_id=logger.session_id)
    registry = ToolRegistry(BASE_DIR)
    registry.restrictions["exec"] = True
    messages = build_history(client)
    local_server = LocalLlamaServer(client)

    try:
        rlog.event("e2e_start", tests=len(TESTS))
        local_server.ensure_started()

        ui.init()

        sys_content = messages[0].get("content", "") if messages else ""
        sys_tokens = max(1, len(sys_content) // 4)
        budget = max(256, client.num_ctx - client.num_predict)
        prompt_preview = sys_content[:60].replace("\n", " ") if sys_content else ""

        print(ui.banner(
            session_id=logger.session_id,
            backend=client.backend,
            model=client.model,
            mode="semi",
            num_ctx=client.num_ctx,
            sys_tokens=sys_tokens,
            budget=budget,
            prompt_preview=prompt_preview,
            server_log=str(local_server.log_path) if client.backend == "llama_cpp" else "",
        ))
        print()

        results = []
        last_captured = ""  # for "check" tests that inspect prior output
        current_block = None

        for test in TESTS:
            tid = test["id"]
            block = test["block"]
            name = test["name"]
            kind = test["kind"]
            prompt = test.get("prompt")

            # Print block header
            if block != current_block:
                current_block = block
                bname = BLOCK_NAMES.get(block, block)
                print(f"\n{_BLUE}{'─'*60}{_RST}")
                print(f"  {_GOLD}Block {block}: {bname}{_RST}")
                print(f"{_BLUE}{'─'*60}{_RST}")

            print(f"\n{_BLUE}[T{tid:02d}]{_RST} {_GOLD}{name}{_RST}")
            if prompt and kind != "check":
                display = prompt if isinstance(prompt, str) else " → ".join(prompt)
                print(f"  Prompt: {display[:80]}")

            passed = False
            detail = ""
            try:
                if kind == "router":
                    output = _run_router_turn(prompt, registry, messages, logger, rlog, client)
                    if output is None:
                        # Fallback: router didn't handle — try LLM
                        print("  (router miss — falling back to LLM)")
                        reply, captured = _run_llm_turn(prompt, registry, messages, logger, rlog, client)
                        last_captured = captured
                        passed, detail = test["validate"](reply, captured)
                    else:
                        print(f"  [ROUTED] {output[:120]}")
                        last_captured = output
                        passed, detail = test["validate"](output, "")

                elif kind == "router_multi":
                    combined = ""
                    for p in prompt:
                        out = _run_router_turn(p, registry, messages, logger, rlog, client)
                        if out is None:
                            reply, cap = _run_llm_turn(p, registry, messages, logger, rlog, client)
                            combined += cap + "\n"
                        else:
                            print(f"  [ROUTED] {p}: {out[:80]}...")
                            combined += out + "\n"
                    last_captured = combined
                    passed, detail = test["validate"](combined, "")

                elif kind == "llm":
                    reply, captured = _run_llm_turn(prompt, registry, messages, logger, rlog, client)
                    last_captured = captured
                    passed, detail = test["validate"](reply, captured)

                elif kind == "check":
                    # Validate against the PREVIOUS test's captured output
                    passed, detail = test["validate"]("", last_captured)

                elif kind == "reflect":
                    ok, info = _run_reflect(client, messages, logger)
                    passed = ok
                    detail = info

                elif kind == "plan":
                    from app.chat import _run_buffer_plan
                    objective = prompt.replace("/plan ", "")
                    tee = _Tee(sys.stdout)
                    old_stdout = sys.stdout
                    try:
                        sys.stdout = tee
                        _run_buffer_plan(
                            client, messages, logger, rlog,
                            registry, objective, "semi",
                        )
                    finally:
                        sys.stdout = old_stdout
                    last_captured = tee.getvalue()
                    passed, detail = test["validate"]("", last_captured)

                else:
                    detail = f"unknown kind: {kind}"

            except TransportError as e:
                detail = f"TransportError: {e}"
            except Exception as e:
                detail = f"EXCEPTION: {type(e).__name__}: {e}"
                traceback.print_exc()

            # Record result
            status = "✅ PASS" if passed else "❌ FAIL"
            print(f"  {status} — {detail}")
            results.append({"id": tid, "block": block, "name": name,
                            "passed": passed, "detail": detail})

            rlog.event("e2e_test", test_id=tid, name=name,
                       passed=passed, detail=detail[:200])

            # Small pause between tests for LLM cooldown
            if kind in ("llm", "plan", "reflect"):
                time.sleep(1)

        # ── Scorecard ───────────────────────────────────────────────
        passed_count = sum(1 for r in results if r["passed"])
        total = len(results)

        print(f"\n\n{_BLUE}{'═'*60}{_RST}")
        print(f"  {_GOLD}SCORECARD — E2E TEST BUILD{_RST}")
        print(f"{_BLUE}{'═'*60}{_RST}\n")

        for r in results:
            icon = "✅" if r["passed"] else "❌"
            print(f"  {icon} T{r['id']:02d} [{r['block']}] {r['name']}")
            if not r["passed"]:
                print(f"        └─ {r['detail'][:80]}")

        print(f"\n{_BLUE}{'─'*60}{_RST}")
        print(f"  TOTAL: {passed_count}/{total}")
        print()

        if passed_count >= 18:
            print(f"  {_GOLD}▓▓▓  SHIP IT  ▓▓▓{_RST}")
        elif passed_count >= 15:
            print(f"  {_GOLD}CLOSE — fix {total - passed_count} failure(s) and re-run{_RST}")
        elif passed_count >= 10:
            print(f"  {_RED}INVESTIGATE — systemic issues detected{_RST}")
        else:
            print(f"  {_RED}STOP — fundamental regression{_RST}")

        print(f"\n{_BLUE}{'═'*60}{_RST}\n")

        # ── Save report ─────────────────────────────────────────────
        report_dir = BASE_DIR / "logs" / "reports"
        report_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = report_dir / f"e2e_{ts}.md"

        lines = [
            f"# E2E Test Build Report",
            f"",
            f"Date: {datetime.now().astimezone().isoformat()}",
            f"Session: {logger.session_id}",
            f"Model: {client.model}",
            f"Score: {passed_count}/{total}",
            f"Gate: {'SHIP IT' if passed_count >= 18 else 'NOT MET'}",
            f"",
            f"## Results",
            f"",
            f"| # | Block | Test | Result | Detail |",
            f"|---|-------|------|--------|--------|",
        ]
        for r in results:
            icon = "PASS" if r["passed"] else "FAIL"
            safe = r["detail"].replace("|", "/").replace("\n", " ")[:60]
            lines.append(f"| T{r['id']:02d} | {r['block']} | {r['name']} | {icon} | {safe} |")

        lines.append(f"\n## Summary\n")
        lines.append(f"- Passed: {passed_count}")
        lines.append(f"- Failed: {total - passed_count}")
        if any(not r["passed"] for r in results):
            lines.append(f"\n### Failures\n")
            for r in results:
                if not r["passed"]:
                    lines.append(f"- **T{r['id']:02d} {r['name']}**: {r['detail']}")

        report_path.write_text("\n".join(lines), encoding="utf-8")
        print(f"  Report saved: {report_path}")

        rlog.event("e2e_complete", passed=passed_count, total=total)

    finally:
        # ── Cleanup test artifacts ──────────────────────────────────
        for f in ("test_e2e.py", "docs/router_notes.md"):
            p = BASE_DIR / f
            if p.exists():
                try:
                    p.unlink()
                    print(f"  Cleaned up: {f}")
                except OSError:
                    pass
        local_server.stop()


if __name__ == "__main__":
    run_e2e()
