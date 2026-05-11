"""Terminal UI styling for the Sovereign Shard.

Colour scheme: IRON MAN
  - Stark Blue (arc reactor)  → J's voice, code output
  - Gold                      → user input, highlights, headings
  - Red                       → system events, framework, errors
  - White                     → emphasis, bright accents
  - Dim gray                  → metadata, secondary info

All output uses ANSI escape sequences (Windows 10+ cmd.exe supports them).
Falls back to plain text if the terminal doesn't support colour.
"""

from __future__ import annotations

import os
import sys


# ── ANSI colour support ──────────────────────────────────────────

def _supports_colour() -> bool:
    """Check if the terminal likely supports ANSI colours."""
    if os.getenv("NO_COLOR"):
        return False
    if os.getenv("FORCE_COLOR"):
        return True
    if sys.platform == "win32":
        # Windows 10 build 14393+ supports ANSI in cmd.exe
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            # Enable virtual terminal processing on stdout
            kernel32.SetConsoleMode(
                kernel32.GetStdHandle(-11), 7
            )
            return True
        except Exception:
            return False
    return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()


COLOUR = _supports_colour()

# Black background persists through every colour reset.
# \033[0m alone resets bg to terminal default (often grey/white on Windows).
# We always reset to \033[0;40m so the black bg sticks.
_RESET = "\033[0;40m" if COLOUR else ""


def _c(code: str, text: str) -> str:
    """Wrap text in ANSI colour code if supported."""
    if not COLOUR:
        return text
    return f"\033[{code}m{text}{_RESET}"


def init() -> None:
    """Initialise the terminal for the shard UI.

    Sets black background, clears the screen, and positions the cursor
    at top-left. Call once at startup before the banner.
    """
    if not COLOUR:
        return
    # Set black background for the whole terminal
    sys.stdout.write("\033[40m")      # bg black
    sys.stdout.write("\033[97m")      # default text bright white
    sys.stdout.write("\033[2J")       # clear entire screen (fills with bg)
    sys.stdout.write("\033[H")        # cursor to top-left
    sys.stdout.flush()


# ── Colour helpers (Iron Man palette) ─────────────────────────────

def stark_blue(text: str) -> str:
    """Bright blue — arc reactor, J's voice, code output."""
    return _c("94", text)

def gold(text: str) -> str:
    """Bright yellow/gold — user input, headings, highlights."""
    return _c("93", text)

def red(text: str) -> str:
    """Bright red — Iron Man red, system events, errors."""
    return _c("91", text)

def deep_red(text: str) -> str:
    """Dark red — subtle accents, framework markers."""
    return _c("31", text)

def white(text: str) -> str:
    """Bright white — emphasis, bright accents."""
    return _c("97", text)

def dim(text: str) -> str:
    """Dark gray — metadata, secondary info."""
    return _c("90", text)

def green(text: str) -> str:
    """Green — success, pass."""
    return _c("92", text)

def bold(text: str) -> str:
    """Bold text."""
    return _c("1", text)


# ── Prompt styling ────────────────────────────────────────────────

def j_prefix() -> str:
    """Styled 'J.: ' prefix for agent output."""
    return stark_blue("J.: ")

def j_stream_start() -> str:
    """Print J prefix and prepare for streaming tokens."""
    return f"\n{j_prefix()}"

def you_prompt() -> str:
    """Styled input prompt for the user."""
    return f"\n{red('▶')} {gold('You')}: "

def tool_tag(name: str) -> str:
    """Styled tool call tag."""
    return gold(f"⚡ [{name}]")

def error_tag(msg: str = "") -> str:
    """Styled error prefix."""
    return red(f"✗ {msg}" if msg else "✗ ERROR")

def ok_tag(msg: str = "") -> str:
    """Styled success tag."""
    return green(f"✓ {msg}" if msg else "✓")

def warn_tag(msg: str = "") -> str:
    """Styled warning tag."""
    return gold(f"⚠ {msg}" if msg else "⚠ WARNING")


# ── Startup banner ────────────────────────────────────────────────

def _arc_reactor() -> str:
    """The arc reactor ASCII art — centrepiece of the banner.

    Uses only single-width characters (ASCII / \\ | plus box-drawing)
    to avoid double-width rendering on Windows cmd.exe fonts.
    All rows 2-4 are 18 visible chars at indent 9 (center = 18).
    Rows 1 & 5 are 15 chars at indent 11 (center = 18.5).
    """
    if not COLOUR:
        return (
            "           +-------------+\n"
            "         +--/  -- || --  \\--+\n"
            "         |  / --- J --- \\  |\n"
            "         +--\\  -- || --  /--+\n"
            "           +-------------+"
        )
    # Single combined ANSI code for bold white J (no nesting)
    j = _c("1;97", "J")
    lines = []
    lines.append(red("           ╭") + dim("─────────────") + red("╮"))
    lines.append(red("         ╭─") + deep_red("╌╌╌") + stark_blue("/  ||  \\") + deep_red("╌╌╌") + red("─╮"))
    lines.append(red("         │") + deep_red("╌╌") + stark_blue(" / ── ") + j + stark_blue(" ── \\") + deep_red("╌╌") + red("│"))
    lines.append(red("         ╰─") + deep_red("╌╌╌") + stark_blue("\\  ||  /") + deep_red("╌╌╌") + red("─╯"))
    lines.append(red("           ╰") + dim("─────────────") + red("╯"))
    return "\n".join(lines)


def banner(session_id: str = "", backend: str = "", model: str = "",
           mode: str = "", num_ctx: int = 0, sys_tokens: int = 0,
           budget: int = 0, prompt_preview: str = "",
           server_log: str = "") -> str:
    """Build the full startup banner string."""

    lines = [""]
    lines.append(_arc_reactor())
    lines.append("")

    # Title
    title = "S O V E R E I G N   S H A R D"
    if COLOUR:
        # Alternate red and gold letters
        styled = ""
        colours = [red, gold]
        ci = 0
        for ch in title:
            if ch == " ":
                styled += " "
            else:
                styled += colours[ci % 2](ch)
                ci += 1
        lines.append(f"        {styled}")
    else:
        lines.append(f"        {title}")

    # Subtitle
    sub = '"Just A Rather Very Intelligent System"'
    lines.append(f"        {dim(sub) if COLOUR else sub}")
    lines.append("")

    # Divider
    divider = _divider()
    lines.append(divider)

    # Session info
    info_items = [
        ("Session", session_id),
        ("Backend", backend),
        ("Model", model),
        ("Mode", mode),
        ("Context", f"{num_ctx} tokens (budget {budget}, system ~{sys_tokens})"),
    ]

    for label, value in info_items:
        if value:
            l = red(f"  {label:>9}") if COLOUR else f"  {label:>9}"
            v = gold(value) if COLOUR else value
            lines.append(f"{l} │ {v}")

    if prompt_preview:
        l = red(f"  {'Prompt':>9}") if COLOUR else f"  {'Prompt':>9}"
        p = dim(prompt_preview + "...") if COLOUR else prompt_preview + "..."
        lines.append(f"{l} │ {p}")

    if server_log:
        l = red(f"  {'Log':>9}") if COLOUR else f"  {'Log':>9}"
        p = dim(server_log) if COLOUR else server_log
        lines.append(f"{l} │ {p}")

    lines.append(divider)

    # Commands
    cmds = "quit · /help · /tools · /plan · /memory · /optimize · /sandbox"
    lines.append(f"  {dim(cmds) if COLOUR else cmds}")

    lines.append(divider)

    # Ready message
    ready = "Systems online. Ready when you are."
    lines.append(f"\n  {stark_blue(ready) if COLOUR else ready}\n")

    return "\n".join(lines)


def _divider() -> str:
    """Standard divider line."""
    if COLOUR:
        return red("  ─") + dim("─" * 48) + red("─")
    return "  " + "-" * 50


# ── Section headers ───────────────────────────────────────────────

def section_header(text: str) -> str:
    """Styled section divider with text."""
    if COLOUR:
        return f"\n{dim('──')} {red(text)} {dim('──')}"
    return f"\n-- {text} --"


def step_header(step_id: str, goal: str, criteria: str = "", deps: str = "") -> str:
    """Styled step header for plan execution."""
    if COLOUR:
        parts = [f"\n{gold('=' * 50)}"]
        parts.append(f"{red(f'[STEP {step_id}]')} {white(goal)}")
        if criteria:
            parts.append(f"{dim('[CRITERIA]')} {criteria}{deps}")
        parts.append(gold("=" * 50))
    else:
        parts = [f"\n{'=' * 50}"]
        parts.append(f"[STEP {step_id}] {goal}")
        if criteria:
            parts.append(f"[CRITERIA] {criteria}{deps}")
        parts.append("=" * 50)
    return "\n".join(parts)


def plan_header(count: int) -> str:
    """Styled plan step count."""
    if COLOUR:
        return f"\n{red('[PLAN]')} {gold(f'{count} step(s)')}"
    return f"\n[PLAN] {count} step(s)"


def memory_status(entries: int, size_bytes: int) -> str:
    """One-line memory status."""
    size_kb = size_bytes / 1024
    if COLOUR:
        colour_fn = red if size_kb > 28 else gold if size_kb > 20 else stark_blue
        return f"{red('[MEMORY]')} {entries} entries, {colour_fn(f'{size_kb:.1f} KB')}"
    return f"[MEMORY] {entries} entries, {size_kb:.1f} KB"


def shutdown_msg(transcript_path: str) -> str:
    """Styled shutdown message and restore terminal defaults."""
    if COLOUR:
        msg = (
            f"\n  {dim('Session saved to')} {gold(transcript_path)}"
            f"\n  {red('▪')} {dim('Shard offline.')}\n"
        )
        # Restore terminal to default colours so cmd.exe isn't stuck on black
        msg += "\033[0m"
        return msg
    return f"\nSession saved to {transcript_path}\nShard offline."


def reflect_status(before: int, after: int) -> str:
    """Auto-reflection compression status."""
    if COLOUR:
        return f"{stark_blue('[AUTO-REFLECT]')} {gold(str(before))} → {green(str(after))} entries"
    return f"[AUTO-REFLECT] {before} → {after} entries"


def tool_result_header(tool_name: str, success: bool) -> str:
    """Header for tool result output."""
    if COLOUR:
        status = green("OK") if success else red("FAIL")
        return f"{gold('⚡')} {dim(f'[{tool_name}]')} {status}"
    status = "OK" if success else "FAIL"
    return f"[{tool_name}] {status}"


def code_block(text: str) -> str:
    """Style text as code output (stark blue)."""
    if COLOUR:
        return stark_blue(text)
    return text


def system_msg(text: str) -> str:
    """Framework/system message (red accent)."""
    if COLOUR:
        return red(f"▪ {text}")
    return f"[SYSTEM] {text}"


def user_echo(text: str) -> str:
    """Echo user input in gold."""
    if COLOUR:
        return gold(text)
    return text
