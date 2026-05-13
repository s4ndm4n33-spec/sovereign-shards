# Sovereign Shards — Terminal UI Guide

> How the terminal UI works, how to fix alignment, and how to customize it.

---

## Overview

The entire terminal UI lives in one file: `app/ui.py` (341 lines). It uses **zero dependencies** — pure ANSI escape codes for colour and styling, compatible with Windows 10+ Command Prompt.

### Architecture

```
app/ui.py
├── Colour support detection  (_supports_colour, init)
├── Colour helpers             (stark_blue, gold, red, deep_red, white, dim, green, bold)
├── Prompt styling             (j_prefix, you_prompt, tool_tag, error_tag, etc.)
├── Startup banner             (_arc_reactor, banner, _divider)
└── Section headers            (section_header, step_header, plan_header, etc.)
```

**Key principle:** Every colour function wraps text in ANSI codes. If the terminal doesn't support colour, it returns plain text. The `COLOUR` flag is set once at import time.

---

## The Iron Man Colour Scheme

| Colour | ANSI Code | Function | Used For |
|--------|-----------|----------|----------|
| Stark Blue | `\033[94m` | `stark_blue()` | J's voice, code output, arc reactor |
| Gold | `\033[93m` | `gold()` | User input, headings, highlights |
| Bright Red | `\033[91m` | `red()` | System events, errors, outer frame |
| Dark Red | `\033[31m` | `deep_red()` | Subtle accents, dashed lines |
| Bright White | `\033[97m` | `white()` | Emphasis, bright accents |
| Dim Gray | `\033[90m` | `dim()` | Metadata, secondary info |
| Green | `\033[92m` | `green()` | Success indicators |

### How Colour Works

Every colour is applied by wrapping text in an ANSI start code and a reset code:

```python
def _c(code: str, text: str) -> str:
    if not COLOUR:
        return text
    return f"\033[{code}m{text}\033[0;40m"
```

The reset `\033[0;40m` restores to white-on-black (not the terminal default, which might be grey/white on Windows). This keeps the black background consistent.

### Background Setup

`init()` is called once at startup:

```python
sys.stdout.write("\033[40m")   # Set background to black
sys.stdout.write("\033[97m")   # Set default text to bright white
sys.stdout.write("\033[2J")    # Clear entire screen (fills with black)
sys.stdout.write("\033[H")     # Move cursor to top-left
```

---

## The Arc Reactor — How It's Built

The arc reactor is the centrepiece of the startup banner. Here's the current design, annotated:

```
Col:      0    5    10   15   20   25   30
          |    |    |    |    |    |    |

Line 1:            ╭─────────────╮           ← outer top (red + dim)
Line 2:          ╭─╌╌╌/  ||  \╌╌╌─╮         ← inner top (red + deep_red + blue)
Line 3:          │╌╌ / ── J ── \╌╌│          ← core (red + deep_red + blue + bold white J)
Line 4:          ╰─╌╌╌\  ||  /╌╌╌─╯         ← inner bottom (red + deep_red + blue)
Line 5:            ╰─────────────╯           ← outer bottom (red + dim)
```

### Character Map

| Line | Indent | Content Width | Content | Center Col |
|------|--------|---------------|---------|------------|
| 1 | 11 spaces | 15 chars | `╭` + 13× `─` + `╮` | 18.5 |
| 2 | 9 spaces | 18 chars | `╭─` + `╌╌╌` + `/  \|\|  \` + `╌╌╌` + `─╮` | 18.0 |
| 3 | 9 spaces | 18 chars | `│` + `╌╌` + ` / ── J ── \` + `╌╌` + `│` | 18.0 (J at col 18) |
| 4 | 9 spaces | 18 chars | `╰─` + `╌╌╌` + `\  \|\|  /` + `╌╌╌` + `─╯` | 18.0 |
| 5 | 11 spaces | 15 chars | `╰` + 13× `─` + `╯` | 18.5 |

### The Alignment Problem

**Lines 1 & 5 are centered at column 18.5. Lines 2–4 are centered at column 18.0.**

That's a half-character offset. The outer frame (top/bottom) is shifted slightly right compared to the inner frame. On most terminals it's nearly invisible, but in certain fonts or zoom levels it creates a visible drift.

Additionally, the `||` on lines 2 and 4 has its center at column 17.5 — another half-char offset from J at column 18.

### The Font Problem

Windows Command Prompt renders Unicode box-drawing characters (╭, ╮, ╌, etc.) at the same width as ASCII in most monospace fonts (Consolas, Cascadia Mono, Lucida Console). **But** some fonts or terminal emulators render them wider, which breaks alignment.

If you see the box characters appearing wider than letters, switch your terminal font:
- **Recommended:** Cascadia Mono, Consolas
- **Avoid:** Raster Fonts, SimSun, MS Gothic

To change font in Command Prompt: right-click title bar → Properties → Font.

---

## Fixed Arc Reactor

Here's a corrected version that aligns all centers at column 18:

```python
def _arc_reactor() -> str:
    if not COLOUR:
        return (
            "          ╭───────────────╮\n"
            "         ╭┤  / ── | ── \\  ├╮\n"
            "         │ ( ──── J ──── ) │\n"
            "         ╰┤  \\ ── | ── /  ├╯\n"
            "          ╰───────────────╯"
        )
    j = _c("1;97", "J")
    lines = []
    lines.append(red("          ╭") + dim("───────────────") + red("╮"))
    lines.append(red("         ╭") + deep_red("┤") + stark_blue("  / ── ") + dim("|") + stark_blue(" ── \\  ") + deep_red("├") + red("╮"))
    lines.append(red("         │") + stark_blue(" ( ──── ") + j + stark_blue(" ──── ) ") + red("│"))
    lines.append(red("         ╰") + deep_red("┤") + stark_blue("  \\ ── ") + dim("|") + stark_blue(" ── /  ") + deep_red("├") + red("╯"))
    lines.append(red("          ╰") + dim("───────────────") + red("╯"))
    return "\n".join(lines)
```

**Character count verification:**

```
Line 1: 10 spaces + ╭ + 15×─ + ╮ = 10 + 17 = 27    center: 10 + 8.5 = 18.5
Line 2:  9 spaces + ╭┤  / ── | ── \  ├╮ = 9 + 19    center: 9 + 9.5 = 18.5
Line 3:  9 spaces + │ ( ──── J ──── ) │ = 9 + 19     center: J at col 18
Line 4:  9 spaces + ╰┤  \ ── | ── /  ├╯ = 9 + 19    center: 9 + 9.5 = 18.5
Line 5: 10 spaces + ╰ + 15×─ + ╯ = 10 + 17 = 27    center: 10 + 8.5 = 18.5
```

Alternatively, here's a **pure-ASCII version** that guarantees alignment on any terminal, any font:

```python
def _arc_reactor() -> str:
    if not COLOUR:
        return (
            "          +---------------+\n"
            "         +|  / -- | -- \\  |+\n"
            "         | ( ---- J ---- ) |\n"
            "         +|  \\ -- | -- /  |+\n"
            "          +---------------+"
        )
    j = _c("1;97", "J")
    lines = []
    lines.append(red("          +") + dim("---------------") + red("+"))
    lines.append(red("         +") + deep_red("|") + stark_blue("  / -- ") + dim("|") + stark_blue(" -- \\  ") + deep_red("|") + red("+"))
    lines.append(red("         |") + stark_blue(" ( ---- ") + j + stark_blue(" ---- ) ") + red("|"))
    lines.append(red("         +") + deep_red("|") + stark_blue("  \\ -- ") + dim("|") + stark_blue(" -- /  ") + deep_red("|") + red("+"))
    lines.append(red("          +") + dim("---------------") + red("+"))
    return "\n".join(lines)
```

---

## How to Edit the Arc Reactor

### Step 1: Plan on Paper

Draw your design in a text editor first. Use a monospace font. Mark the center column — every line should have its visual center at the same column.

**Rules:**
- Every character = 1 column width (true for ASCII, risky for Unicode)
- Count visible characters, not ANSI codes (ANSI codes are invisible)
- Backslashes in Python strings need doubling: `\\` in code = `\` on screen

### Step 2: Map the Colours

For each line, decide which segments get which colour. Each segment becomes one function call:

```python
# This line: ╭─╌╌╌/  ||  \╌╌╌─╮
# Breaks into:
red("╭─")           # outer frame piece
deep_red("╌╌╌")     # dashed inner ring
stark_blue("/  ||  \\")  # reactor core
deep_red("╌╌╌")     # dashed inner ring
red("─╮")           # outer frame piece
```

### Step 3: Add Indentation

The indentation is raw spaces *inside* the first string of each line. It's NOT an ANSI code — just literal space characters.

```python
red("         ╭─")   # 9 spaces + characters
#   ^^^^^^^^^
#   these are literal spaces
```

### Step 4: Handle the J

The J is a special case — it's bold bright white (`1;97`), which requires a combined ANSI code. It's created once and inserted:

```python
j = _c("1;97", "J")
# Then in the line:
stark_blue(" / ── ") + j + stark_blue(" ── \\")
```

### Step 5: Verify Alignment

After any edit, count visible characters per line (exclude ANSI codes). Use this Python snippet to strip ANSI and check:

```python
import re

def strip_ansi(text):
    return re.sub(r'\033\[[0-9;]*m', '', text)

# Test each line
for line in reactor_lines:
    clean = strip_ansi(line)
    print(f"len={len(clean):2d}  |{clean}|")
```

Run this to see exactly what the terminal will render, with widths.

---

## Modifying Other UI Elements

### Change the Iron Man Colours

To change a colour, modify the ANSI code in the helper function. For example, to make "Stark Blue" into a true cyan:

```python
def stark_blue(text: str) -> str:
    return _c("96", text)  # Changed from 94 (blue) to 96 (cyan)
```

**Common ANSI colour codes:**

| Code | Colour |
|------|--------|
| 30/90 | Black / Dark Gray |
| 31/91 | Red / Bright Red |
| 32/92 | Green / Bright Green |
| 33/93 | Yellow (Gold) / Bright Yellow |
| 34/94 | Blue / Bright Blue |
| 35/95 | Magenta / Bright Magenta |
| 36/96 | Cyan / Bright Cyan |
| 37/97 | White / Bright White |

Codes 30–37 are normal; 90–97 are bright variants.

### Change the User Prompt

```python
def you_prompt() -> str:
    return f"\n{red('▶')} {gold('You')}: "
```

Change `'▶'` to any character. Change `'You'` to any label.

### Change the Divider

```python
def _divider() -> str:
    if COLOUR:
        return red("  ─") + dim("─" * 48) + red("─")
    return "  " + "-" * 50
```

Change `48` to adjust width. The red bookends (`─`) are decorative.

### Change the Title

In the `banner()` function, the title is:

```python
title = "S O V E R E I G N   S H A R D"
```

Characters are coloured alternating red/gold. Change the string to change the title. The letter-alternation logic is automatic.

### Change the Subtitle

```python
sub = '"Just A Rather Very Intelligent System"'
```

Change the string directly. It's rendered in dim gray.

---

## Adding New UI Elements

### New Status Line

```python
def my_status(label: str, value: str) -> str:
    if COLOUR:
        return f"{red(label)} {gold(value)}"
    return f"{label} {value}"
```

### New Section Divider

```python
def my_divider(text: str) -> str:
    if COLOUR:
        return f"\n{dim('──')} {gold(text)} {dim('──')}"
    return f"\n-- {text} --"
```

### Always Follow This Pattern

Every UI function must:
1. Check `if COLOUR:` before using ANSI codes
2. Provide a plain-text fallback
3. Use the `_c()` helper or colour functions (never raw ANSI strings)
4. End with `{_RESET}` via the colour functions (handled automatically by `_c()`)

---

## Troubleshooting

### Black background doesn't fill the whole screen

`init()` must be called before any output. Check that `run.py` or `chat.py` calls `ui.init()` early.

### Colours look wrong or don't appear

- Make sure you're using **Command Prompt** (cmd.exe), not PowerShell ISE
- Windows Terminal and cmd.exe on Win 10+ support ANSI natively
- If using PowerShell, ANSI support is automatic on Windows Terminal
- Set `FORCE_COLOR=1` environment variable to override detection

### Box-drawing characters render as ? or □

Your terminal font doesn't support Unicode. Switch to Cascadia Mono, Consolas, or another modern monospace font.

### The reactor looks different in VS Code terminal vs cmd.exe

VS Code's integrated terminal uses a different font renderer. Alignment may differ. The primary target is cmd.exe (per the project's USB-portable design). Test in cmd.exe first.

---

## Quick Reference: File Locations

| What | Where |
|------|-------|
| All UI code | `app/ui.py` |
| Banner called from | `app/chat.py` (look for `ui.banner(...)`) |
| Colour init called from | `run.py` or `app/chat.py` (look for `ui.init()`) |
| Icon file | `assets/icon.ico` |
| Prompt template | `prompts/J-chat-template.jinja` |
| System prompt | `prompts/J-system.txt` |

---

*Viktor*
*May 12, 2026*
