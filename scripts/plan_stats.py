#!/usr/bin/env python3
# Copyright (c) 2024-2026 Reed Richards (s4ndm4n33). Licensed under BSL 1.1.
"""Plan verify/reject rate reporter.

Parses runtime JSONL logs from /plan builds and reports:
  - Total steps planned vs completed
  - Verify pass / fail counts and rate
  - Per-step breakdown with reasons
  - Tool calls per step
  - Timing between events

Usage:
  python scripts/plan_stats.py                          # latest session
  python scripts/plan_stats.py logs/runtime/20260515-143022.jsonl   # specific log
  python scripts/plan_stats.py --all                    # all sessions
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
RUNTIME_DIR = BASE_DIR / "logs" / "runtime"


def load_events(path: Path) -> list[dict]:
    """Load JSONL events from a runtime log file."""
    events = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return events


def extract_plan_runs(events: list[dict]) -> list[dict]:
    """Extract /plan build data from a stream of events.

    Returns a list of plan-run dicts, each containing:
      objective, steps_planned, steps_done, verifications[], tool_calls[]
    """
    runs = []
    current = None

    for ev in events:
        name = ev.get("event", "")
        ts = ev.get("timestamp", "")

        if name == "agent_start":
            current = {
                "objective": ev.get("objective", ""),
                "started": ts,
                "verifications": [],
                "tool_calls": [],
                "steps_planned": 0,
                "steps_done": 0,
                "steps_failed": 0,
                "ended": None,
            }

        elif name == "verify_done" and current is not None:
            current["verifications"].append({
                "step": ev.get("step", "?"),
                "passed": ev.get("passed", True),
                "reason": ev.get("reason", ""),
                "timestamp": ts,
            })

        elif name == "tool_call" and current is not None:
            current["tool_calls"].append({
                "tool": ev.get("tool", "?"),
                "hop": ev.get("hop", 0),
                "timestamp": ts,
            })

        elif name == "agent_step_failed" and current is not None:
            current["steps_failed"] += 1

        elif name == "agent_complete" and current is not None:
            current["steps_planned"] = ev.get("total", 0)
            current["steps_done"] = ev.get("done", 0)
            current["ended"] = ts
            runs.append(current)
            current = None

        # Also handle buffer plan mode
        elif name == "buffer_plan_start":
            current = {
                "objective": ev.get("objective", ""),
                "started": ts,
                "verifications": [],
                "tool_calls": [],
                "steps_planned": 0,
                "steps_done": 0,
                "steps_failed": 0,
                "ended": None,
            }

        elif name == "buffer_plan_complete" and current is not None:
            current["steps_planned"] = ev.get("total", 0)
            current["steps_done"] = ev.get("done", 0)
            current["steps_failed"] = ev.get("failed", 0)
            current["ended"] = ts
            runs.append(current)
            current = None

    return runs


def format_duration(start: str, end: str) -> str:
    """Human-readable duration between two ISO timestamps."""
    try:
        t0 = datetime.fromisoformat(start)
        t1 = datetime.fromisoformat(end)
        delta = t1 - t0
        secs = int(delta.total_seconds())
        if secs < 60:
            return f"{secs}s"
        mins, secs = divmod(secs, 60)
        return f"{mins}m {secs}s"
    except (ValueError, TypeError):
        return "?"


def print_run_report(run: dict, index: int = 0) -> None:
    """Print a formatted report for one /plan run."""
    v = run["verifications"]
    passed = sum(1 for x in v if x["passed"])
    failed = sum(1 for x in v if not x["passed"])
    total_v = len(v)
    rate = (passed / total_v * 100) if total_v else 0

    duration = format_duration(run["started"], run["ended"]) if run["ended"] else "?"

    # Header
    print(f"\n{'=' * 60}")
    print(f"  /plan Run #{index + 1}")
    print(f"{'=' * 60}")
    print(f"  Objective : {run['objective'][:80]}")
    print(f"  Duration  : {duration}")
    print(f"  Steps     : {run['steps_done']}/{run['steps_planned']} completed")
    print()

    # Verify rate box
    bar_len = 30
    fill = int(bar_len * rate / 100) if total_v else 0
    bar = "█" * fill + "░" * (bar_len - fill)
    print(f"  VERIFY RATE: {rate:.0f}%  [{bar}]")
    print(f"  ✓ Passed : {passed}")
    print(f"  ✗ Failed : {failed}")
    print(f"  Total    : {total_v}")
    print()

    # Per-step breakdown
    if v:
        print(f"  {'Step':<15} {'Result':<8} Reason")
        print(f"  {'─' * 15} {'─' * 8} {'─' * 35}")
        for entry in v:
            status = "✓ PASS" if entry["passed"] else "✗ FAIL"
            reason = entry["reason"][:50]
            print(f"  {entry['step']:<15} {status:<8} {reason}")
        print()

    # Tool usage summary
    if run["tool_calls"]:
        tool_counts = defaultdict(int)
        for tc in run["tool_calls"]:
            tool_counts[tc["tool"]] += 1
        print(f"  Tool calls: {len(run['tool_calls'])} total")
        for tool, count in sorted(tool_counts.items(), key=lambda x: -x[1]):
            print(f"    {tool:<25} × {count}")
        print()


def print_aggregate(runs: list[dict]) -> None:
    """Print aggregate stats across multiple runs."""
    if not runs:
        print("\nNo /plan runs found in logs.")
        return

    all_v = []
    total_steps = 0
    done_steps = 0
    for r in runs:
        all_v.extend(r["verifications"])
        total_steps += r["steps_planned"]
        done_steps += r["steps_done"]

    passed = sum(1 for x in all_v if x["passed"])
    failed = sum(1 for x in all_v if not x["passed"])
    total_v = len(all_v)
    rate = (passed / total_v * 100) if total_v else 0

    print(f"\n{'=' * 60}")
    print(f"  AGGREGATE — {len(runs)} plan run(s)")
    print(f"{'=' * 60}")
    print(f"  Steps completed : {done_steps}/{total_steps}")
    print(f"  Verify pass     : {passed}/{total_v} ({rate:.1f}%)")
    print(f"  Verify fail     : {failed}/{total_v} ({100 - rate:.1f}%)")

    # Failure reasons
    if failed:
        print(f"\n  Failure reasons:")
        for entry in all_v:
            if not entry["passed"]:
                print(f"    [{entry['step']}] {entry['reason'][:70]}")
    print()


def main() -> None:
    args = sys.argv[1:]

    if not args:
        # Latest session log
        logs = sorted(RUNTIME_DIR.glob("*.jsonl"))
        if not logs:
            print(f"No runtime logs found in {RUNTIME_DIR}")
            print("Run a /plan build first, then re-run this script.")
            return
        target = logs[-1]
        print(f"Reading latest log: {target.name}")
        events = load_events(target)
        runs = extract_plan_runs(events)
        for i, run in enumerate(runs):
            print_run_report(run, i)
        print_aggregate(runs)

    elif args[0] == "--all":
        logs = sorted(RUNTIME_DIR.glob("*.jsonl"))
        if not logs:
            print(f"No runtime logs found in {RUNTIME_DIR}")
            return
        print(f"Scanning {len(logs)} log file(s)...")
        all_runs = []
        for log in logs:
            events = load_events(log)
            runs = extract_plan_runs(events)
            all_runs.extend(runs)
        for i, run in enumerate(all_runs):
            print_run_report(run, i)
        print_aggregate(all_runs)

    else:
        target = Path(args[0])
        if not target.exists():
            target = BASE_DIR / args[0]
        if not target.exists():
            print(f"File not found: {args[0]}")
            return
        print(f"Reading: {target}")
        events = load_events(target)
        runs = extract_plan_runs(events)
        for i, run in enumerate(runs):
            print_run_report(run, i)
        print_aggregate(runs)


if __name__ == "__main__":
    main()
