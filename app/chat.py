"""Chat loop for the Sovereign Shard developer agent.

Preserves the original version-1.0 interactive loop and streaming.
Adds: RuntimeJsonLogger, TransportError, agent planner/executor/verifier,
context trimming, autonomy modes, and the full dev-tool suite.
"""

from __future__ import annotations

import ast
import os
import re
import time
from json import JSONDecodeError, dumps, loads
from pathlib import Path
from urllib.request import Request, urlopen

from app.agent import ToolRegistry, working_memory
from app import personality as persona
from app import ui
from app.agent import task_buffer
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
RETRY_MARGIN = 5  # extra loop iterations for retries / validation errors
MAX_TOOL_BUDGET = int(os.getenv("J_TOOL_BUDGET", "3"))  # approved calls per turn
MAX_TOOL_OUTPUT_LINES = 60  # truncate tool output to protect 2048 context
PHASE_SIZE = 4  # compress context every N tool calls (keeps 7B models on track)

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


def _balanced_json(text: str, start: int) -> str | None:
    """Extract the first balanced JSON object from *text* starting at *start*.

    Counts braces outside of string literals so nested objects (e.g.
    run_str_replace payloads) are handled correctly.  Returns ``None``
    if no balanced object is found.
    """
    depth = 0
    in_string = False
    escape_next = False
    for i in range(start, len(text)):
        ch = text[i]
        if escape_next:
            escape_next = False
            continue
        if ch == "\\" and in_string:
            escape_next = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


def _extract_action(content: str) -> dict | None:
    """Parse an ACTION payload from the model response.

    Handles three formats J may produce:
      1. ACTION:{"tool": "...", "args": [...]}     (standard JSON)
      2. ACTION:tool_name arg1 arg2                (bare / no-JSON)
      3. ACTION:{...} [TOOL EXECUTION] ...         (hallucinated tail)
    """
    if "ACTION:" not in content:
        return None

    payload = content.split("ACTION:", 1)[1].strip()
    if not payload:
        return None

    # Strip hallucinated [TOOL …] blocks that J sometimes appends
    for marker in ("[TOOL EXECUTION]", "[TOOL"):
        idx = payload.find(marker)
        if idx > 0:
            payload = payload[:idx].rstrip()

    # ── 1. Try balanced-brace JSON extraction ───────────────────────
    brace = payload.find("{")
    if brace != -1:
        json_str = _balanced_json(payload, brace)
        if json_str:
            try:
                return loads(json_str)
            except JSONDecodeError:
                try:
                    return ast.literal_eval(json_str)
                except Exception:
                    pass

    # ── 2. Fallback: ACTION:tool_name arg1 arg2 (no JSON wrapper) ──
    parts = payload.split(None, 1)
    if parts and re.match(r"^[a-z_][a-z0-9_]*$", parts[0]):
        tool = parts[0]
        rest = parts[1].strip() if len(parts) > 1 else ""
        args = rest.split() if rest else []
        return {"tool": tool, "args": args}

    return None


def _truncate_tool_output(output: str, max_lines: int = MAX_TOOL_OUTPUT_LINES) -> str:
    """Truncate large tool output to protect the 2048 context window.

    Keeps the first and last lines so J sees structure and end-state,
    with a hint to use run_search for specifics.
    """
    lines = output.splitlines(keepends=True)
    if len(lines) <= max_lines:
        return output
    head_n = max_lines - 5  # most context at the top
    tail_n = 5
    head = "".join(lines[:head_n])
    tail = "".join(lines[-tail_n:])
    omitted = len(lines) - head_n - tail_n
    return (
        f"{head}"
        f"\n[... {omitted} lines omitted — use run_search to find specific content ...]\n"
        f"{tail}"
    )


def _execute_tool(action: dict, registry: ToolRegistry) -> str:
    tool_name = action.get("tool")
    tool_args = action.get("args", [])

    if not tool_name:
        return "[TOOL ERROR] Tool name is missing."
    if not isinstance(tool_args, list):
        return "[TOOL ERROR] Tool args must be a list."

    # Strip wrapping quotes from string args — J often double-quotes
    # patterns like run_search "circuit_breaker" which JSON-parses as
    # the literal string "circuit_breaker" (with quotes), missing all hits.
    tool_args = [
        a[1:-1]
        if isinstance(a, str) and len(a) >= 2
        and a[0] == a[-1] and a[0] in ('"', "'")
        else a
        for a in tool_args
    ]

    result = registry.execute(tool_name, tool_args)
    return _truncate_tool_output(result)


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
            "repeat_penalty": client.repeat_penalty,
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
        "repeat_penalty": client.repeat_penalty,
        "frequency_penalty": client.repeat_penalty - 1.0,
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
        print(f"\n{ui.warn_tag(persona.language_drift())}")
        print(f"  System prompt: ~{sys_tokens} tokens | Budget: {budget} tokens")


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
        result = persona.strip_bleed("".join(reply_chunks))
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
        full_reply = persona.strip_bleed(full_reply)
        _check_language_drift(full_reply, messages, client)
        return full_reply


# ── Auto-reflection ─────────────────────────────────────────────────


def _maybe_auto_reflect(
    client: "RuntimeConfig",
    messages: list[dict[str, str]],
    logger: "SessionLogger",
) -> None:
    """Fire reflection automatically when working memory exceeds 32KB.

    Same logic as the /reflect command, but triggered after every turn.
    Keeps working memory bounded without manual intervention.
    """
    if not should_reflect():
        return
    entries = working_memory.read_all()
    if not entries:
        return
    print(f"\n{ui.stark_blue(persona.reflect_start(len(entries), working_memory.size_bytes()))}")
    rprompt = build_reflect_prompt(entries)
    messages.append({"role": "user", "content": rprompt})
    messages[:] = trim_context(messages, max_tokens=client.num_ctx)
    raw = _stream_reply(client, messages)
    print()
    assistant_role = _assistant_role(client)
    messages.append({"role": assistant_role, "content": raw})
    consolidated = parse_reflected(raw)
    if consolidated:
        apply_reflection(consolidated)
        print(ui.stark_blue(persona.reflect_done(len(entries), len(consolidated))))
    else:
        print(ui.error_tag(persona.reflect_failed()))


# ── Turn execution ──────────────────────────────────────────────────


def _run_turn(
    client: RuntimeConfig,
    messages: list[dict[str, str]],
    logger: SessionLogger,
    rlog: RuntimeJsonLogger,
    user_message: str,
    registry: ToolRegistry,
    autonomy_mode: str = "semi",
    tool_budget: int = MAX_TOOL_BUDGET,
) -> str:

    rlog.event("stage_start", stage="input")
    messages.append({"role": "user", "content": user_message})
    logger.append("user", user_message)

    # Tier 1: reconstruct active context (pulls working + long-term memory)
    # On small context windows (≤2048) memory injection costs more than
    # it's worth — J can run_search memory files when needed instead.
    if client.num_ctx > 2048:
        messages[:] = reconstruct_context(
            messages, task_hint=user_message, max_tokens=client.num_ctx,
        )
    else:
        messages[:] = trim_context(messages, max_tokens=client.num_ctx)

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
    turn_tool_calls = 0  # per-turn counter (not cumulative across turns)
    turn_tool_log: list[str] = []  # breadcrumb trail of completed calls
    max_hops = tool_budget + RETRY_MARGIN  # scale loop with budget
    for hop in range(max_hops):
        action = _extract_action(reply)
        if action is None:
            # Budget-aware answer detection:
            # - budget=0 (pure chat): accept any non-stub answer
            # - budget>=1 but tools already used: J answered after using tools — accept
            # - budget>=1 and no tools used yet: retry — J should use a tool
            stripped_reply = reply.strip()
            # Accept the answer if:
            #   a) budget=0 (router said no tool needed), OR
            #   b) J already used at least one tool this turn (task done, now answering)
            # Only reject pure stubs: empty, just "Understood", or ACTION leftovers.
            is_chat_answer = (
                (tool_budget == 0 or turn_tool_calls > 0)
                and len(stripped_reply) > 0
                and stripped_reply.lower() not in ("understood", "understood.")
                and "ACTION:" not in stripped_reply
            )
            if is_chat_answer or action_retries >= MAX_ACTION_RETRIES:
                break
            messages.append({"role": "user", "content": ACTION_RETRY_PROMPT})
            logger.append("user", ACTION_RETRY_PROMPT)
            action_retries += 1
            reply = _stream_reply(client, messages)
            print()
            messages.append({"role": assistant_role, "content": reply})
            logger.append("assistant", reply)
            continue

        validation_error = validate_action_payload(action, registry)
        if validation_error is not None:
            messages.append({"role": "user", "content": validation_error})
            logger.append("system", validation_error)
            continue

        tool_name = action.get("tool", "")
        tool_args = str(action.get("args", []))
        # Pre-compute call signature for dedup + breadcrumbs
        call_args_str = " ".join(str(a) for a in action.get("args", []))
        current_call_sig = f"{tool_name} {call_args_str}".strip()

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

        # ── Dedup guard: skip exact duplicate tool calls ────────
        # If J already made this exact call (same tool + same args),
        # don't execute again — redirect immediately.  This prevents
        # the 7B model from re-reading the same file 4x in a row.
        if current_call_sig in turn_tool_log:
            done_list = "\n".join(
                f"  ✓ {c}" for c in dict.fromkeys(turn_tool_log)
            )
            skip_msg = (
                f"[DUPLICATE SKIPPED] Already called: {current_call_sig}\n"
                f"Completed so far:\n{done_list}\n"
                "Pick a DIFFERENT file or tool you have NOT used yet."
            )
            print(f"\n🔁 Dedup skip: {current_call_sig}")
            messages.append({"role": "user", "content": skip_msg})
            logger.append("system", skip_msg)
            breaker.record_turn(
                tool=tool_name, args=tool_args,
                output="[DUPLICATE SKIPPED]", is_error=True,
            )
            reply = _stream_reply(client, messages)
            print()
            messages.append({"role": assistant_role, "content": reply})
            logger.append("assistant", reply)
            continue

        # Autonomy gate
        if needs_confirmation(tool_name, registry, autonomy_mode):
            effect = registry.get_side_effect(tool_name)
            print(f"\n⚠ {persona.tool_confirm(tool_name, effect)}")
            print(f"  Args: {action.get('args', [])}")
            confirm = input("  Approve? (y/n): ").strip().lower()
            if confirm != "y":
                tool_result = f"[TOOL BLOCKED] {persona.tool_blocked(tool_name)}"
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

        # ── Tool budget tracking (per-turn, not cumulative) ─────────
        turn_tool_calls += 1
        remaining = tool_budget - turn_tool_calls

        # Log this call for the breadcrumb trail (call_args_str computed earlier)
        turn_tool_log.append(current_call_sig)

        # ── Error-aware nudge: tell J what went wrong so it can fix args ──
        error_hint = ""
        if is_error and remaining > 0:
            error_hint = f" Your last tool call FAILED: {tool_result[:200]}. Fix the arguments and try again."

        # ── Breadcrumb: remind J what it already did (prevents re-reads) ──
        breadcrumb = ""
        if tool_budget > 3 and len(turn_tool_log) >= 2:
            breadcrumb = " Already done: " + ", ".join(turn_tool_log) + "."
            # Anchor J to the original task so it doesn't veer off-plan
            task_hint = user_message[:300].rstrip()
            if len(user_message) > 300:
                task_hint += "..."
            breadcrumb += f" Original task: {task_hint}"

        if remaining <= 0:
            # Budget spent — force answer, no more tools
            continuation = (
                f"[ACTION COMPLETE — {tool_budget}/{tool_budget} tool calls used] "
                "Respond to the user now. Do not call another tool."
            )
        elif remaining == 1:
            continuation = (
                f"[{turn_tool_calls}/{tool_budget} tool calls used, 1 remaining] "
                "Continue." + error_hint + breadcrumb
                + (" You may call one more tool if needed, then respond." if not error_hint else "")
            )
        else:
            continuation = (
                f"[{turn_tool_calls}/{tool_budget} tool calls used, {remaining} remaining] "
                "Continue." + error_hint + breadcrumb
                + (" Call another tool if needed, or respond to the user." if not error_hint else "")
            )

        messages.append({"role": "user", "content": continuation})
        logger.append("user", continuation)

        # ── Phase break: compress context at phase boundaries ──────
        # Every PHASE_SIZE calls on high-budget tasks, replace verbose
        # tool outputs with a compact summary.  This frees context
        # window for the 7B model so it can stay coherent across many
        # steps instead of losing the plot after 3-4 calls.
        if (tool_budget > PHASE_SIZE
                and turn_tool_calls >= PHASE_SIZE
                and turn_tool_calls % PHASE_SIZE == 0
                and remaining > 0):
            phase_num = turn_tool_calls // PHASE_SIZE
            phase_summary = (
                f"[PHASE {phase_num} COMPLETE — starting phase {phase_num + 1}]\n"
                f"Original task: {user_message}\n\n"
                f"Completed ({turn_tool_calls}/{tool_budget} calls): "
                + ", ".join(turn_tool_log) + ".\n\n"
                f"Continue with the NEXT step. Do NOT repeat any call listed above. "
                f"You have {remaining} calls remaining."
            )
            system_msgs = [m for m in messages if m.get("role") == "system"]
            messages.clear()
            messages.extend(system_msgs)
            messages.append({"role": "user", "content": phase_summary})
            logger.append("system", f"[Phase {phase_num} context compression]")

        time.sleep(PROCESS_PAUSE_SECONDS)
        reply = _stream_reply(client, messages)
        print()

        # ── Post-generation trim: strip runaway tool calls ─────────
        # If budget is spent and J still generates an ACTION:, or if
        # J answered and then tacked on a second ACTION:, trim it
        # and BREAK — do not let the retry logic re-prompt.
        if remaining <= 0:
            if "ACTION:" in reply:
                answer_part = reply.split("ACTION:", 1)[0].rstrip()
                if len(answer_part) > 20:
                    reply = answer_part
                else:
                    reply = f"[STOPPED] {persona.tool_budget_exhausted()}"
            messages.append({"role": assistant_role, "content": reply})
            logger.append("assistant", reply)
            break  # budget spent — exit the tool loop

        messages.append({"role": assistant_role, "content": reply})
        logger.append("assistant", reply)

    rlog.event("turn_complete", chars=len(reply))

    # Tier 2: compress this turn into working memory
    wm_entry = working_memory.compress_turn(user_message, reply)
    working_memory.append(**wm_entry)
    _maybe_auto_reflect(client, messages, logger)

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
    print(f"\n{ui.red('[PLANNING]')} {ui.gold(persona.planning_start())}")
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

    print(f"\n{ui.red('[PLAN]')} {ui.gold(persona.plan_parsed(len(task.steps)))}")
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

        deps_label = f" (after: {', '.join(step.depends_on)})" if step.depends_on else ""
        safe_print(ui.step_header(step.id, step.goal, step.success_criteria, deps_label))

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
        _vfn = persona.verify_pass if passed else persona.verify_fail
        safe_print(f"\n{_vfn(step.id, reason)}")
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
            safe_print(f"\n{persona.tier_start(tier_idx + 1, len(pending))}")

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
                working_memory.append(outcome.step.id, step_summary)
            else:
                safe_print(persona.step_failed(outcome.step.id))
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
    summary = f"\n{persona.agent_complete(done, total, task_id)}"
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
        print(persona.report_saved(report_path))
    except Exception:
        pass  # Non-critical — don't fail the task over a report

    return summary


# ── Buffer-based plan/execute (7B-friendly) ─────────────────────────


def _run_buffer_plan(
    client: RuntimeConfig,
    messages: list[dict[str, str]],
    logger: SessionLogger,
    rlog: RuntimeJsonLogger,
    registry: ToolRegistry,
    objective: str,
    autonomy_mode: str = "semi",
    skip_planning: bool = False,
) -> str:
    """Lightweight plan → execute flow using the file-based task buffer.

    Designed for small context windows (≤2048 tokens):
    1. PLAN phase: J outputs numbered steps (1 inference, plan_mode prefix)
    2. Parse steps → write to task_buffer.jsonl (0 inference)
    3. EXECUTE phase: for each step, inject ONLY the step goal → run 1-2 tools
    4. SUMMARY phase: inject buffer summary → J summarizes (1 inference)

    Key difference from _run_agent_task: each step gets a CLEAN context
    (system prompt + step only), and plans live on disk not in context.
    """
    rlog.event("buffer_plan_start", objective=objective)

    # ── Phase 1: PLAN — get J to output numbered steps ──────────
    # Skip if steps were already loaded into the buffer (e.g. /steps command)
    if skip_planning and task_buffer.pending_count() > 0:
        print(f"\n{ui.red('[BUFFER]')} {ui.gold(persona.buffer_executing())}")
        print(task_buffer.summary())
    else:
        # ── Pre-check: does the objective already contain numbered steps? ──
        user_steps = task_buffer.parse_numbered_plan(objective)
        if len(user_steps) >= 2:
            # User provided explicit steps — skip LLM planning entirely
            print(f"\n{ui.red('[PLAN]')} {ui.gold(persona.plan_detected_steps())}")
            steps = user_steps
        else:
            plan_prefix = ""
            try:
                plan_prefix = (PROMPTS_DIR / "plan_mode.txt").read_text(encoding="utf-8").strip()
            except OSError:
                plan_prefix = ("PLAN MODE: Break the task into numbered steps BEFORE acting.\n"
                               "Format:\n1. [step]\n2. [step]\n...\n"
                               "Do NOT call any tools yet. Just output the plan.")

            plan_prompt = f"{plan_prefix}\n\nObjective: {objective}"
            messages.append({"role": "user", "content": plan_prompt})
            messages[:] = trim_context(messages, max_tokens=client.num_ctx)

            print(f"\n{persona.plan_mode_start()}\n")
            print(ui.j_prefix(), end="", flush=True)
            plan_raw = _stream_reply(client, messages)
            print()
            messages.append({"role": _assistant_role(client), "content": plan_raw})
            logger.append("assistant", f"[PLAN]\n{plan_raw}")

            # Parse steps → buffer
            steps = task_buffer.parse_numbered_plan(plan_raw)
            if not steps:
                print(ui.warn_tag(persona.plan_fallback()))
                steps = [{
                    "id": "s1",
                    "goal": objective,
                    "depends": [],
                    "status": "pending",
                    "result": "",
                }]

        n_written = task_buffer.write_plan(steps)
        print(f"\n{ui.red('[BUFFER]')} {ui.gold(f'{n_written} step(s) queued:')}")
        print(task_buffer.summary())
        rlog.event("buffer_plan_parsed", steps=n_written)

    # ── Phase 2: EXECUTE — one step at a time, clean context ────
    exec_prefix = ""
    try:
        exec_prefix = (PROMPTS_DIR / "execute_mode.txt").read_text(encoding="utf-8").strip()
    except OSError:
        exec_prefix = ("EXECUTE MODE: You have a plan. Execute the current step now.\n"
                       "Call exactly ONE tool.")

    while True:
        step = task_buffer.next_step()
        if step is None:
            break

        step_id = step["id"]
        goal = step["goal"]
        print(f"\n{'='*50}")
        print(f"[STEP {step_id}] {goal}")
        print("=" * 50)

        # Build a FRESH message list — system + step prompt only
        step_messages = [
            {"role": _system_role(client), "content": SYSTEM_PROMPT},
        ]

        # Build the step prompt (DO NOT append here — _run_turn appends it)
        step_content = task_buffer.step_prompt(step)
        full_prompt = f"{exec_prefix}\n\n{step_content}"

        # Run the step through the normal turn machinery
        print(persona.exec_status(step_id, 2))
        print(ui.j_prefix(), end="", flush=True)
        try:
            step_reply = _run_turn(
                client, step_messages, logger, rlog,
                full_prompt, registry, autonomy_mode,
                tool_budget=2,  # max 2 tool calls per step
            )
        except TransportError as error:
            step_reply = f"[ERROR] {error}"

        # Check if the router handled the goal directly
        route_result = fast_route(goal, registry)
        if route_result.handled and not step_reply.strip():
            step_reply = route_result.output

        # Evaluate result
        is_error = any(m in step_reply for m in ("[TOOL ERROR]", "[ERROR]", "FAILED"))
        if is_error:
            task_buffer.mark_failed(step_id, step_reply[:200])
            print(f"\n{persona.step_failed(step_id)}")
            rlog.event("buffer_step_failed", step=step_id)
            # Don't abort — continue with independent steps
        else:
            result_summary = step_reply[:200].replace("\n", " ").strip()
            task_buffer.mark_done(step_id, result_summary)
            print(f"\n{persona.step_done(step_id)}")
            rlog.event("buffer_step_done", step=step_id)

        # Compress into working memory for cross-step recall
        wm_entry = working_memory.compress_turn(goal, step_reply)
        working_memory.append(**wm_entry)
        _maybe_auto_reflect(client, messages, logger)

    # ── Phase 4: SUMMARY ────────────────────────────────────────
    buf_summary = task_buffer.summary()
    done = task_buffer.done_count()
    total = len(task_buffer.read_all())
    failed = task_buffer.failed_count()

    print(f"\n{'='*50}")
    print(persona.plan_complete(done, total, failed))
    print("=" * 50)
    print(f"\n{buf_summary}")

    # Ask J for a final summary (1 inference)
    summary_messages = [
        {"role": _system_role(client), "content": SYSTEM_PROMPT},
        {"role": "user", "content": (
            f"You just completed a multi-step task. Here are the results:\n\n"
            f"{buf_summary}\n\n"
            f"Summarize what was accomplished in 2-3 sentences."
        )},
    ]
    print(ui.j_stream_start(), end="", flush=True)
    final_summary = _stream_reply(client, summary_messages)
    print()
    logger.append("assistant", f"[PLAN SUMMARY]\n{final_summary}")
    rlog.event("buffer_plan_complete", done=done, total=total, failed=failed)

    # Clean up buffer
    task_buffer.clear()

    return final_summary


# ── Quick build (preserved from version-1.0) ────────────────────────


def _handle_quick_build(user_message: str, registry: ToolRegistry, logger: SessionLogger) -> bool:
    """Intercept short 'build <name>' commands → run_scaffold.

    Only fires for simple project names (1-3 words, no punctuation that
    signals a complex instruction).  Multi-step prompts that happen to
    start with 'Build' are left for the LLM/agent loop.
    """
    lowered = user_message.strip().lower()
    if not lowered.startswith("build "):
        return False
    target = user_message.strip()[6:].strip()
    if target.endswith(" now"):
        target = target[:-4].strip()
    if not target:
        print(f"{ui.j_prefix()}Please provide a project name, e.g. 'build starter_agent now'.")
        return True
    # Complex instruction guard: if the target contains sentence-like
    # punctuation or is more than 3 words, it's a task — not a scaffold.
    words = target.split()
    has_instruction_markers = any(c in target for c in ("—", ",", ".", ";", "then ", "\n"))
    if len(words) > 3 or has_instruction_markers:
        return False  # let the LLM/agent handle it
    result = registry.execute("run_scaffold", [target])
    print(f"{ui.j_prefix()}{result}")
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
    registry.restrictions["exec"] = True  # shard is local — exec tools are safe
    messages = build_history(client)
    local_server = LocalLlamaServer(client)

    try:
        rlog.event("startup", backend=client.backend, model=client.model, mode=autonomy_mode)
        local_server.ensure_started()

        # ── Diagnostic: confirm system prompt is loaded ──
        sys_content = messages[0].get("content", "") if messages else ""
        sys_tokens = max(1, len(sys_content) // 4)
        budget = max(256, client.num_ctx - client.num_predict)

        ui.init()  # Black background, clear screen

        prompt_preview = ""
        if sys_content:
            prompt_preview = sys_content[:60].replace("\n", " ")
        else:
            print(ui.warn_tag("System prompt is EMPTY — J-system.txt may be missing!"))

        print(ui.banner(
            session_id=logger.session_id,
            backend=client.backend,
            model=client.model,
            mode=autonomy_mode,
            num_ctx=client.num_ctx,
            sys_tokens=sys_tokens,
            budget=budget,
            prompt_preview=prompt_preview,
            server_log=str(local_server.log_path) if client.backend == "llama_cpp" else "",
        ))

        if initial_message:
            # Route through the fast router first (catches math, shell, etc.)
            route_result = fast_route(initial_message, registry)
            if route_result.handled:
                print(f"\n[{route_result.tool_name}] {route_result.output}")
                logger.append("system", f"[ROUTED] {route_result.tool_name}: {route_result.output[:500]}")
                rlog.event("fast_route", tool=route_result.tool_name)
            else:
                print(ui.j_stream_start(), end="", flush=True)
                _run_turn(client, messages, logger, rlog, initial_message, registry, autonomy_mode,
                          tool_budget=route_result.tool_budget)
            return

        while True:
            user_message = input(ui.you_prompt()).strip()

            if user_message.lower() in {"quit", "exit"}:
                print(ui.shutdown_msg(str(logger.transcript_path)))
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
                    "  /steps <steps>   — manual step injection (numbered or tool commands)\n"
                    "  /buffer          — show current task buffer state\n"
                    "  /buffer clear    — clear the task buffer\n"
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
                    print(persona.mode_changed(autonomy_mode))
                    rlog.event("mode_change", mode=autonomy_mode)
                else:
                    print(persona.mode_error())
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
                    print(persona.model_changed(new_model, client.backend, client.num_ctx))
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
                    print(persona.reflect_failed())
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
                        print(f"\n{persona.report_saved(path)}")
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
                    print(persona.report_saved(report_path))
                except Exception as exc:
                    print(f"[REPORT ERROR] {exc}")
                rlog.event("report_generated")
                continue

            if user_message.startswith("/plan "):
                objective = user_message[6:].strip()
                if objective:
                    # Small context (≤2048): use lightweight buffer-based flow
                    # Large context: use full agent task with DAG execution
                    if client.num_ctx <= 2048:
                        _run_buffer_plan(
                            client, messages, logger, rlog, registry, objective, autonomy_mode
                        )
                    else:
                        _run_agent_task(
                            client, messages, logger, rlog, registry, objective, autonomy_mode
                        )
                else:
                    print("Usage: /plan <describe your goal>")
                continue

            if user_message.startswith("/steps"):
                # Manual step injection — user provides numbered steps or
                # tool commands, J executes them one at a time.
                # Usage: /steps
                #   1. run_search should_reflect app/chat.py
                #   2. run_read app/chat.py
                #   3. Fix the bug on line 42
                body = user_message[6:].strip()
                if not body:
                    # Check if there's an existing buffer
                    if task_buffer.pending_count() > 0:
                        print(task_buffer.summary())
                    else:
                        print("Usage: /steps <numbered steps or tool commands>")
                        print("Example:")
                        print("  /steps")
                        print("  1. run_search should_reflect app/chat.py")
                        print("  2. run_read app/chat.py")
                        print("  3. Add auto-reflection after line 950")
                    continue
                # Try numbered steps first, then tool commands
                steps = task_buffer.parse_numbered_plan(body)
                if not steps:
                    steps = task_buffer.parse_tool_commands(body)
                if not steps:
                    print("[STEPS] Could not parse steps from input.")
                    continue
                n = task_buffer.write_plan(steps)
                print(f"[STEPS] {n} step(s) loaded into buffer.")
                print(task_buffer.summary())
                # Execute via buffer plan (skip LLM planning — user already provided steps)
                _run_buffer_plan(
                    client, messages, logger, rlog, registry,
                    "Execute user-provided steps", autonomy_mode,
                    skip_planning=True,
                )
                continue

            if user_message == "/buffer":
                # Show current task buffer state
                buf = task_buffer.read_all()
                if buf:
                    print(task_buffer.summary())
                else:
                    print("[TASK BUFFER] Empty.")
                continue

            if user_message == "/buffer clear":
                task_buffer.clear()
                print("[TASK BUFFER] Cleared.")
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
                _maybe_auto_reflect(client, messages, logger)
                # Inject a one-line breadcrumb into J's message history so
                # it can recall router-handled turns when asked.
                output_preview = route_result.output[:120].replace("\n", " ")
                breadcrumb = f"[SYSTEM] {route_result.tool_name} {' '.join(route_result.tool_args)}: {output_preview}"
                assistant_role = _assistant_role(client)
                messages.append({"role": "user", "content": user_message})
                messages.append({"role": assistant_role, "content": breadcrumb})
                continue

            try:
                budget = route_result.tool_budget
                print(ui.j_stream_start(), end="", flush=True)
                _run_turn(
                    client, messages, logger, rlog, user_message, registry, autonomy_mode,
                    tool_budget=budget,
                )
                # Weight-triggered reflection
                if should_reflect():
                    entries = working_memory.read_all()
                    print(f"\n{ui.stark_blue(persona.reflect_start(len(entries), working_memory.size_bytes()))}")
                    rprompt = build_reflect_prompt(entries)
                    messages.append({"role": "user", "content": rprompt})
                    messages[:] = trim_context(messages, max_tokens=client.num_ctx)
                    raw = _stream_reply(client, messages)
                    print()
                    messages.append({"role": _assistant_role(client), "content": raw})
                    consolidated = parse_reflected(raw)
                    if consolidated:
                        apply_reflection(consolidated)
                        print(ui.stark_blue(persona.reflect_done(len(entries), len(consolidated))))
                        rlog.event("reflection", before=len(entries), after=len(consolidated))
                    else:
                        print(ui.error_tag(persona.reflect_failed()))
            except TransportError as error:
                print(f"\n{ui.error_tag(f'J.: {error}')}")
                logger.append("error", str(error))
                rlog.event("error", code=error.code, message=error.message)

    finally:
        local_server.stop()
