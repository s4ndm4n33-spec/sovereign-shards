# Copyright (c) 2024-2026 Reed Richards (s4ndm4n33). Licensed under BSL 1.1.
"""Deterministic AST transformations for the Five Masters Code Optimizer.

Each transform takes an AST and an Issue, returns a modified AST.
Pure stdlib. No string manipulation. No regex on source code.

Transforms:
  fix_range_len        (Korotkevich) — range(len(x)) → enumerate(x)
  fix_bare_except      (Torvalds)    — except: pass → except Exception + log
  fix_silent_except    (Torvalds)    — except Exception (no log) → + log
  fix_mutable_default  (Carmack)     — def f(x=[]) → def f(x=None) + guard
  fix_unguarded_io     (Hamilton)    — open() outside try → wrap in try
  fix_naming_funcs     (Ritchie)     — camelCase functions → snake_case
  fix_naming_classes   (Ritchie)     — snake_case classes  → PascalCase
"""

from __future__ import annotations

import ast
import re as _re
import copy
import textwrap
from dataclasses import dataclass
from typing import Optional


@dataclass
class TransformResult:
    """Result of a single AST transformation."""
    applied: bool
    description: str
    master: str
    line: int
    original_node: Optional[ast.AST] = None


# ── Korotkevich: Efficiency ───────────────────────────────────────────


class _RangeLenRewriter(ast.NodeTransformer):
    """Rewrite `for i in range(len(x)): ... x[i] ...` to enumerate."""

    def __init__(self) -> None:
        self.changes: list[TransformResult] = []

    def visit_For(self, node: ast.For) -> ast.AST:
        self.generic_visit(node)

        # Match: for VAR in range(len(COLLECTION))
        if not (isinstance(node.iter, ast.Call)
                and isinstance(node.iter.func, ast.Name)
                and node.iter.func.id == "range"
                and len(node.iter.args) == 1):
            return node

        arg = node.iter.args[0]
        if not (isinstance(arg, ast.Call)
                and isinstance(arg.func, ast.Name)
                and arg.func.id == "len"
                and len(arg.args) == 1):
            return node

        if not isinstance(node.target, ast.Name):
            return node

        idx_name = node.target.id
        collection = arg.args[0]

        # Determine a safe item variable name
        if isinstance(collection, ast.Name):
            item_name = f"_{collection.id}_item"
        else:
            item_name = "_item"

        # Rewrite the for-loop target to a tuple (idx, item)
        new_target = ast.Tuple(
            elts=[
                ast.Name(id=idx_name, ctx=ast.Store()),
                ast.Name(id=item_name, ctx=ast.Store()),
            ],
            ctx=ast.Store(),
        )

        # Rewrite the iterator to enumerate(collection)
        new_iter = ast.Call(
            func=ast.Name(id="enumerate", ctx=ast.Load()),
            args=[copy.deepcopy(collection)],
            keywords=[],
        )

        # Rewrite body: replace collection[idx] with item_name
        new_body = _replace_subscript(node.body, collection, idx_name, item_name)

        new_node = ast.For(
            target=new_target,
            iter=new_iter,
            body=new_body,
            orelse=node.orelse,
        )
        ast.copy_location(new_node, node)
        ast.fix_missing_locations(new_node)

        self.changes.append(TransformResult(
            applied=True,
            description=f"range(len()) → enumerate()",
            master="korotkevich",
            line=node.lineno,
        ))
        return new_node


def _replace_subscript(
    nodes: list[ast.stmt],
    collection: ast.AST,
    idx_name: str,
    item_name: str,
) -> list[ast.stmt]:
    """Replace collection[idx] with item_name in a list of statements."""
    replacer = _SubscriptReplacer(collection, idx_name, item_name)
    return [replacer.visit(copy.deepcopy(n)) for n in nodes]


class _SubscriptReplacer(ast.NodeTransformer):
    """Replace collection[idx_var] → item_var."""

    def __init__(self, collection: ast.AST, idx_name: str, item_name: str):
        self.collection = collection
        self.idx_name = idx_name
        self.item_name = item_name

    def visit_Subscript(self, node: ast.Subscript) -> ast.AST:
        self.generic_visit(node)

        # Match collection[idx_name]
        if (isinstance(node.slice, ast.Name)
                and node.slice.id == self.idx_name
                and isinstance(self.collection, ast.Name)
                and isinstance(node.value, ast.Name)
                and node.value.id == self.collection.id):
            replacement = ast.Name(id=self.item_name, ctx=node.ctx)
            ast.copy_location(replacement, node)
            return replacement

        return node


def fix_range_len(tree: ast.Module) -> tuple[ast.Module, list[TransformResult]]:
    """Apply range(len()) → enumerate() transformation."""
    rewriter = _RangeLenRewriter()
    new_tree = rewriter.visit(copy.deepcopy(tree))
    ast.fix_missing_locations(new_tree)
    return new_tree, rewriter.changes


# ── Torvalds: Error Handling ──────────────────────────────────────────


class _BareExceptRewriter(ast.NodeTransformer):
    """Rewrite bare except: pass → except Exception as e: log + raise."""

    def __init__(self) -> None:
        self.changes: list[TransformResult] = []

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> ast.AST:
        self.generic_visit(node)

        if node.type is not None:
            return node  # Not a bare except

        # Check if it's just `pass`
        is_pass = (len(node.body) == 1 and isinstance(node.body[0], ast.Pass))

        if is_pass:
            # except: pass → except Exception as e: logging + raise
            new_body = _make_log_and_raise("e")
            desc = "bare except: pass → except Exception + log + raise"
        else:
            # Bare except with actual code — just add the type
            new_body = node.body
            desc = "bare except: → except Exception:"

        new_handler = ast.ExceptHandler(
            type=ast.Name(id="Exception", ctx=ast.Load()),
            name="e",
            body=new_body,
        )
        ast.copy_location(new_handler, node)
        ast.fix_missing_locations(new_handler)

        self.changes.append(TransformResult(
            applied=True, description=desc,
            master="torvalds", line=node.lineno,
        ))
        return new_handler


class _SilentExceptRewriter(ast.NodeTransformer):
    """Add logging to except Exception blocks that silently swallow errors."""

    def __init__(self) -> None:
        self.changes: list[TransformResult] = []

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> ast.AST:
        self.generic_visit(node)

        # Only target `except Exception` (with explicit type)
        if not (node.type and isinstance(node.type, ast.Name)
                and node.type.id == "Exception"):
            return node

        # Check if already has raise or logging
        has_raise = any(isinstance(n, ast.Raise) for n in ast.walk(node))
        has_log = False
        for n in ast.walk(node):
            if isinstance(n, ast.Call):
                if isinstance(n.func, ast.Attribute):
                    if n.func.attr in ("error", "warning", "exception", "critical"):
                        has_log = True
                        break
                if isinstance(n.func, ast.Name) and n.func.id == "print":
                    has_log = True
                    break

        if has_raise or has_log:
            return node  # Already handled

        # Prepend a logging call
        exc_name = node.name or "e"
        if not node.name:
            node.name = "e"

        log_stmt = _make_log_stmt(exc_name)
        node.body.insert(0, log_stmt)
        ast.fix_missing_locations(node)

        self.changes.append(TransformResult(
            applied=True,
            description="silent except Exception → added error logging",
            master="torvalds",
            line=node.lineno,
        ))
        return node


def _make_log_and_raise(exc_name: str) -> list[ast.stmt]:
    """Generate: print(f"Error: {e}"); raise"""
    log = _make_log_stmt(exc_name)
    raise_stmt = ast.Raise(exc=None, cause=None)
    return [log, raise_stmt]


def _make_log_stmt(exc_name: str) -> ast.stmt:
    """Generate: print(f"Error: {exc_name}")"""
    return ast.Expr(value=ast.Call(
        func=ast.Name(id="print", ctx=ast.Load()),
        args=[ast.JoinedStr(values=[
            ast.Constant(value="Error: "),
            ast.FormattedValue(
                value=ast.Name(id=exc_name, ctx=ast.Load()),
                conversion=-1, format_spec=None,
            ),
        ])],
        keywords=[],
    ))


def fix_bare_except(tree: ast.Module) -> tuple[ast.Module, list[TransformResult]]:
    """Fix bare except clauses."""
    rewriter = _BareExceptRewriter()
    new_tree = rewriter.visit(copy.deepcopy(tree))
    ast.fix_missing_locations(new_tree)
    return new_tree, rewriter.changes


def fix_silent_except(tree: ast.Module) -> tuple[ast.Module, list[TransformResult]]:
    """Add logging to silent except Exception blocks."""
    rewriter = _SilentExceptRewriter()
    new_tree = rewriter.visit(copy.deepcopy(tree))
    ast.fix_missing_locations(new_tree)
    return new_tree, rewriter.changes


# ── Carmack: Performance ─────────────────────────────────────────────


class _MutableDefaultRewriter(ast.NodeTransformer):
    """Rewrite mutable default args: def f(x=[]) → def f(x=None) + guard."""

    def __init__(self) -> None:
        self.changes: list[TransformResult] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST:
        self.generic_visit(node)
        changed = False

        guards: list[ast.stmt] = []
        args = node.args

        # Process positional defaults
        # defaults align to the END of args.args
        offset = len(args.args) - len(args.defaults)
        for i, default in enumerate(args.defaults):
            if isinstance(default, (ast.List, ast.Dict, ast.Set)):
                param = args.args[offset + i]
                mutable_type = type(default).__name__  # List, Dict, Set
                args.defaults[i] = ast.Constant(value=None)
                guard = _make_none_guard(param.arg, mutable_type)
                guards.append(guard)
                changed = True

        # Process keyword defaults
        for i, default in enumerate(args.kw_defaults):
            if default and isinstance(default, (ast.List, ast.Dict, ast.Set)):
                param = args.kwonlyargs[i]
                mutable_type = type(default).__name__
                args.kw_defaults[i] = ast.Constant(value=None)
                guard = _make_none_guard(param.arg, mutable_type)
                guards.append(guard)
                changed = True

        if changed:
            node.body = guards + node.body
            ast.fix_missing_locations(node)
            self.changes.append(TransformResult(
                applied=True,
                description=f"mutable default arg in {node.name}() → None + guard",
                master="carmack",
                line=node.lineno,
            ))

        return node

    visit_AsyncFunctionDef = visit_FunctionDef


def _make_none_guard(param_name: str, mutable_type: str) -> ast.stmt:
    """Generate: if param is None: param = <empty mutable>"""
    factory = {"List": ast.List(elts=[], ctx=ast.Load()),
               "Dict": ast.Dict(keys=[], values=[]),
               "Set": ast.Call(func=ast.Name(id="set", ctx=ast.Load()),
                               args=[], keywords=[])}
    return ast.If(
        test=ast.Compare(
            left=ast.Name(id=param_name, ctx=ast.Load()),
            ops=[ast.Is()],
            comparators=[ast.Constant(value=None)],
        ),
        body=[ast.Assign(
            targets=[ast.Name(id=param_name, ctx=ast.Store())],
            value=factory.get(mutable_type, ast.List(elts=[], ctx=ast.Load())),
            lineno=0,
        )],
        orelse=[],
    )


def fix_mutable_default(tree: ast.Module) -> tuple[ast.Module, list[TransformResult]]:
    """Fix mutable default arguments."""
    rewriter = _MutableDefaultRewriter()
    new_tree = rewriter.visit(copy.deepcopy(tree))
    ast.fix_missing_locations(new_tree)
    return new_tree, rewriter.changes


# ── Hamilton: Fault Tolerance ─────────────────────────────────────────


class _UnguardedIORewriter(ast.NodeTransformer):
    """Wrap unguarded I/O calls (open, urlopen, connect) in try/except."""

    def __init__(self, try_ranges: list[tuple[int, int]]) -> None:
        self.try_ranges = try_ranges
        self.changes: list[TransformResult] = []

    def visit_Expr(self, node: ast.Expr) -> ast.AST:
        return self._maybe_wrap(node)

    def visit_Assign(self, node: ast.Assign) -> ast.AST:
        return self._maybe_wrap(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> ast.AST:
        return self._maybe_wrap(node)

    def _maybe_wrap(self, node: ast.stmt) -> ast.AST:
        """Wrap the statement in try/except if it contains an unguarded I/O call."""
        if self._is_guarded(node.lineno):
            return node

        has_io = False
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                if isinstance(child.func, ast.Name) and child.func.id == "open":
                    has_io = True
                    break
                if isinstance(child.func, ast.Attribute):
                    if child.func.attr in ("urlopen", "connect", "send", "recv"):
                        has_io = True
                        break

        if not has_io:
            return node

        # Wrap in try/except OSError
        wrapped = ast.Try(
            body=[copy.deepcopy(node)],
            handlers=[ast.ExceptHandler(
                type=ast.Name(id="OSError", ctx=ast.Load()),
                name="e",
                body=_make_log_and_raise("e"),
            )],
            orelse=[],
            finalbody=[],
        )
        ast.copy_location(wrapped, node)
        ast.fix_missing_locations(wrapped)

        self.changes.append(TransformResult(
            applied=True,
            description="unguarded I/O → wrapped in try/except OSError",
            master="hamilton",
            line=node.lineno,
        ))
        return wrapped

    def _is_guarded(self, lineno: int) -> bool:
        return any(s <= lineno <= e for s, e in self.try_ranges)


def _get_try_ranges(tree: ast.Module) -> list[tuple[int, int]]:
    """Get line ranges of all try blocks in the AST."""
    ranges = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Try):
            end = max(
                (getattr(n, "lineno", node.lineno) for n in ast.walk(node)),
                default=node.lineno,
            )
            ranges.append((node.lineno, end))
    return ranges


def fix_unguarded_io(tree: ast.Module) -> tuple[ast.Module, list[TransformResult]]:
    """Wrap unguarded I/O operations in try/except."""
    try_ranges = _get_try_ranges(tree)
    rewriter = _UnguardedIORewriter(try_ranges)
    new_tree = copy.deepcopy(tree)

    # Only transform top-level and function-body statements
    new_body = []
    for node in new_tree.body:
        result = rewriter.visit(node)
        new_body.append(result)
    new_tree.body = new_body
    ast.fix_missing_locations(new_tree)
    return new_tree, rewriter.changes


# ── Ritchie: Clarity ──────────────────────────────────────────────────

# Naming convention helpers (pure-stdlib, no external deps)

def _camel_to_snake(name: str) -> str:
    """Convert camelCase or PascalCase to snake_case."""
    # Insert _ before sequences like 'aB' → 'a_B', or 'ABc' → 'A_Bc'
    s1 = _re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", name)
    s2 = _re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", s1)
    return s2.lower()


def _snake_to_pascal(name: str) -> str:
    """Convert snake_case to PascalCase."""
    return "".join(part.capitalize() for part in name.split("_") if part)


def _is_camel_case_func(name: str) -> bool:
    """Return True if name looks like camelCase (not snake_case or dunder)."""
    if name.startswith("_"):
        return False
    if "_" in name:
        return False
    if name.isupper():
        return False
    if name == name.lower():
        return False
    # Has at least one uppercase after a lowercase → camelCase
    return bool(_re.search(r"[a-z][A-Z]", name))


def _is_snake_case_class(name: str) -> bool:
    """Return True if name uses snake_case (not PascalCase) for a class."""
    if "_" not in name:
        return False
    if name.startswith("_"):
        return False
    return name[0].islower()


class _FuncNameRewriter(ast.NodeTransformer):
    """Rename camelCase function definitions and all call-sites to snake_case."""

    def __init__(self) -> None:
        self.rename_map: dict[str, str] = {}  # old → new
        self.changes: list[TransformResult] = []

    # --- Pass 1: collect renames from FunctionDef ---
    def scan(self, tree: ast.Module) -> None:
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if _is_camel_case_func(node.name):
                    new_name = _camel_to_snake(node.name)
                    if new_name != node.name:
                        self.rename_map[node.name] = new_name

    # --- Pass 2: apply renames everywhere ---
    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST:
        self.generic_visit(node)
        if node.name in self.rename_map:
            old = node.name
            node.name = self.rename_map[old]
            self.changes.append(TransformResult(
                applied=True,
                description=f"def {old}() → def {node.name}()",
                master="ritchie",
                line=node.lineno,
            ))
        return node

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Name(self, node: ast.Name) -> ast.AST:
        if node.id in self.rename_map:
            node.id = self.rename_map[node.id]
        return node

    def visit_Attribute(self, node: ast.Attribute) -> ast.AST:
        self.generic_visit(node)
        if node.attr in self.rename_map:
            node.attr = self.rename_map[node.attr]
        return node


class _ClassNameRewriter(ast.NodeTransformer):
    """Rename snake_case class definitions and all references to PascalCase."""

    def __init__(self) -> None:
        self.rename_map: dict[str, str] = {}
        self.changes: list[TransformResult] = []

    def scan(self, tree: ast.Module) -> None:
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                if _is_snake_case_class(node.name):
                    new_name = _snake_to_pascal(node.name)
                    if new_name != node.name:
                        self.rename_map[node.name] = new_name

    def visit_ClassDef(self, node: ast.ClassDef) -> ast.AST:
        self.generic_visit(node)
        if node.name in self.rename_map:
            old = node.name
            node.name = self.rename_map[old]
            self.changes.append(TransformResult(
                applied=True,
                description=f"class {old} → class {node.name}",
                master="ritchie",
                line=node.lineno,
            ))
        return node

    def visit_Name(self, node: ast.Name) -> ast.AST:
        if node.id in self.rename_map:
            node.id = self.rename_map[node.id]
        return node

    def visit_Attribute(self, node: ast.Attribute) -> ast.AST:
        self.generic_visit(node)
        if node.attr in self.rename_map:
            node.attr = self.rename_map[node.attr]
        return node


def fix_naming_funcs(tree: ast.Module) -> tuple[ast.Module, list[TransformResult]]:
    """Rename camelCase functions to snake_case (Ritchie: Clarity)."""
    rewriter = _FuncNameRewriter()
    new_tree = copy.deepcopy(tree)
    rewriter.scan(new_tree)
    if not rewriter.rename_map:
        return new_tree, []
    new_tree = rewriter.visit(new_tree)
    ast.fix_missing_locations(new_tree)
    return new_tree, rewriter.changes


def fix_naming_classes(tree: ast.Module) -> tuple[ast.Module, list[TransformResult]]:
    """Rename snake_case classes to PascalCase (Ritchie: Clarity)."""
    rewriter = _ClassNameRewriter()
    new_tree = copy.deepcopy(tree)
    rewriter.scan(new_tree)
    if not rewriter.rename_map:
        return new_tree, []
    new_tree = rewriter.visit(new_tree)
    ast.fix_missing_locations(new_tree)
    return new_tree, rewriter.changes


# ── Master Pipeline ──────────────────────────────────────────────────


# Ordered list of all deterministic transforms
DETERMINISTIC_TRANSFORMS = [
    ("korotkevich", "range_len", fix_range_len),
    ("torvalds", "bare_except", fix_bare_except),
    ("torvalds", "silent_except", fix_silent_except),
    ("carmack", "mutable_default", fix_mutable_default),
    ("hamilton", "unguarded_io", fix_unguarded_io),
    ("ritchie", "naming_funcs", fix_naming_funcs),
    ("ritchie", "naming_classes", fix_naming_classes),
]


def apply_all_deterministic(
    tree: ast.Module,
) -> tuple[ast.Module, list[TransformResult]]:
    """Apply all deterministic transforms in sequence.

    Each transform operates on the output of the previous one.
    If any transform produces an unparseable AST, it is reverted.
    """
    all_results: list[TransformResult] = []
    current = tree

    for master, name, transform_fn in DETERMINISTIC_TRANSFORMS:
        try:
            new_tree, results = transform_fn(current)
            # Verify the result is still valid
            ast.parse(ast.unparse(new_tree))
            current = new_tree
            all_results.extend(results)
        except (SyntaxError, ValueError, TypeError) as e:
            # Transform broke the AST — skip it
            all_results.append(TransformResult(
                applied=False,
                description=f"{name}: reverted — {e}",
                master=master,
                line=0,
            ))

    return current, all_results
