# Copyright (c) 2024-2026 Reed Richards (s4ndm4n33). Licensed under BSL 1.1.
"""Safe calculator — evaluates arithmetic without exec/eval.

Usage:
    python calc.py <expression>

Examples:
    python calc.py "47 * 13"          → 611
    python calc.py "sqrt(144) + 1"    → 13.0
    python calc.py "2 ** 10"          → 1024
    python calc.py "round(22/7, 4)"   → 3.1429

Supports: + - * / // % **  parentheses  integers  floats
Built-in: abs, round, min, max, sqrt, pow, log, log2, log10,
          sin, cos, tan, pi, e, ceil, floor

Stdlib only. No dependencies. No exec/eval — uses AST node walking.
"""

from __future__ import annotations

import ast
import math
import operator
import sys

# ── Allowed operations ──────────────────────────────────────────────

_BINARY_OPS = {
    ast.Add:      operator.add,
    ast.Sub:      operator.sub,
    ast.Mult:     operator.mul,
    ast.Div:      operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod:      operator.mod,
    ast.Pow:      operator.pow,
}

_UNARY_OPS = {
    ast.UAdd:  operator.pos,
    ast.USub:  operator.neg,
}

# Safe math functions (name → callable)
_FUNCTIONS = {
    "abs":   abs,
    "round": round,
    "min":   min,
    "max":   max,
    "sqrt":  math.sqrt,
    "pow":   pow,
    "log":   math.log,
    "log2":  math.log2,
    "log10": math.log10,
    "sin":   math.sin,
    "cos":   math.cos,
    "tan":   math.tan,
    "ceil":  math.ceil,
    "floor": math.floor,
    "factorial": math.factorial,
}

# Safe constants
_CONSTANTS = {
    "pi": math.pi,
    "e":  math.e,
    "tau": math.tau,
    "inf": math.inf,
}


# ── AST evaluator ──────────────────────────────────────────────────

class CalcError(Exception):
    """Raised for invalid or disallowed expressions."""


def _eval_node(node: ast.AST) -> float | int:
    """Recursively evaluate an AST node — only safe math ops allowed."""

    # Numbers: 42, 3.14
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return node.value
        raise CalcError(f"Unsupported constant type: {type(node.value).__name__}")

    # Unary: -x, +x
    if isinstance(node, ast.UnaryOp):
        op_fn = _UNARY_OPS.get(type(node.op))
        if op_fn is None:
            raise CalcError(f"Unsupported unary operator: {type(node.op).__name__}")
        return op_fn(_eval_node(node.operand))

    # Binary: x + y, x * y, etc.
    if isinstance(node, ast.BinOp):
        op_fn = _BINARY_OPS.get(type(node.op))
        if op_fn is None:
            raise CalcError(f"Unsupported operator: {type(node.op).__name__}")
        left = _eval_node(node.left)
        right = _eval_node(node.right)
        # Guard against huge exponents (DoS)
        if isinstance(node.op, ast.Pow) and isinstance(right, (int, float)) and right > 10000:
            raise CalcError("Exponent too large (max 10000)")
        return op_fn(left, right)

    # Function calls: sqrt(x), round(x, 2), min(a, b, c)
    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name):
            raise CalcError("Only simple function names allowed")
        name = node.func.id
        func = _FUNCTIONS.get(name)
        if func is None:
            raise CalcError(f"Unknown function: {name}")
        args = [_eval_node(a) for a in node.args]
        try:
            return func(*args)
        except Exception as exc:
            raise CalcError(f"{name}() error: {exc}")

    # Named constants: pi, e
    if isinstance(node, ast.Name):
        val = _CONSTANTS.get(node.id)
        if val is not None:
            return val
        raise CalcError(f"Unknown name: {node.id}")

    raise CalcError(f"Unsupported expression: {ast.dump(node)}")


def safe_eval(expression: str) -> float | int:
    """Parse and evaluate a math expression safely.

    Only allows arithmetic operators, numeric literals, whitelisted
    functions, and whitelisted constants. No exec, no eval, no imports.
    """
    expression = expression.strip()
    if not expression:
        raise CalcError("Empty expression")

    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise CalcError(f"Syntax error: {exc}")

    result = _eval_node(tree.body)

    # Clean up float display: 611.0 → 611
    if isinstance(result, float) and result == int(result) and abs(result) < 1e15:
        return int(result)
    return result


# ── Natural language preprocessor ───────────────────────────────────

import re

# Word-to-operator mapping for natural language math
_WORD_OPS = [
    (r"\btimes\b",          "*"),
    (r"\bmultiplied\s+by\b", "*"),
    (r"\bdivided\s+by\b",   "/"),
    (r"\bover\b",           "/"),
    (r"\bplus\b",           "+"),
    (r"\bminus\b",          "-"),
    (r"\bmod\b",            "%"),
    (r"\bmodulo\b",         "%"),
    (r"\bto\s+the\s+power\s+of\b", "**"),
    (r"\braised\s+to\b",    "**"),
    (r"\bsquared\b",        "**2"),
    (r"\bcubed\b",          "**3"),
]

# Strip common question framing
_STRIP_PATTERNS = [
    r"^what\s+is\s+",
    r"^what\'s\s+",
    r"^calculate\s+",
    r"^compute\s+",
    r"^solve\s+",
    r"^evaluate\s+",
    r"^how\s+much\s+is\s+",
    r"\?+$",
    r"^=\s*",
]


def normalize_math(text: str) -> str:
    """Convert natural language math to an evaluable expression.

    '47 times 13'          → '47 * 13'
    'what is 100 plus 50?' → '100 + 50'
    'sqrt of 144'          → 'sqrt(144)'
    """
    s = text.strip()

    # Strip question framing
    for pat in _STRIP_PATTERNS:
        s = re.sub(pat, "", s, flags=re.IGNORECASE).strip()

    # Replace word operators with symbols
    for pat, repl in _WORD_OPS:
        s = re.sub(pat, repl, s, flags=re.IGNORECASE)

    # "sqrt of X" → "sqrt(X)"
    s = re.sub(r"(\w+)\s+of\s+(\d[\d.]*)", r"\1(\2)", s, flags=re.IGNORECASE)

    # Collapse whitespace
    s = re.sub(r"\s+", " ", s).strip()

    return s


# ── CLI entry point ─────────────────────────────────────────────────

def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python calc.py <expression>")
        print("Examples:")
        print('  python calc.py "47 * 13"')
        print('  python calc.py "sqrt(144) + 1"')
        print('  python calc.py "47 times 13"')
        sys.exit(1)

    raw = " ".join(sys.argv[1:])
    expr = normalize_math(raw)

    try:
        result = safe_eval(expr)
        # Show the normalised expression if it differs from input
        if expr != raw.strip():
            print(f"{raw.strip()} = {expr} = {result}")
        else:
            print(f"{expr} = {result}")
    except CalcError as exc:
        print(f"Error: {exc}")
        sys.exit(1)
    except Exception as exc:
        print(f"Unexpected error: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
