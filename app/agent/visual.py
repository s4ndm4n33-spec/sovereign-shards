"""Visual/UI output — terminal-native and HTML report generation.

Provides rich terminal output using Unicode box-drawing characters
and generates standalone HTML reports that can be opened from the USB
in any browser. Zero external dependencies.
"""

from __future__ import annotations

import html
import os
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
REPORTS_DIR = BASE_DIR / "reports"


# ── Terminal Visuals ──────────────────────────────────────────────────


def box(title: str, content: str, width: int = 60) -> str:
    """Draw a Unicode box around content."""
    lines = content.splitlines()
    inner = width - 4
    out = []
    out.append(f"┌─ {title[:inner]} {'─' * max(0, inner - len(title) - 1)}┐")
    for line in lines:
        if len(line) > inner:
            line = line[:inner - 1] + "…"
        out.append(f"│ {line:<{inner}} │")
    out.append(f"└{'─' * (width - 2)}┘")
    return "\n".join(out)


def progress_bar(current: int, total: int, width: int = 30, label: str = "") -> str:
    """Render a Unicode progress bar."""
    if total <= 0:
        pct = 0.0
    else:
        pct = min(current / total, 1.0)
    filled = int(width * pct)
    bar = "█" * filled + "░" * (width - filled)
    text = f"[{bar}] {current}/{total}"
    if label:
        text = f"{label} {text}"
    return text


def task_tree(
    steps: list[dict],
    completed: set[str] | None = None,
    width: int = 60,
) -> str:
    """Render a task graph as a visual tree with status indicators.

    Args:
        steps: List of dicts with 'id', 'goal', 'depends_on' keys.
        completed: Set of completed step IDs.
        width: Max width.
    """
    if completed is None:
        completed = set()

    lines = ["┌── Task Graph ──────────────────────────────┐"]

    for i, step in enumerate(steps):
        sid = step.get("id", f"step_{i}")
        goal = step.get("goal", "")[:width - 15]
        deps = step.get("depends_on", [])

        if sid in completed:
            icon = "✅"
        elif all(d in completed for d in deps):
            icon = "🔄"  # Ready
        else:
            icon = "⏳"  # Waiting

        connector = "├" if i < len(steps) - 1 else "└"
        bar = "│" if i < len(steps) - 1 else " "

        lines.append(f"{connector}── {icon} {sid}: {goal}")
        if deps:
            lines.append(f"{bar}      └─ depends: {', '.join(deps)}")

    lines.append("└───────────────────────────────────────────┘")
    return "\n".join(lines)


def status_panel(
    task_name: str,
    done: int,
    total: int,
    current_step: str = "",
    memory_kb: float = 0,
    elapsed: float = 0,
) -> str:
    """Render a dashboard-style status panel."""
    prog = progress_bar(done, total, label="Progress")
    elapsed_str = f"{elapsed:.1f}s" if elapsed else "—"
    mem_str = f"{memory_kb:.1f}KB" if memory_kb else "—"

    content = (
        f"Task: {task_name}\n"
        f"{prog}\n"
        f"Current: {current_step or '—'}\n"
        f"Elapsed: {elapsed_str}  Memory: {mem_str}"
    )
    return box("Agent Status", content)


# ── HTML Report Generation ────────────────────────────────────────────


_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
         background: #0d1117; color: #c9d1d9; padding: 2rem; line-height: 1.6; }}
  .container {{ max-width: 900px; margin: 0 auto; }}
  h1 {{ color: #58a6ff; margin-bottom: 0.5rem; font-size: 1.8rem; }}
  h2 {{ color: #8b949e; font-size: 1.1rem; margin-bottom: 1.5rem; font-weight: 400; }}
  .card {{ background: #161b22; border: 1px solid #30363d; border-radius: 8px;
           padding: 1.2rem; margin-bottom: 1rem; }}
  .card h3 {{ color: #58a6ff; margin-bottom: 0.8rem; font-size: 1rem; }}
  .stat {{ display: inline-block; margin-right: 2rem; margin-bottom: 0.5rem; }}
  .stat .label {{ color: #8b949e; font-size: 0.85rem; }}
  .stat .value {{ color: #f0f6fc; font-size: 1.4rem; font-weight: 600; }}
  .step {{ padding: 0.6rem 0; border-bottom: 1px solid #21262d; }}
  .step:last-child {{ border-bottom: none; }}
  .step .id {{ color: #58a6ff; font-weight: 600; margin-right: 0.5rem; }}
  .pass {{ color: #3fb950; }} .fail {{ color: #f85149; }} .pending {{ color: #d29922; }}
  .issue {{ padding: 0.4rem 0.8rem; margin: 0.3rem 0; border-radius: 4px;
            font-family: monospace; font-size: 0.85rem; }}
  .issue.warning {{ background: #1c1c00; border-left: 3px solid #d29922; }}
  .issue.error {{ background: #1c0000; border-left: 3px solid #f85149; }}
  pre {{ background: #0d1117; border: 1px solid #30363d; border-radius: 6px;
         padding: 1rem; overflow-x: auto; font-size: 0.85rem; }}
  .footer {{ color: #484f58; text-align: center; margin-top: 2rem; font-size: 0.8rem; }}
</style>
</head>
<body>
<div class="container">
  <h1>{title}</h1>
  <h2>{subtitle}</h2>
  {body}
  <p class="footer">Generated by Sovereign Shard J · {timestamp}</p>
</div>
</body>
</html>
"""


def _esc(text: str) -> str:
    return html.escape(str(text))


def generate_task_report(
    task_name: str,
    steps: list[dict],
    completed: set[str],
    issues: list[dict] | None = None,
    stats: dict | None = None,
) -> str:
    """Generate a standalone HTML task report.

    Args:
        task_name: Name/objective of the task.
        steps: List of step dicts with 'id', 'goal', 'result'.
        completed: Set of completed step IDs.
        issues: Optional Five Masters issues [{master, line, message, severity}].
        stats: Optional dict of runtime stats.

    Returns:
        Path to the generated HTML file.
    """
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    body_parts = []

    # Stats card
    if stats:
        stats_html = "".join(
            f'<div class="stat"><div class="label">{_esc(k)}</div>'
            f'<div class="value">{_esc(str(v))}</div></div>'
            for k, v in stats.items()
        )
        body_parts.append(f'<div class="card"><h3>Stats</h3>{stats_html}</div>')

    # Steps card
    done = len(completed)
    total = len(steps)
    steps_html = []
    for step in steps:
        sid = step.get("id", "?")
        goal = _esc(step.get("goal", ""))
        result = _esc(step.get("result", ""))
        if sid in completed:
            status = '<span class="pass">✓ PASSED</span>'
        else:
            status = '<span class="pending">○ PENDING</span>'
        steps_html.append(
            f'<div class="step"><span class="id">{_esc(sid)}</span>'
            f'{status} — {goal}'
            f'{"<br><small>" + result + "</small>" if result else ""}</div>'
        )

    body_parts.append(
        f'<div class="card"><h3>Steps ({done}/{total})</h3>'
        f'{"".join(steps_html)}</div>'
    )

    # Issues card
    if issues:
        issues_html = []
        for iss in issues[:30]:
            sev = iss.get("severity", "warning")
            master = _esc(iss.get("master", ""))
            msg = _esc(iss.get("message", ""))
            line = iss.get("line", "?")
            issues_html.append(
                f'<div class="issue {sev}">'
                f'L{line} [{master}] {msg}</div>'
            )
        body_parts.append(
            f'<div class="card"><h3>Code Quality ({len(issues)} issues)</h3>'
            f'{"".join(issues_html)}</div>'
        )

    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    report_html = _HTML_TEMPLATE.format(
        title=_esc(task_name),
        subtitle=f"{done}/{total} steps completed",
        body="\n".join(body_parts),
        timestamp=timestamp,
    )

    # Atomic write
    safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in task_name[:40])
    filename = f"report_{safe_name}_{int(time.time())}.html"
    filepath = REPORTS_DIR / filename
    tmp = str(filepath) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(report_html)
    os.replace(tmp, str(filepath))

    return str(filepath)


def generate_refactor_report(project_map_summary: str, issues: list[dict]) -> str:
    """Generate an HTML refactoring analysis report."""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    body_parts = [
        f'<div class="card"><h3>Project Overview</h3><pre>{_esc(project_map_summary)}</pre></div>'
    ]

    if issues:
        issues_html = []
        for iss in issues[:50]:
            sev = iss.get("severity", "warning")
            kind = _esc(iss.get("kind", ""))
            file_ = _esc(iss.get("file", ""))
            msg = _esc(iss.get("message", ""))
            line = iss.get("line", "?")
            issues_html.append(
                f'<div class="issue {sev}">'
                f'[{kind}] {file_}:{line} — {msg}</div>'
            )
        body_parts.append(
            f'<div class="card"><h3>Issues ({len(issues)})</h3>'
            f'{"".join(issues_html)}</div>'
        )

    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    report_html = _HTML_TEMPLATE.format(
        title="Refactoring Analysis",
        subtitle=f"{len(issues)} issues found",
        body="\n".join(body_parts),
        timestamp=timestamp,
    )

    filename = f"refactor_report_{int(time.time())}.html"
    filepath = REPORTS_DIR / filename
    tmp = str(filepath) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(report_html)
    os.replace(tmp, str(filepath))

    return str(filepath)
