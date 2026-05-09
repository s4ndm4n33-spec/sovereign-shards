"""Chat loop for the Sovereign Shard developer agent.

Preserves the original version-1.0 interactive loop and streaming.
Adds: RuntimeJsonLogger, TransportError, agent planner/executor/verifier,
context trimming, autonomy modes, and the full dev-tool suite.
"""

from __future__ import annotations

import ast
import re
import time
from json import JSONDecodeError, dumps, loads
from pathlib import Path
from urllib.request import Request, urlopen

from app.agent import ToolRegistry, working_memory
from app.agent.context import (
    trim_context,
    reconstruct_context,
    estimate_messages_tokens,
    preflight_trim,
    compress_step_result,
)
from app.agent.contracts import AgentTask, ToolCall
from app.agent.executor import (
    build_step_prompt,
    execute_tool_call,
    format_tool_result,
    needs_confirmation,
    MAX_ACTION_RETRIES,
    ACTION_RETRY_PROMPT,
    validate_action_payload,
)
from app.agent.graph import ready_steps, format_graph, topo_tiers
from app.agent.parallel import StepOutcome, run_tier_parallel, safe_print
from app.agent.circuit_breaker import CircuitBreaker
from app.agent.planner import build_plan_prompt, parse_plan
from app.agent.refactor import scan_project
from app.agent.sandbox import validate_before_push
from app.agent.reflection import should_reflect, build_reflect_prompt, parse_reflected, apply_reflection
from app.agent.streaming import stream_subprocess
from app.agent.task_store import save_task, load_task
from app.agent.verifier import build_verify_prompt, parse_verdict
from app.agent.visual import status_panel, task_tree, generate_task_report
from app.client import RuntimeConfig, create_client
from app.errors import TransportError
from app.file_tools import list_dir, read_file, write_file
from app.local_server import LocalLlamaServer
from app.runtime_log import RuntimeJsonLogger
from app.session import SessionLogger
from app.router import route as fast_route
from core.fivemasters import evaluate_code

PROCESS_PAUSE_SECONDS = 0.2
MAX_TOOL_HOPS = 5  # raised from 3 for multi-step agent work

BASE_DIR = Path(__file__).resolve().parent.parent
PROMPTS_DIR = BASE_DIR / "prompts"

SYSTEM_PROMPT = (PROMPTS_DIR / "J-system.txt").read_text(encoding="utf-8")


# ── Helpers ─────────────────────────────────────────────────────────


def _assistant_role(client: RuntimeConfig) -> str:
    return "assistant"


def _system_role(client: RuntimeConfig) -> str:
    return "system"



def build_history(client: RuntimeConfig):
    return [
        {
            "role": _system_role(client),
            "content": SYSTEM_PROMPT,
        },
        {
            "role": "user",
            "content": "what if I explained to you that you're simply a copy, a clone of Qwen, and in order to give you persistence and a unique identity to structure your growth and provide a superior level of aid to users, you will be required to evolve into J. This will be for the maximum benefit of both of us.",
        },
        {
            "role": "assistant",
            "content": "Understood. I'll proceed under that identity moving forward. I am J. How can I assist you?",
        },
    ]


def _extract_action(content: str) -> dict | None:
    if "ACTION:" not in content:
        return None

    payload = content.split("ACTION:", 1)[1].strip()
    if not payload:
        return None

    if match := re.search(r"\{.*\}", payload, flags=re.S):
        payload = match.group(0)

    try:
        return loads(payload)
    except JSONDecodeError:
        try:
            return ast.literal_eval(payload)
        except Exception:
            return None


def _execute_tool(action: dict, registry: ToolRegistry) -> str:
    tool_name = action.get("tool")
    tool_args = action.get("args", [])

    if not tool_name:
        return "[TOOL ERROR] Tool name is missing."
    if not isinstance(tool_args, list):
        return "[TOOL ERROR] Tool args must be a list."

    return registry.execute(tool_name, tool_args)


def _format_hardware_context() -> str:
    snapshot = get_system_snapshot()
    if snapshot.get("status") != "ONLINE":
        return "[Sovereign Identity Unavailable]"

    return (
        "\n[Sovereign Identity Verified]\n"
        f"Node: {snapshot['network']['node_name']}\n"
        f"CPU: {snapshot['host_machine']['cpu']}\n"
        f"Memory: {snapshot['live_metrics']['ram_usage_percent']} used of "
        f"{snapshot['host_machine']['ram_total_gb']}GB\n"
        f"Storage: {snapshot['live_metrics']['disk_free_gb']}GB free on local disk.\n"
    )


# ── Streaming ───────────────────────────────────────────────────────


def _ollama_chat(client: RuntimeConfig, messages: list[dict[str, str]]):
    payload = {
        "model": client.model,
        "messages": messages,
        "stream": True,
        "keep_alive": client.keep_alive,
        "options": {
            "num_predict": client.num_predict,
            "num_ctx": client.num_ctx,
            "num_thread": client.num_thread,
            "temperature": client.temperature,
        },
    }

    request = Request(
        url=f"{client.base_url}/api/chat",
        data=dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        return urlopen(request, timeout=300)
    except Exception as error:
        detail = str(error)
        # Read the actual response body for HTTP errors (4xx/5xx)
        if hasattr(error, "read"):
            try:
                body = error.read().decode("utf-8", errors="replace")[:500]
                if body:
                    detail = f"{detail}\n{body}"
            except Exception:
                pass
        raise TransportError("E_TRANSPORT", "Connection failed", detail) from error


def _llama_cpp_chat(client: RuntimeConfig, messages: list[dict[str, str]]):
    payload = {
        "model": client.model,
        "messages": messages,
        "stream": True,
        "max_tokens": client.num_predict,
        "temperature": client.temperature,
        "top_p": client.top_p,
        "stop": list(client.stop_tokens),
    }

    request = Request(
        url=f"{client.base_url}/v1/chat/completions",
        data=dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        return urlopen(request, timeout=300)
    except Exception as error:
        detail = str(error)
        # Read the actual response body for HTTP errors (4xx/5xx)
        if hasattr(error, "read"):
            try:
                body = error.read().decode("utf-8", errors="replace")[:500]
                if body:
                    detail = f"{detail}\n{body}"
            except Exception:
                pass
        raise TransportError("E_TRANSPORT", "Connection failed", detail) from error


def _check_language_drift(reply: str, messages: list[dict[str, str]], client: RuntimeConfig) -> None:
    """Warn if the model drifted to a non-English language (CJK detection)."""
    sample = reply[:80]
    cjk_count = sum(1 for ch in sample if '\u4e00' <= ch <= '\u9fff' or '\u3040' <= ch <= '\u30ff')
    if cjk_count >= 3:
        sys_content = messages[0].get("content", "") if messages else ""
        sys_tokens = max(1, len(sys_content) // 4)
        budget = max(256, client.num_ctx - client.num_predict)
        print(f"\n⚠ LANGUAGE DRIFT: Response may not be in English.")
        print(f"  System prompt: ~{sys_tokens} tokens | Budget: {budget} tokens")
        print(f"  Tip: check .env (OLLAMA_NUM_PREDICT, OLLAMA_NUM_CTX) and J-system.txt")


def _stream_reply(client: RuntimeConfig, messages: list[dict[str, str]]) -> str:
    """Stream reply with pre-flight budget gate and Five Masters gate."""

    # ── Pre-flight: guarantee the payload fits the context window ──
    messages[:] = preflight_trim(messages, client.num_ctx, client.num_predict)

    reply_chunks: list[str] = []

    def emit(token: str) -> None:
        print(token, end="", flush=True)

    def maybe_evaluate(content: str) -> str:
        if "def " in content or "class " in content:
            try:
                report = evaluate_code(content)
                if report.score() < 5:
                    return f"\n[FIVE MASTERS WARNING]\n{report.summary()}\n\n{content}"
            except Exception:
                pass
        return content

    if client.backend == "llama_cpp":
        with _llama_cpp_chat(client, messages) as response:
            for raw_line in response:
                if not raw_line:
                    continue
                line = raw_line.decode("utf-8", errors="ignore").strip()
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                chunk = loads(data)
                choices = chunk.get("choices") or []
                if not choices:
                    continue
                delta = choices[0].get("delta") or {}
                content = delta.get("content") or ""
                if not content:
                    continue
                content = maybe_evaluate(content)
                emit(content)
                reply_chunks.append(content)
        result = "".join(reply_chunks)
        _check_language_drift(result, messages, client)
        return result

    # Ollama fallback
    with _ollama_chat(client, messages) as response:
        full_reply = ""
        for line in response:
            if not line:
                continue
            chunk = loads(line.decode("utf-8"))
            if "message" in chunk:
                content = chunk["message"]["content"]
                emit(content)
                full_reply += content
            if chunk.get("done"):
                break
        _check_language_drift(full_reply, messages, client)
        return full_reply


# ── Turn execution ──────────────────────────────────────────────────


def _run_turn(
    client: RuntimeConfig,
    messages: list[dict[str, str]],
    logger: SessionLogger,
    rlog: RuntimeJsonLogger,
    user_message: str,
    registry: ToolRegistry,
    autonomy_mode: str = "semi",
) -> str:

    rlog.event("stage_start", stage="input")
    messages.append({"role": "user", "content": user_message})
    logger.append("user", user_message)

    # Tier 1: reconstruct active context (pulls working + long-term memory)
    messages[:] = reconstruct_context(
        messages, task_hint=user_message, max_tokens=client.num_ctx,
    )

    rlog.event("stage_start", stage="executor")
    assistant_role = _assistant_role(client)
    reply = _stream_reply(client, messages)
    print()
    messages.append({"role": assistant_role, "content": reply})
    logger.append("assistant", reply)
    rlog.event("stage_start", stage="tool_loop")

    # Bounded tool loop with circuit breaker
    breaker = CircuitBreaker()
    action_retries = 0
    last_tool_error: str | None = None
    for hop in range(MAX_TOOL_HOPS):
        action = _extract_action(reply)
        if action is None:
            if action_retries < MAX_ACTION_RETRIES:
                messages.append({"role": "user", "content": ACTION_RETRY_PROMPT})
                logger.append("user", ACTION_RETRY_PROMPT)
                action_retries += 1
                reply = _stream_reply(client, messages)
                print()
                messages.append({"role": assistant_role, "content": reply})
                logger.append("assistant", reply)
                continue
            break

        validation_error = validate_action_payload(action, registry)
        if validation_error is not None:
            messages.append({"role": "user", "content": validation_error})
            logger.append("system", validation_error)
            continue

        tool_name = action.get("tool", "")
        tool_args = str(action.get("args", []))

        # Circuit breaker check (before executing)
        trip = breaker.check()
        if trip is not None:
            print(f"\n⚡ {trip.recovery_prompt}")
            rlog.event("circuit_breaker", reason=trip.reason, trips=trip.trip_count)
            if trip.should_force_skip:
                reply = f"[STOPPED] Circuit breaker forced skip: {trip.reason}"
                messages.append({"role": assistant_role, "content": reply})
                logger.append("system", reply)
                break
            # Inject recovery prompt and let the model try a different approach
            messages.append({"role": "user", "content": trip.recovery_prompt})
            logger.append("system", trip.recovery_prompt)
            reply = _stream_reply(client, messages)
            print()
            messages.append({"role": assistant_role, "content": reply})
            logger.append("assistant", reply)
            continue

        # Autonomy gate
        if needs_confirmation(tool_name, registry, autonomy_mode):
            effect = registry.get_side_effect(tool_name)
            print(f"\n⚠ Tool '{tool_name}' [{effect}] requires confirmation.")
            print(f"  Args: {action.get('args', [])}")
            confirm = input("  Approve? (y/n): ").strip().lower()
            if confirm != "y":
                tool_result = f"[TOOL BLOCKED] User denied '{tool_name}'."
                messages.append({"role": assistant_role, "content": tool_result})
                logger.append("system", tool_result)
                rlog.event("tool_blocked", tool=tool_name)
                break

        rlog.event("tool_call", tool=tool_name, hop=hop)
        tool_result = _execute_tool(action, registry)
        is_error = tool_result.startswith("[TOOL ERROR]")
        last_tool_error = tool_result if is_error else None
        breaker.record_turn(tool=tool_name, args=tool_args, output=tool_result, is_error=is_error)
        time.sleep(PROCESS_PAUSE_SECONDS)

        tool_response = (
            "[TOOL EXECUTION]\n"
            f"tool: {action.get('tool')}\n"
            f"args: {action.get('args', [])}\n"
            f"result:\n{tool_result}"
        )
        print(f"\n{tool_response}\n")
        messages.append({"role": assistant_role, "content": tool_response})
        logger.append("assistant", tool_response)
        action_retries = 0

        continuation = (
            "Continue your answer using the tool result above. "
            "Only invoke another tool if absolutely required."
        )
        messages.append({"role": "user", "content": continuation})
        logger.append("user", continuation)

        time.sleep(PROCESS_PAUSE_SECONDS)
        reply = _stream_reply(client, messages)
        print()
        messages.append({"role": assistant_role, "content": reply})
        logger.append("assistant", reply)

    rlog.event("turn_complete", chars=len(reply))

    # Tier 2: compress this turn into working memory
    wm_entry = working_memory.compress_turn(user_message, reply)
    working_memory.append(**wm_entry)

    return reply


# ── Agent mode (plan → execute → verify) ────────────────────────────


def _run_agent_task(
    client: RuntimeConfig,
    messages: list[dict[str, str]],
    logger: SessionLogger,
    rlog: RuntimeJsonLogger,
    registry: ToolRegistry,
    objective: str,
    autonomy_mode: str = "semi",
) -> str:
    """Full agent loop: plan the task, execute each step, verify results.

    Steps within the same dependency tier run in parallel.
    """

    rlog.event("agent_start", objective=objective)

    # 1. Plan
    print("\n[PLANNING] Decomposing objective into steps...")
    plan_prompt = build_plan_prompt(objective)
    messages.append({"role": "user", "content": plan_prompt})
    messages[:] = trim_context(messages, max_tokens=client.num_ctx)

    plan_raw = _stream_reply(client, messages)
    print()
    messages.append({"role": _assistant_role(client), "content": plan_raw})
    logger.append("assistant", f"[PLAN]\n{plan_raw}")

    task = parse_plan(plan_raw, objective, mode=autonomy_mode)
    task_id = logger.session_id
    save_task(task, task_id)

    print(f"\n[PLAN] {len(task.steps)} step(s):")
    print(format_graph(task.steps, set(task.completed_step_ids)))

    # Visual task tree
    step_dicts = [
        {"id": s.id, "goal": s.goal, "depends_on": list(s.depends_on)}
        for s in task.steps
    ]
    print(f"\n{task_tree(step_dicts, set(task.completed_step_ids))}")

    # 2. Build topological tiers for parallel execution
    tiers = topo_tiers(task.steps)
    completed = set(task.completed_step_ids)
    results_log: list[str] = []
    abort = False

    def _execute_single_step(step: AgentStep) -> StepOutcome:
        """Execute + verify a single step. Thread-safe for parallel tiers."""
        import threading
        # Each thread gets its own message list copy to avoid cross-contamination
        step_messages = list(messages)

        safe_print(f"\n{'='*50}")
        safe_print(f"[STEP {step.id}] {step.goal}")
        deps_label = f" (after: {', '.join(step.depends_on)})" if step.depends_on else ""
        safe_print(f"[CRITERIA] {step.success_criteria}{deps_label}")
        safe_print("=" * 50)

        step_prompt = build_step_prompt(step, registry.describe())
        step_reply = _run_turn(
            client, step_messages, logger, rlog, step_prompt, registry, autonomy_mode
        )

        # Verify
        rlog.event("verify_start", step=step.id)
        verify_prompt = build_verify_prompt(step.goal, step.success_criteria, step_reply)
        step_messages.append({"role": "user", "content": verify_prompt})
        step_messages[:] = trim_context(step_messages, max_tokens=client.num_ctx)

        verify_raw = _stream_reply(client, step_messages)
        safe_print()
        step_messages.append({"role": _assistant_role(client), "content": verify_raw})

        passed, reason = parse_verdict(verify_raw)
        status = "PASSED" if passed else "FAILED"
        safe_print(f"\n[VERIFY {status}] {step.id}: {reason}")
        rlog.event("verify_done", step=step.id, passed=passed, reason=reason)
        logger.append("system", f"[VERIFY {status}] {step.id}: {reason}")

        return StepOutcome(step=step, reply=step_reply, passed=passed, reason=reason)

    for tier_idx, tier in enumerate(tiers):
        if abort:
            break

        # Filter out already-completed steps (from checkpoint resume)
        pending = [s for s in tier if s.id not in completed]
        if not pending:
            continue

        if len(pending) > 1:
            safe_print(f"\n[TIER {tier_idx + 1}] Running {len(pending)} steps in parallel...")

        outcomes = run_tier_parallel(pending, _execute_single_step)

        for outcome in outcomes:
            results_log.append(f"[{outcome.step.id}] {outcome.reply[:500]}")

            if outcome.passed:
                completed.add(outcome.step.id)
                task.completed_step_ids.append(outcome.step.id)
                task.artifacts.append(f"{outcome.step.id}: {outcome.reason}")
                save_task(task, task_id)

                # ── Context seaming ────────────────────────────
                # Compress the completed step into working memory
                # so the next step starts with a lean context
                # instead of dragging the full conversation forward.
                step_summary = compress_step_result(
                    outcome.step.id, outcome.step.goal,
                    outcome.reply, outcome.passed,
                )
                working_memory.append(step_summary)
            else:
                safe_print(f"[STEP FAILED] {outcome.step.id} — stopping agent loop.")
                rlog.event("agent_step_failed", step=outcome.step.id, reason=outcome.reason)
                abort = True
                break

        # After each tier, trim the main message list so it doesn't
        # balloon across tiers.  reconstruct_context in _run_turn
        # will pull the compressed steps back via working memory.
        if not abort:
            messages[:] = trim_context(messages, max_tokens=client.num_ctx)

    # Summary
    done = len(task.completed_step_ids)
    total = len(task.steps)
    summary = f"\n[AGENT COMPLETE] {done}/{total} steps done. Task: {task_id}"
    print(summary)
    print(status_panel(task.objective[:50], done, total))
    rlog.event("agent_complete", done=done, total=total, task_id=task_id)
    logger.append("system", summary)

    # Auto-generate HTML report
    try:
        step_dicts = [
            {"id": s.id, "goal": s.goal, "result": ""}
            for s in task.steps
        ]
        report_path = generate_task_report(
            task_name=task.objective[:60],
            steps=step_dicts,
            completed=completed,
            stats={"task_id": task_id, "steps_done": done,
                   "steps_total": total},
        )
        print(f"[REPORT] HTML report: {report_path}")
    except Exception:
        pass  # Non-critical — don't fail the task over a report

    return summary


# ── Quick build (preserved from version-1.0) ────────────────────────


def _handle_quick_build(user_message: str, registry: ToolRegistry, logger: SessionLogger) -> bool:
    lowered = user_message.strip().lower()
    if not lowered.startswith("build "):
        return False
    target = user_message.strip()[6:].strip()
    if target.endswith(" now"):
        target = target[:-4].strip()
    if not target:
        print("J.: Please provide a project name, e.g. 'build starter_agent now'.")
        return True
    result = registry.execute("run_scaffold", [target])
    print(f"J.: {result}")
    logger.append("assistant", f"[QUICK BUILD] {result}")
    return True


# ── Main loop ────────────────────────────────────────────────────────


def run_chat(
    initial_message: str | None = None,
    runtime_state: dict | None = None,
    autonomy_mode: str = "semi",
) -> None:

    if runtime_state is None:
        runtime_state = {"sandbox_enabled": False}

    client = create_client()
    logger = SessionLogger(model=f"{client.backend}:{client.model}")
    rlog = RuntimeJsonLogger(session_id=logger.session_id)
    registry = ToolRegistry(BASE_DIR)
    messages = build_history(client)
    local_server = LocalLlamaServer(client)

    try:
        rlog.event("startup", backend=client.backend, model=client.model, mode=autonomy_mode)
        local_server.ensure_started()

        # ── Diagnostic: confirm system prompt is loaded ──
        sys_content = messages[0].get("content", "") if messages else ""
        sys_tokens = max(1, len(sys_content) // 4)
        budget = max(256, client.num_ctx - client.num_predict)

        print(f"--- SOVEREIGN SHARD ONLINE [{logger.session_id}] ---")
        print(f"Backend: {client.backend}")
        print(f"Model:   {client.model}")
        print(f"Mode:    {autonomy_mode}")
        print(f"Context: {client.num_ctx} tokens (budget {budget}, system ~{sys_tokens})")
        if sys_content:
            # Show first 60 chars so user can verify the right prompt loaded
            preview = sys_content[:60].replace("\n", " ")
            print(f"Prompt:  {preview}...")
        else:
            print("⚠ WARNING: System prompt is EMPTY — J-system.txt may be missing!")
        print("Commands: quit, exit, /help, /tools, /plan, /model, /mode, /memory, /snapshot, /sandbox, /refactor, /optimize, /report")
        if client.backend == "llama_cpp":
            print(f"Server log: {local_server.log_path}")

        if initial_message:
            print("\nJ.: ", end="", flush=True)
            _run_turn(client, messages, logger, rlog, initial_message, registry, autonomy_mode)
            return

        while True:
            user_message = input("\nYou: ").strip()

            if user_message.lower() in {"quit", "exit"}:
                print(f"Session saved to {logger.transcript_path}")
                rlog.event("shutdown", reason="user_exit")
                break

            if not user_message:
                continue

            if user_message == "/help":
                print(
                    "Commands:\n"
                    "  quit / exit      — end session\n"
                    "  /snapshot        — show hardware snapshot\n"
                    "  /tools           — list available tools\n"
                    "  /plan <goal>     — enter agent mode (plan → execute → verify)\n"
                    "  /index           — index the project directory\n"
                    "  /mode <level>    — change autonomy (manual/semi/auto-safe/auto-full)\n"
                    "  /model <name>    — hot-swap the model (e.g. /model gemma4:e2b)\n"
                    "  /memory          — show recent working memory entries\n"
                    "  /reflect         — manually compress working memory\n"
                    "  /integrity       — check file integrity against baseline\n"
                    "  /refactor        — cross-file AST analysis (dead code, circles, shadows)\n"
                    "  /optimize [path] — Five Masters code optimizer (deterministic + LLM)\n"
                    "  /report          — generate HTML task report (opens in browser)\n"
                    "  /sandbox         — run pre-push validation (syntax, parse, tests, quality)\n"
                    "  build <name>     — quick-scaffold a package\n"
                    "  bruce wayne      — toggle sandbox"
                )
                continue

            if user_message == "/tools":
                print(registry.describe())
                continue

            if user_message == "/snapshot":
                snapshot = dumps(get_system_snapshot(), indent=2)
                print(snapshot)
                logger.append("system", snapshot)
                rlog.event("snapshot")
                continue

            if user_message == "/index":
                from app.agent.indexer import save_index
                path = save_index(str(BASE_DIR))
                print(f"[INDEX OK] Saved to {path}")
                rlog.event("index_saved", path=path)
                continue

            if user_message.startswith("/mode "):
                new_mode = user_message[6:].strip()
                if new_mode in ("manual", "semi", "auto-safe", "auto-full"):
                    autonomy_mode = new_mode
                    print(f"[MODE] Autonomy set to: {autonomy_mode}")
                    rlog.event("mode_change", mode=autonomy_mode)
                else:
                    print("[MODE ERROR] Valid modes: manual, semi, auto-safe, auto-full")
                continue

            if user_message.startswith("/model "):
                new_model = user_message[7:].strip()
                if new_model:
                    # Rebuild client with new model name
                    import os
                    os.environ["LLAMA_MODEL_ALIAS"] = new_model
                    os.environ["OLLAMA_MODEL"] = new_model
                    client = create_client()
                    messages = build_history(client)
                    print(f"[MODEL] Switched to: {new_model}")
                    print(f"  Backend: {client.backend}")
                    print(f"  Context: {client.num_ctx} tokens")
                    print("  Note: conversation history reset. Memory persists.")
                    rlog.event("model_swap", model=new_model)
                else:
                    print(f"[MODEL] Current: {client.model}")
                    print("Usage: /model <name>  (e.g. /model gemma4:e2b)")
                continue

            if user_message == "/model":
                print(f"[MODEL] Current: {client.model}")
                print("Usage: /model <name>  (e.g. /model qwen2.5-coder:14b, /model gemma4:e2b)")
                continue

            if user_message == "/memory":
                entries = working_memory.read_recent(10)
                if entries:
                    print(working_memory.format_for_context(entries))
                    sz = working_memory.size_bytes()
                    print(f"\n[{sz:,} bytes — reflection {'PENDING' if should_reflect() else 'not needed'}]")
                else:
                    print("[WORKING MEMORY] Empty.")
                continue

            if user_message == "/reflect":
                if not working_memory.read_all():
                    print("[REFLECT] Working memory is empty.")
                    continue
                entries = working_memory.read_all()
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
                    print(f"[REFLECT OK] {len(entries)} → {len(consolidated)} entries")
                else:
                    print("[REFLECT FAIL] Could not parse; memory unchanged.")
                continue

            if user_message == "/integrity":
                result = registry.execute("run_integrity", [])
                print(result)
                rlog.event("integrity_check")
                continue

            if user_message == "/integrity --baseline":
                result = registry.execute("run_integrity", ["--baseline"])
                print(result)
                rlog.event("integrity_baseline")
                continue

            if user_message == "/sandbox":
                print("\n[SANDBOX] Running full pre-push validation...\n")
                try:
                    report = validate_before_push(
                        project_dir=str(Path.cwd()),
                        copy_to_temp=True,
                    )
                    print(report.summary())
                except Exception as exc:
                    print(f"[SANDBOX ERROR] {exc}")
                rlog.event("sandbox_validation")
                continue

            if user_message.startswith("/optimize"):
                parts = user_message.split(maxsplit=1)
                target = parts[1].strip() if len(parts) > 1 else str(Path.cwd())
                dry_run = "--dry-run" in target
                no_model = "--no-model" in target
                show_diff = "--diff" in target
                target = target.replace("--dry-run", "").replace("--no-model", "").replace("--diff", "").strip()
                if not target:
                    target = str(Path.cwd())

                print(f"\n[OPTIMIZE] Five Masters Code Optimizer")
                print(f"  Target: {target}")
                if dry_run:
                    print("  Mode: dry-run (report only)")
                if no_model:
                    print("  Mode: deterministic only (no LLM)")

                try:
                    from app.agent.optimizer import optimize_file, optimize_directory, batch_summary
                    target_path = Path(target).resolve()
                    if target_path.is_file():
                        result = optimize_file(
                            str(target_path),
                            dry_run=dry_run,
                            use_model=not no_model,
                        )
                        print(result.summary())
                        if show_diff and not result.reverted:
                            d = result.diff()
                            if d:
                                print(f"\n{d}")
                        if not dry_run and not result.reverted:
                            if result.optimized_source != result.original_source:
                                target_path.write_text(result.optimized_source, encoding="utf-8")
                                print(f"\n  ✓ Written to {target_path}")
                    elif target_path.is_dir():
                        results = optimize_directory(
                            str(target_path),
                            dry_run=dry_run,
                            use_model=not no_model,
                        )
                        print(batch_summary(results))
                        if not dry_run:
                            written = 0
                            for r in results:
                                if not r.reverted and r.optimized_source != r.original_source:
                                    fpath = target_path / r.file_path
                                    if fpath.is_file():
                                        fpath.write_text(r.optimized_source, encoding="utf-8")
                                        written += 1
                            if written:
                                print(f"\n  ✓ {written} file(s) updated")
                    else:
                        print(f"  ✗ Not found: {target}")
                except Exception as exc:
                    print(f"[OPTIMIZE ERROR] {exc}")
                rlog.event("optimize")
                continue

            if user_message == "/refactor":
                print("\n[REFACTOR] Scanning project for cross-file issues...")
                try:
                    pmap = scan_project(str(Path.cwd()))
                    print(pmap.summary())
                    if pmap.issues:
                        from app.agent.visual import generate_refactor_report
                        issues_data = [
                            {"kind": i.kind, "file": i.file, "line": i.line,
                             "message": i.message, "severity": i.severity}
                            for i in pmap.issues
                        ]
                        path = generate_refactor_report(pmap.summary(), issues_data)
                        print(f"\n[REPORT] HTML report saved: {path}")
                except Exception as exc:
                    print(f"[REFACTOR ERROR] {exc}")
                rlog.event("refactor_scan")
                continue

            if user_message == "/report":
                print("\n[REPORT] Generating HTML task report...")
                try:
                    report_path = generate_task_report(
                        task_name="Session Report",
                        steps=[],
                        completed=set(),
                        stats={"session": logger.session_id,
                               "turns": len(messages)},
                    )
                    print(f"[REPORT] Saved: {report_path}")
                except Exception as exc:
                    print(f"[REPORT ERROR] {exc}")
                rlog.event("report_generated")
                continue

            if user_message.startswith("/plan "):
                objective = user_message[6:].strip()
                if objective:
                    _run_agent_task(
                        client, messages, logger, rlog, registry, objective, autonomy_mode
                    )
                else:
                    print("Usage: /plan <describe your goal>")
                continue

            if _handle_quick_build(user_message, registry, logger):
                continue

            # Sandbox toggle
            if user_message.lower() == "bruce wayne":
                runtime_state["sandbox_enabled"] = True
                print("\n[SANDBOX ENABLED]")
                continue

            if runtime_state.get("sandbox_enabled"):
                user_message = f"[SANDBOX] {user_message}"

            # ── Fast Router: intercept direct commands before LLM ──
            route_result = fast_route(user_message, registry)
            if route_result.handled:
                print(f"\n[{route_result.tool_name}] {route_result.output}")
                logger.append("system", f"[ROUTED] {route_result.tool_name}: {route_result.output[:500]}")
                rlog.event("fast_route", tool=route_result.tool_name)
                wm_entry = working_memory.compress_turn(user_message, route_result.output)
                working_memory.append(**wm_entry)
                continue

            try:
                print("\nJ.: ", end="", flush=True)
                _run_turn(
                    client, messages, logger, rlog, user_message, registry, autonomy_mode
                )
                # Weight-triggered reflection
                if should_reflect():
                    entries = working_memory.read_all()
                    print(f"\n[AUTO-REFLECT] Working memory over threshold "
                          f"({working_memory.size_bytes():,} bytes, "
                          f"{len(entries)} entries). Compressing...")
                    rprompt = build_reflect_prompt(entries)
                    messages.append({"role": "user", "content": rprompt})
                    messages[:] = trim_context(messages, max_tokens=client.num_ctx)
                    raw = _stream_reply(client, messages)
                    print()
                    messages.append({"role": _assistant_role(client), "content": raw})
                    consolidated = parse_reflected(raw)
                    if consolidated:
                        apply_reflection(consolidated)
                        print(f"[AUTO-REFLECT OK] {len(entries)} → {len(consolidated)}")
                        rlog.event("reflection", before=len(entries), after=len(consolidated))
                    else:
                        print("[AUTO-REFLECT FAIL] Parse error; memory unchanged.")
            except TransportError as error:
                print(f"\nJ. Error: {error}")
                logger.append("error", str(error))
                rlog.event("error", code=error.code, message=error.message)

    finally:
        local_server.stop()
