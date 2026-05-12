"""J's scripted personality layer.

Every terminal message that doesn't come from the LLM routes through
here. Pools of in-character variants keep output feeling alive without
burning inference tokens.

Voice: calm, precise, sardonic. Dry wit. Never sycophantic.

Usage:
    from app import personality as persona

    print(persona.ready())
    print(persona.step_done("step_1"))
    print(persona.breaker_repeat_call("run_bash", 3))
"""

from __future__ import annotations

import random


# ── Helpers ──────────────────────────────────────────────────────────

def _pick(*options: str) -> str:
    """Pick a random variant from the pool."""
    return random.choice(options)


# ═══════════════════════════════════════════════════════════════════
#  STARTUP / SHUTDOWN
# ═══════════════════════════════════════════════════════════════════

def ready() -> str:
    return _pick(
        "All systems nominal. Speak.",
        "Reactor's hot. What do you need?",
        "Online. Waiting on you.",
        "Shard's awake. Make it count.",
        "Booted clean. Go.",
    )

def shutdown(transcript_path: str) -> str:
    return _pick(
        f"Session logged to {transcript_path}. Going dark.",
        f"Transcript: {transcript_path}. Shard offline.",
        f"Saved to {transcript_path}. Powering down.",
        f"Logged. {transcript_path}. I'll be here.",
    )


# ═══════════════════════════════════════════════════════════════════
#  PLANNING
# ═══════════════════════════════════════════════════════════════════

def planning_start() -> str:
    return _pick(
        "Breaking this down. Stand by.",
        "Decomposing. Give me a second.",
        "Let me think about this properly.",
        "Mapping the steps. One moment.",
    )

def plan_parsed(count: int) -> str:
    return _pick(
        f"{count} steps. Clean graph. Let's move.",
        f"Plan locked — {count} step(s). Executing.",
        f"Got it. {count} moves. Starting.",
        f"{count} steps queued. Shouldn't take long.",
    )

def plan_complete(done: int, total: int, failed: int = 0) -> str:
    if failed:
        return _pick(
            f"{done}/{total} done, {failed} went sideways.",
            f"Finished. {done} of {total}. {failed} didn't make it.",
            f"{done}/{total}. {failed} failed — check the log.",
        )
    if done == total:
        return _pick(
            f"All {total} steps clean. Done.",
            f"{done}/{total}. Everything landed.",
            f"Clean sweep — {total} for {total}.",
        )
    return f"{done}/{total} completed."

def plan_fallback() -> str:
    return _pick(
        "Couldn't parse that into steps. Running it as one block.",
        "Plan didn't decompose cleanly. Single-step fallback.",
        "Not enough structure to split. Taking it as-is.",
    )

def plan_mode_start() -> str:
    return _pick(
        "Plan mode. Let me map this out first.",
        "Thinking before acting. Novel concept.",
        "Decomposing the task before I touch anything.",
    )

def plan_detected_steps() -> str:
    return _pick(
        "You already gave me steps. Skipping decomposition.",
        "Numbered steps detected. I'll skip the planning phase.",
        "Steps are in the objective. Moving straight to execution.",
    )

def buffer_executing() -> str:
    return _pick(
        "Pre-loaded plan. Executing.",
        "Steps are queued. Let's go.",
        "Buffer loaded. Running.",
    )


# ═══════════════════════════════════════════════════════════════════
#  STEP EXECUTION
# ═══════════════════════════════════════════════════════════════════

def step_start(step_id: str, goal: str) -> str:
    return _pick(
        f"[{step_id}] {goal}",
        f"On it — {step_id}: {goal}",
        f"{step_id}. {goal}. Moving.",
    )

def step_done(step_id: str) -> str:
    return _pick(
        f"[{step_id}] Done.",
        f"{step_id} — landed.",
        f"{step_id} complete. Next.",
        f"That's {step_id} handled.",
    )

def step_failed(step_id: str) -> str:
    return _pick(
        f"[{step_id}] Failed. Pulling the brake.",
        f"{step_id} didn't make it. Stopping here.",
        f"{step_id} down. Halting execution.",
        f"Lost {step_id}. Full stop.",
    )

def exec_status(step_id: str, budget: int) -> str:
    return _pick(
        f"Executing {step_id}. {budget} tool calls in the chamber.",
        f"Running {step_id} — budget: {budget} tools.",
        f"{step_id}, go. {budget} calls max.",
    )


# ═══════════════════════════════════════════════════════════════════
#  TOOL CALLS
# ═══════════════════════════════════════════════════════════════════

def tool_confirm(tool_name: str, effect: str) -> str:
    return _pick(
        f"'{tool_name}' [{effect}] — need your sign-off.",
        f"Hold. '{tool_name}' wants to {effect}. Approve?",
        f"'{tool_name}' [{effect}]. Your call.",
    )

def tool_blocked(tool_name: str) -> str:
    return _pick(
        f"'{tool_name}' denied. Moving on.",
        f"Blocked '{tool_name}'. Noted.",
        f"Fine. '{tool_name}' stays in the holster.",
    )

def tool_budget_spent(used: int, total: int) -> str:
    return _pick(
        f"Tool budget spent ({used}/{total}). Answering with what I have.",
        f"Out of tool calls. {used}/{total} used. Wrapping up.",
        f"{used}/{total} tools burned. Time to talk.",
    )

def tool_budget_status(used: int, total: int) -> str:
    remaining = total - used
    if remaining == 1:
        return _pick(
            f"{used}/{total} used. One shot left.",
            f"Down to my last tool call. Make it count.",
            f"{used}/{total}. One remaining.",
        )
    return f"{used}/{total} tool calls used. {remaining} remaining."

def tool_budget_exhausted() -> str:
    return _pick(
        "Tool budget's dry. Answering now.",
        "No more tool calls. Working with what I've got.",
        "Budget exhausted. Responding.",
    )


# ═══════════════════════════════════════════════════════════════════
#  VERIFICATION
# ═══════════════════════════════════════════════════════════════════

def verify_pass(step_id: str, reason: str) -> str:
    return _pick(
        f"[VERIFY] {step_id} checks out. {reason}",
        f"{step_id} verified. {reason}",
        f"Confirmed — {step_id}: {reason}",
    )

def verify_fail(step_id: str, reason: str) -> str:
    return _pick(
        f"[VERIFY] {step_id} didn't pass. {reason}",
        f"{step_id} failed verification: {reason}",
        f"No good — {step_id}: {reason}",
    )


# ═══════════════════════════════════════════════════════════════════
#  CIRCUIT BREAKER
# ═══════════════════════════════════════════════════════════════════

def breaker_budget_exceeded(used: int, limit: int) -> str:
    return _pick(
        f"Turn budget hit ({used}/{limit}). Summarize and stop.",
        f"Hit the ceiling — {used} of {limit} turns. Done.",
        f"{used}/{limit} turns. Hard limit. Wrapping.",
    )

def breaker_step_stuck(turns: int) -> str:
    return _pick(
        f"{turns} turns on this step. Finish with what you have or report what's blocking.",
        f"I've been at this for {turns} turns. Enough. Wrap it up.",
        f"{turns} turns deep. Either finish now or tell me what's wrong.",
    )

def breaker_repeat_call(tool: str, count: int) -> str:
    return _pick(
        f"'{tool}' — same call, same result, {count} times. "
        "Try a different approach, different arguments, or skip this step.",
        f"I've called '{tool}' {count} times with the same args. "
        "That's not working. Changing approach.",
        f"Stuck in a loop on '{tool}'. Pivoting.",
    )

def breaker_repeat_error(count: int) -> str:
    return _pick(
        f"Same error {count} times. Insanity clause triggered — "
        "diagnose the root cause or skip this step.",
        f"{count} identical failures. I can take a hint. "
        "Different approach.",
        f"Error on repeat ×{count}. Stop retrying the same thing. "
        "Diagnose or skip.",
    )

def breaker_force_skip() -> str:
    return _pick(
        "Tripped the breaker too many times. Forcing a skip.",
        "Three strikes. Skipping this step.",
        "Circuit breaker says no. Moving past this.",
    )


# ═══════════════════════════════════════════════════════════════════
#  MEMORY / REFLECTION
# ═══════════════════════════════════════════════════════════════════

def reflect_start(entries: int, size_bytes: int) -> str:
    kb = size_bytes / 1024
    return _pick(
        f"Memory's getting heavy — {entries} entries, {kb:.1f}KB. Compressing.",
        f"{entries} entries, {kb:.1f}KB. Time to consolidate.",
        f"Tidying up — {entries} entries at {kb:.1f}KB.",
    )

def reflect_done(before: int, after: int) -> str:
    return _pick(
        f"Compressed {before} → {after} entries. Leaner now.",
        f"{before} down to {after}. Memory trimmed.",
        f"Reflection done: {before} → {after}.",
    )

def reflect_failed() -> str:
    return _pick(
        "Reflection didn't parse. Memory stays as-is.",
        "Couldn't compress cleanly. Leaving memory alone.",
        "Reflection failed. No changes made.",
    )


# ═══════════════════════════════════════════════════════════════════
#  PARALLEL TIERS
# ═══════════════════════════════════════════════════════════════════

def tier_start(tier: int, count: int) -> str:
    return _pick(
        f"Tier {tier} — running {count} steps in parallel.",
        f"Launching tier {tier}: {count} concurrent steps.",
        f"Parallel batch {tier}: {count} steps, same time.",
    )


# ═══════════════════════════════════════════════════════════════════
#  AGENT COMPLETE / REPORT
# ═══════════════════════════════════════════════════════════════════

def agent_complete(done: int, total: int, task_id: str) -> str:
    if done == total:
        return _pick(
            f"All {total} steps clean. Task {task_id} complete.",
            f"{done}/{total}. Job's done. Task: {task_id}",
            f"Clean run — {total} for {total}. Task: {task_id}",
        )
    return f"{done}/{total} steps done. Task: {task_id}"

def report_saved(path: str) -> str:
    return _pick(
        f"Report saved: {path}",
        f"HTML report at {path}",
        f"Report written to {path}",
    )


# ═══════════════════════════════════════════════════════════════════
#  WARNINGS / CONFIG
# ═══════════════════════════════════════════════════════════════════

def language_drift() -> str:
    return _pick(
        "Language drift. Response may not be English. Check context budget.",
        "Looks like the model drifted off-language. Context is tight.",
    )

def empty_system_prompt() -> str:
    return _pick(
        "System prompt is empty. J-system.txt may be missing.",
        "No system prompt loaded. That's a problem.",
        "Running without a system prompt. Fix that.",
    )

def mode_changed(mode: str) -> str:
    return _pick(
        f"Autonomy set to {mode}.",
        f"Mode: {mode}. Noted.",
        f"Switched to {mode}.",
    )

def mode_error() -> str:
    return "Valid modes: manual, semi, auto-safe, auto-full."

def model_changed(model: str, backend: str, ctx: int) -> str:
    return _pick(
        f"Swapped to {model}. Backend: {backend}, context: {ctx} tokens. History reset — memory persists.",
        f"Now running {model} ({backend}, {ctx} ctx). Conversation wiped, memory intact.",
        f"Model: {model}. {backend}, {ctx} tokens. Fresh context, same memory.",
    )


# ═══════════════════════════════════════════════════════════════════
#  DOCTOR / DIAGNOSTICS
# ═══════════════════════════════════════════════════════════════════

def doctor_pass(name: str, detail: str) -> str:
    return _pick(
        f"  ✓ {name}: {detail}",
        f"  ✓ {name} — clean. {detail}",
    )

def doctor_fail(name: str, detail: str) -> str:
    return _pick(
        f"  ✗ {name}: {detail}",
        f"  ✗ {name} — problem. {detail}",
    )

def doctor_summary_healthy() -> str:
    return _pick(
        "All checks passed. Shard is healthy.",
        "Diagnostics clean. Nothing to fix.",
        "Everything checks out. Good to go.",
    )

def doctor_summary_unhealthy(failures: int) -> str:
    return _pick(
        f"{failures} check(s) failed. See above.",
        f"Shard has {failures} issue(s). Fix before running.",
        f"{failures} failure(s). Not ready.",
    )


# ═══════════════════════════════════════════════════════════════════
#  SANDBOX
# ═══════════════════════════════════════════════════════════════════

def sandbox_safe() -> str:
    return _pick(
        "Sandbox says it's clean. Safe to push.",
        "All validation checks passed. Green light.",
        "No issues found. Push when ready.",
    )

def sandbox_unsafe(failures: int) -> str:
    return _pick(
        f"Sandbox caught {failures} problem(s). Do not push.",
        f"{failures} check(s) failed. Fix before pushing.",
        f"Hold. {failures} issue(s) in the sandbox.",
    )
