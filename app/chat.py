"""Chat loop for the Sovereign Shard developer agent.

Preserves the original version-1.0 interactive loop and streaming.
Adds: RuntimeJsonLogger, TransportError, agent planner/executor/verifier,
context trimming, autonomy modes, and the full dev-tool suite.
"""

from __future__ import annotations

import os
import re
import time
from json import dumps, loads
from pathlib import Path

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
from app.agent.reflection import should_reflect, apply_reflection, compress_entries
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
from app.llm import stream_reply as _stream_reply
from app.action import extract_action as _extract_action, strip_identity_preamble as _strip_identity_preamble, truncate_tool_output as _truncate_tool_output, MAX_TOOL_OUTPUT_LINES
from app.tool_exec import execute_tool as _execute_tool, PROCESS_PAUSE_SECONDS
from core.fivemasters import evaluate_code
RETRY_MARGIN = 5  # extra loop iterations for retries / validation errors
MAX_TOOL_BUDGET = int(os.getenv("J_TOOL_BUDGET", "3"))  # approved calls per turn
CHAIN_LOG_PATH = Path(".j_chain.json")
MAX_CHAIN_TURNS = int(os.getenv("J_MAX_CHAIN_TURNS", "10"))
PHASE_SIZE = 4  # compress context every N tool calls (keeps 7B models on track)
DEDUP_CACHE: dict[str, str] = {}

BASE_DIR = Path(__file__).resolve().parent.parent
HOST_GGUF_PATH = r"C:\Jarvis\Models\manifests\registry.ollama.ai\library\gemma4\gemma.gguf"
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


# Extracted action parsing and streaming helpers are delegated to app.action,\n# app.tool_exec, and app.llm to keep app.chat focused on the agent loop.\n\n\n# ── Auto-reflection ─────────────────────────────────────────────────


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
    def _llm_reflect(prompt: str) -> str:
        messages.append({"role": "user", "content": prompt})
        messages[:] = trim_context(messages, max_tokens=client.num_ctx)
        raw = _stream_reply(client, messages)
        print()
        assistant_role = _assistant_role(client)
        messages.append({"role": assistant_role, "content": raw})
        return raw

    consolidated = compress_entries(entries, _llm_reflect)
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

    # Optional checklist anchor for "read each .py file in <dir>" tasks.
    pending_read_targets: list[str] = []
    checklist_match = re.search(
        r"read\s+each\s+\.py\s+file\s+in\s+([^\n\r]+)",
        user_message,
        re.IGNORECASE,
    )
    if checklist_match:
        target_dir = checklist_match.group(1).strip().strip(". ")
        dir_path = Path(target_dir)
        if dir_path.is_dir():
            pending_read_targets = [
                str(p.as_posix()) for p in sorted(dir_path.glob("*.py"))
            ]

    # Bounded tool loop with circuit breaker
    breaker = CircuitBreaker(tool_budget=tool_budget)
    action_retries = 0
    last_tool_error: str | None = None
    turn_tool_calls = 0  # per-turn counter (not cumulative across turns)
    turn_tool_log: list[str] = []  # breadcrumb trail of completed calls
    turn_tool_digests: list[str] = []  # brief output summaries per call
    max_hops = tool_budget + RETRY_MARGIN  # scale loop with budget
    for hop in range(max_hops):
        reply = _strip_identity_preamble(reply)
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
        effect = registry.get_side_effect(tool_name)
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
        if current_call_sig in DEDUP_CACHE:
            cached = DEDUP_CACHE[current_call_sig][:500]
            skip_msg = (
                f"[DUPLICATE — CACHED RESULT] {current_call_sig}\n"
                f"{cached}"
            )
            print(f"\n{persona.tool_narrate_dedup(current_call_sig)}")
            messages.append({"role": "user", "content": skip_msg})
            logger.append("system", skip_msg)
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
        DEDUP_CACHE[current_call_sig] = tool_result
        time.sleep(PROCESS_PAUSE_SECONDS)

        tool_response = (
            "[TOOL EXECUTION]\n"
            f"tool: {action.get('tool')}\n"
            f"args: {action.get('args', [])}\n"
            f"result:\n{tool_result}"
        )
        # User/transcript sees personality-voiced narration
        narration = persona.tool_narrate(tool_name, action.get("args", []), tool_result, is_error)
        print(f"\n{narration}\n")
        # Model gets the structured data (needs it for reasoning)
        messages.append({"role": assistant_role, "content": tool_response})
        # Transcript gets narration (clean read); raw data stays in rlog
        logger.append("assistant", narration)
        action_retries = 0

        # ── Tool budget tracking (per-turn, not cumulative) ─────────
        turn_tool_calls += 1
        remaining = tool_budget - turn_tool_calls

        # Log this call for the breadcrumb trail (call_args_str computed earlier)
        turn_tool_log.append(current_call_sig)
        if tool_name == "run_read" and action.get("args"):
            read_target = str(action["args"][0]).strip()
            pending_read_targets = [p for p in pending_read_targets if p != read_target]

        # Capture a brief digest of the output for phase summaries
        if not is_error:
            preview_lines = tool_result.strip().split("\n")[:3]
            preview = "\n  ".join(preview_lines)[:200]
            turn_tool_digests.append(f"• {current_call_sig}\n  {preview}")

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

        if remaining <= 0 and turn_tool_calls >= 3:
            completed_steps: list[dict[str, object]] = []
            for idx, call_sig in enumerate(turn_tool_log, start=1):
                tool = call_sig.split(" ", 1)[0] if call_sig else ""
                args_text = call_sig.split(" ", 1)[1] if " " in call_sig else ""
                args = args_text.split() if args_text else []
                summary_text = ""
                if idx - 1 < len(turn_tool_digests):
                    digest = turn_tool_digests[idx - 1]
                    summary_text = digest.split("\n", 1)[1].strip() if "\n" in digest else digest.strip()
                completed_steps.append(
                    {"step": idx, "tool": tool, "args": args, "summary": summary_text[:200]}
                )

            key_facts: list[str] = []
            for digest in turn_tool_digests:
                fact_lines = [line.strip() for line in digest.splitlines() if line.strip()]
                if len(fact_lines) >= 2:
                    key_facts.append(fact_lines[1][:200])

            checkpoint_prompt = (
                "[CHECKPOINT] Budget spent. List remaining steps for this task as a short numbered list. "
                "Do NOT call a tool."
            )
            messages.append({"role": "user", "content": checkpoint_prompt})
            logger.append("user", checkpoint_prompt)
            checkpoint_reply = _stream_reply(client, messages)
            print()
            messages.append({"role": assistant_role, "content": checkpoint_reply})
            logger.append("assistant", checkpoint_reply)

            chain_data = {
                "task": user_message,
                "status": "in_progress",
                "turn": 1,
                "completed": completed_steps,
                "next_steps": checkpoint_reply,
                "key_facts": key_facts,
            }
            if CHAIN_LOG_PATH.exists():
                try:
                    existing = loads(CHAIN_LOG_PATH.read_text(encoding="utf-8"))
                    prior_completed = existing.get("completed", []) if isinstance(existing, dict) else []
                    prior_turn = int(existing.get("turn", 0)) if isinstance(existing, dict) else 0
                    chain_data["task"] = existing.get("task", user_message) if isinstance(existing, dict) else user_message
                    chain_data["turn"] = prior_turn + 1
                    chain_data["completed"] = prior_completed + completed_steps
                except Exception:
                    pass

            next_steps_text = (checkpoint_reply or "").strip().lower()
            if not next_steps_text or "done" in next_steps_text or "complete" in next_steps_text:
                chain_data["status"] = "complete"

            CHAIN_LOG_PATH.write_text(dumps(chain_data, indent=2), encoding="utf-8")
            print(f"\n[Chain checkpoint — turn {chain_data['turn']}, {len(chain_data['completed'])} steps done]")
            rlog.event("turn_complete", chars=len(checkpoint_reply))
            wm_entry = working_memory.compress_turn(user_message, checkpoint_reply)
            working_memory.append(**wm_entry)
            _maybe_auto_reflect(client, messages, logger)
            return checkpoint_reply

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
        # Log concise status (not the full system continuation prompt)
        logger.append("system", f"[{turn_tool_calls}/{tool_budget} tools used]")

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
            # Build a digest of what J has gathered (keeps 7B model
            # oriented without the full verbose tool outputs).
            digest_block = "\n".join(turn_tool_digests) if turn_tool_digests else "(none)"
            phase_summary = (
                f"[PHASE {phase_num} COMPLETE — starting phase {phase_num + 1}]\n"
                f"Original task: {user_message}\n\n"
                f"What you've gathered so far:\n{digest_block}\n\n"
                f"Do NOT repeat any call above. "
                f"You have {remaining} calls remaining. "
                f"Continue with the NEXT unfinished step."
            )
            if pending_read_targets:
                todo = ", ".join(pending_read_targets[:12])
                if len(pending_read_targets) > 12:
                    todo += ", ..."
                phase_summary += (
                    f"\n\nChecklist (still unread): {todo}\n"
                    "Pick the next unread file with run_read."
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

        step_prompt = build_step_prompt(step, registry.describe(), tool_budget=2)
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
                budget = max(route_result.tool_budget, MAX_TOOL_BUDGET)
                active_prompt = initial_message
                while True:
                    if CHAIN_LOG_PATH.exists():
                        chain = loads(CHAIN_LOG_PATH.read_text(encoding="utf-8"))
                        if chain.get("status") == "in_progress":
                            if int(chain.get("turn", 0)) >= MAX_CHAIN_TURNS:
                                chain["status"] = "complete"
                                CHAIN_LOG_PATH.write_text(dumps(chain, indent=2), encoding="utf-8")
                                print(f"\n[Chain safety cutoff reached at turn {MAX_CHAIN_TURNS}; marking complete.]")
                                CHAIN_LOG_PATH.unlink(missing_ok=True)
                                break
                            completed = chain.get("completed", [])
                            completed_lines = "\n".join(
                                f"{i}. {step.get('tool', '')} {step.get('args', [])} — {step.get('summary', '')}".strip()
                                for i, step in enumerate(completed, start=1)
                            ) or "1. (none)"
                            facts = chain.get("key_facts", [])
                            facts_lines = "\n".join(f"- {fact}" for fact in facts) or "- (none)"
                            active_prompt = (
                                f"Continuing task (turn {int(chain.get('turn', 0)) + 1}).\n"
                                f"Original: {chain.get('task', initial_message)}\n\n"
                                f"Completed:\n{completed_lines}\n\n"
                                f"Remaining:\n{chain.get('next_steps', '')}\n\n"
                                f"Key facts:\n{facts_lines}\n\n"
                                "You have 3 tool calls. Continue where you left off."
                            )
                    _run_turn(client, messages, logger, rlog, active_prompt, registry, autonomy_mode, tool_budget=budget)
                    if not CHAIN_LOG_PATH.exists():
                        break
                    chain = loads(CHAIN_LOG_PATH.read_text(encoding="utf-8"))
                    if chain.get("status") != "in_progress":
                        summary_prompt = "[TASK COMPLETE] Summarize what you accomplished."
                        messages.append({"role": "user", "content": summary_prompt})
                        logger.append("user", summary_prompt)
                        completion = _stream_reply(client, messages)
                        print()
                        messages.append({"role": _assistant_role(client), "content": completion})
                        logger.append("assistant", completion)
                        CHAIN_LOG_PATH.unlink(missing_ok=True)
                        break
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
                    "  /gguf            — show current GGUF path mode\n"
                    "  /gguf host       — switch to host GGUF (C:\\Jarvis\\...\\gemma.gguf)\n"
                    "  /gguf local      — switch back to shard/default GGUF\n"
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

            if user_message == "/gguf":
                current_path = os.getenv("LLAMA_MODEL_PATH", "").strip()
                mode = "host" if current_path.lower() == HOST_GGUF_PATH.lower() else "local/default"
                resolved = str(client.model_path)
                print(f"[GGUF] Mode: {mode}")
                print(f"[GGUF] Active path: {resolved}")
                print("Usage: /gguf host | /gguf local")
                continue

            if user_message in {"/gguf host", "/gguf local"}:
                use_host = user_message.endswith("host")
                if use_host:
                    os.environ["LLAMA_MODEL_PATH"] = HOST_GGUF_PATH
                    os.environ["LLAMA_MODEL_ALIAS"] = "gemma4-gguf-host"
                else:
                    os.environ.pop("LLAMA_MODEL_PATH", None)
                    os.environ.pop("LLAMA_MODEL_ALIAS", None)
                local_server.stop()
                client = create_client()
                messages = build_history(client)
                local_server = LocalLlamaServer(client)
                local_server.ensure_started()
                mode = "host" if use_host else "local/default"
                print(f"[GGUF] Switched to {mode} model path.")
                print(f"[GGUF] Active path: {client.model_path}")
                rlog.event("gguf_toggle", mode=mode, model_path=str(client.model_path))
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
                def _llm_reflect(prompt: str) -> str:
                    messages.append({"role": "user", "content": prompt})
                    messages[:] = trim_context(messages, max_tokens=client.num_ctx)
                    raw = _stream_reply(client, messages)
                    print()
                    messages.append({"role": _assistant_role(client), "content": raw})
                    return raw

                consolidated = compress_entries(entries, _llm_reflect)
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
                budget = max(route_result.tool_budget, MAX_TOOL_BUDGET)
                print(ui.j_stream_start(), end="", flush=True)
                active_prompt = user_message
                while True:
                    if CHAIN_LOG_PATH.exists():
                        chain = loads(CHAIN_LOG_PATH.read_text(encoding="utf-8"))
                        if chain.get("status") == "in_progress":
                            if int(chain.get("turn", 0)) >= MAX_CHAIN_TURNS:
                                chain["status"] = "complete"
                                CHAIN_LOG_PATH.write_text(dumps(chain, indent=2), encoding="utf-8")
                                print(f"\n[Chain safety cutoff reached at turn {MAX_CHAIN_TURNS}; marking complete.]")
                                CHAIN_LOG_PATH.unlink(missing_ok=True)
                                break
                            completed = chain.get("completed", [])
                            completed_lines = "\n".join(
                                f"{i}. {step.get('tool', '')} {step.get('args', [])} — {step.get('summary', '')}".strip()
                                for i, step in enumerate(completed, start=1)
                            ) or "1. (none)"
                            facts = chain.get("key_facts", [])
                            facts_lines = "\n".join(f"- {fact}" for fact in facts) or "- (none)"
                            active_prompt = (
                                f"Continuing task (turn {int(chain.get('turn', 0)) + 1}).\n"
                                f"Original: {chain.get('task', user_message)}\n\n"
                                f"Completed:\n{completed_lines}\n\n"
                                f"Remaining:\n{chain.get('next_steps', '')}\n\n"
                                f"Key facts:\n{facts_lines}\n\n"
                                "You have 3 tool calls. Continue where you left off."
                            )
                    _run_turn(
                        client, messages, logger, rlog, active_prompt, registry, autonomy_mode,
                        tool_budget=budget,
                    )
                    if not CHAIN_LOG_PATH.exists():
                        break
                    chain = loads(CHAIN_LOG_PATH.read_text(encoding="utf-8"))
                    if chain.get("status") != "in_progress":
                        summary_prompt = "[TASK COMPLETE] Summarize what you accomplished."
                        messages.append({"role": "user", "content": summary_prompt})
                        logger.append("user", summary_prompt)
                        completion = _stream_reply(client, messages)
                        print()
                        messages.append({"role": _assistant_role(client), "content": completion})
                        logger.append("assistant", completion)
                        CHAIN_LOG_PATH.unlink(missing_ok=True)
                        break
                # Weight-triggered reflection
                if should_reflect():
                    entries = working_memory.read_all()
                    print(f"\n{ui.stark_blue(persona.reflect_start(len(entries), working_memory.size_bytes()))}")
                    def _llm_reflect(prompt: str) -> str:
                        messages.append({"role": "user", "content": prompt})
                        messages[:] = trim_context(messages, max_tokens=client.num_ctx)
                        raw = _stream_reply(client, messages)
                        print()
                        messages.append({"role": _assistant_role(client), "content": raw})
                        return raw

                    consolidated = compress_entries(entries, _llm_reflect)
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
