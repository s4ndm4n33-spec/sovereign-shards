"""Multi-file AST refactoring intelligence.

Cross-file analysis: import graphs, symbol tracking, dead code detection,
rename propagation, and circular dependency detection.

All pure-stdlib AST — no external deps. Operates on a project directory.
"""

from __future__ import annotations

import ast
import os
from dataclasses import dataclass, field
from pathlib import Path


# ── Data Structures ───────────────────────────────────────────────────


@dataclass
class Symbol:
    """A defined symbol (function, class, or variable) in a module."""
    name: str
    kind: str  # "function" | "class" | "variable" | "constant"
    file: str
    line: int

    @property
    def qualified(self) -> str:
        module = self.file.replace(os.sep, ".").removesuffix(".py")
        return f"{module}.{self.name}"


@dataclass
class Import:
    """An import relationship between two modules."""
    source: str       # Importing file (relative path)
    target: str       # Imported module/file
    names: list[str]  # Specific names imported (empty = whole module)
    line: int


@dataclass
class RefactorIssue:
    """A detected cross-file issue."""
    kind: str       # "dead_code" | "circular" | "shadow" | "missing" | "unused_import"
    file: str
    line: int
    message: str
    severity: str = "warning"


@dataclass
class ProjectMap:
    """Complete AST-level map of a Python project."""
    root: str
    files: list[str] = field(default_factory=list)
    symbols: list[Symbol] = field(default_factory=list)
    imports: list[Import] = field(default_factory=list)
    issues: list[RefactorIssue] = field(default_factory=list)
    parse_errors: list[str] = field(default_factory=list)

    def summary(self) -> str:
        lines = [
            f"Project Map: {len(self.files)} files, "
            f"{len(self.symbols)} symbols, "
            f"{len(self.imports)} imports",
        ]
        if self.issues:
            lines.append(f"\n{len(self.issues)} issue(s):")
            for iss in self.issues[:20]:
                lines.append(f"  [{iss.kind}] {iss.file}:{iss.line} — {iss.message}")
            if len(self.issues) > 20:
                lines.append(f"  ... and {len(self.issues) - 20} more")
        if self.parse_errors:
            lines.append(f"\n{len(self.parse_errors)} file(s) failed to parse:")
            for err in self.parse_errors[:5]:
                lines.append(f"  ✗ {err}")
        return "\n".join(lines)


# ── Scanner ───────────────────────────────────────────────────────────


SKIP_DIRS = {"__pycache__", ".git", ".venv", "venv", "node_modules",
             "models", "model-server", "Lib", "Scripts"}


def scan_project(root: str) -> ProjectMap:
    """Scan a Python project and build a complete symbol/import map."""
    root = os.path.abspath(root)
    pmap = ProjectMap(root=root)

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fname in sorted(filenames):
            if not fname.endswith(".py"):
                continue
            full = os.path.join(dirpath, fname)
            rel = os.path.relpath(full, root).replace("\\", "/")
            pmap.files.append(rel)

            try:
                source = Path(full).read_text(encoding="utf-8", errors="replace")
                tree = ast.parse(source, filename=rel)
            except SyntaxError as e:
                pmap.parse_errors.append(f"{rel}: {e}")
                continue

            _extract_symbols(tree, rel, pmap.symbols)
            _extract_imports(tree, rel, pmap.imports)

    # Analysis passes
    _detect_circular_imports(pmap)
    _detect_unused_imports(pmap)
    _detect_dead_symbols(pmap)
    _detect_shadows(pmap)

    return pmap


# ── Extraction ────────────────────────────────────────────────────────


def _extract_symbols(tree: ast.Module, filepath: str, out: list[Symbol]) -> None:
    """Extract top-level symbol definitions from an AST."""
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            out.append(Symbol(node.name, "function", filepath, node.lineno))
        elif isinstance(node, ast.ClassDef):
            out.append(Symbol(node.name, "class", filepath, node.lineno))
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    kind = "constant" if target.id.isupper() else "variable"
                    out.append(Symbol(target.id, kind, filepath, node.lineno))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            out.append(Symbol(node.target.id, "variable", filepath, node.lineno))


def _extract_imports(tree: ast.Module, filepath: str, out: list[Import]) -> None:
    """Extract import statements from an AST."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                out.append(Import(
                    source=filepath,
                    target=alias.name,
                    names=[],
                    line=node.lineno,
                ))
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            names = [alias.name for alias in node.names]
            out.append(Import(
                source=filepath,
                target=module,
                names=names,
                line=node.lineno,
            ))


# ── Analysis Passes ───────────────────────────────────────────────────


def _resolve_module(import_target: str, project_files: list[str]) -> str | None:
    """Try to resolve an import target to a project file path."""
    # "app.agent.graph" → "app/agent/graph.py"
    as_path = import_target.replace(".", "/") + ".py"
    if as_path in project_files:
        return as_path
    # Could be a package __init__
    as_init = import_target.replace(".", "/") + "/__init__.py"
    if as_init in project_files:
        return as_init
    return None


def _detect_circular_imports(pmap: ProjectMap) -> None:
    """Detect circular import chains using DFS."""
    # Build adjacency list (only for internal imports)
    adj: dict[str, set[str]] = {f: set() for f in pmap.files}
    for imp in pmap.imports:
        resolved = _resolve_module(imp.target, pmap.files)
        if resolved and resolved != imp.source:
            adj.setdefault(imp.source, set()).add(resolved)

    # DFS cycle detection
    WHITE, GRAY, BLACK = 0, 1, 2
    color: dict[str, int] = {f: WHITE for f in pmap.files}
    path: list[str] = []
    found_cycles: set[tuple[str, ...]] = set()

    def dfs(node: str) -> None:
        color[node] = GRAY
        path.append(node)
        for neighbor in adj.get(node, set()):
            if color.get(neighbor) == GRAY:
                # Found a cycle — extract it
                idx = path.index(neighbor)
                cycle = tuple(path[idx:])
                norm = tuple(sorted(cycle))
                if norm not in found_cycles:
                    found_cycles.add(norm)
                    cycle_str = " → ".join(cycle) + f" → {neighbor}"
                    pmap.issues.append(RefactorIssue(
                        "circular", node, 0,
                        f"Circular import chain: {cycle_str}",
                        severity="error",
                    ))
            elif color.get(neighbor, WHITE) == WHITE:
                dfs(neighbor)
        path.pop()
        color[node] = BLACK

    for f in pmap.files:
        if color.get(f, WHITE) == WHITE:
            dfs(f)


def _detect_unused_imports(pmap: ProjectMap) -> None:
    """Detect imports that aren't referenced in the importing file's AST."""
    for imp in pmap.imports:
        if not imp.names:
            continue  # whole-module imports are harder to check

        full_path = os.path.join(pmap.root, imp.source)
        try:
            source = Path(full_path).read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(source)
        except (SyntaxError, OSError):
            continue

        # Collect all Name references in the file
        used_names: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                used_names.add(node.id)
            elif isinstance(node, ast.Attribute):
                # For things like `contracts.AgentStep`
                if isinstance(node.value, ast.Name):
                    used_names.add(node.value.id)

        for name in imp.names:
            if name == "*":
                continue
            if name not in used_names:
                pmap.issues.append(RefactorIssue(
                    "unused_import", imp.source, imp.line,
                    f"'{name}' imported from '{imp.target}' but never used",
                ))


def _detect_dead_symbols(pmap: ProjectMap) -> None:
    """Detect symbols defined but never imported or referenced elsewhere."""
    # Build a set of all names that appear in import lists
    imported_names: set[str] = set()
    for imp in pmap.imports:
        imported_names.update(imp.names)

    # Check each non-private symbol
    for sym in pmap.symbols:
        if sym.name.startswith("_"):
            continue  # Private by convention
        if sym.kind == "constant":
            continue  # Constants often used dynamically
        if sym.name in ("main", "setup", "run", "app", "cli"):
            continue  # Entry points

        # Is it imported anywhere else?
        if sym.name in imported_names:
            continue

        # Is it referenced in any OTHER file?
        referenced = False
        for other_file in pmap.files:
            if other_file == sym.file:
                continue
            full_path = os.path.join(pmap.root, other_file)
            try:
                source = Path(full_path).read_text(encoding="utf-8", errors="replace")
                if sym.name in source:
                    referenced = True
                    break
            except OSError:
                continue

        if not referenced:
            pmap.issues.append(RefactorIssue(
                "dead_code", sym.file, sym.line,
                f"{sym.kind} '{sym.name}' defined but never imported/referenced elsewhere",
            ))


def _detect_shadows(pmap: ProjectMap) -> None:
    """Detect same-named symbols across different files (shadowing risk)."""
    by_name: dict[str, list[Symbol]] = {}
    for sym in pmap.symbols:
        if sym.name.startswith("_") or sym.kind in ("variable", "constant"):
            continue
        by_name.setdefault(sym.name, []).append(sym)

    for name, syms in by_name.items():
        if len(syms) > 1:
            files = [s.file for s in syms]
            # Only flag if the name is actually imported somewhere
            imported = any(
                name in imp.names for imp in pmap.imports
            )
            if imported:
                locations = ", ".join(f"{s.file}:{s.line}" for s in syms)
                pmap.issues.append(RefactorIssue(
                    "shadow", syms[0].file, syms[0].line,
                    f"'{name}' defined in multiple files: {locations}",
                ))


# ── Rename Helper ─────────────────────────────────────────────────────


def find_symbol_references(
    root: str,
    symbol_name: str,
    files: list[str] | None = None,
) -> list[tuple[str, int, str]]:
    """Find all references to a symbol across the project.

    Returns list of (file, line_number, line_text).
    Useful for rename refactoring — shows everywhere a name appears.
    """
    root = os.path.abspath(root)
    if files is None:
        pmap = scan_project(root)
        files = pmap.files

    refs: list[tuple[str, int, str]] = []
    for filepath in files:
        full = os.path.join(root, filepath)
        try:
            source = Path(full).read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(source, filename=filepath)
        except (SyntaxError, OSError):
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and node.id == symbol_name:
                # Get the actual line text
                lines = source.splitlines()
                line_text = lines[node.lineno - 1] if node.lineno <= len(lines) else ""
                refs.append((filepath, node.lineno, line_text.strip()))
            elif isinstance(node, ast.Attribute) and node.attr == symbol_name:
                lines = source.splitlines()
                line_text = lines[node.lineno - 1] if node.lineno <= len(lines) else ""
                refs.append((filepath, node.lineno, line_text.strip()))

    return refs
