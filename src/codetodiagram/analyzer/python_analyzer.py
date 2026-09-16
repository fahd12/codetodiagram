"""Python AST analyzer that builds a pruned call graph."""

from __future__ import annotations

import ast
import fnmatch
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from codetodiagram.analyzer.base import LanguageAnalyzer
from codetodiagram.analyzer.call_graph import CallGraph
from codetodiagram.analyzer.entry_points import detect_entry_points
from codetodiagram.models import Graph, Node, stable_node_id

_SELF_NAMES = frozenset({"self", "cls"})


@dataclass(frozen=True)
class _ImportRef:
    """Where a local name was imported from."""

    module: str
    name: str | None


@dataclass(frozen=True)
class _Symbol:
    """A function or method discovered in a module."""

    qualified_name: str
    short_name: str
    file_display: str
    line: int
    node: ast.FunctionDef | ast.AsyncFunctionDef
    module: str
    class_name: str | None


@dataclass
class _ParsedModule:
    """One successfully parsed source file."""

    path: Path
    display: str
    module: str
    tree: ast.Module
    imports: dict[str, _ImportRef]


class PythonAnalyzer(LanguageAnalyzer):
    """Walk Python files, resolve calls, and prune from entry points."""

    def __init__(
        self,
        *,
        max_depth: int = 10,
        entry_filter: Sequence[str] | None = None,
        exclude: Sequence[str] | None = None,
        verbose: bool = False,
    ) -> None:
        """Create an analyzer.

        Args:
            max_depth: Maximum call-graph hops from an entry point.
            entry_filter: If set, only these entry names (or qualified names).
            exclude: Glob patterns matched against paths relative to the root.
            verbose: Write progress to stderr.
        """
        self._max_depth = max_depth
        self._entry_filter = tuple(entry_filter) if entry_filter else ()
        self._exclude = tuple(exclude) if exclude else ()
        self._verbose = verbose
        self._symbols: dict[str, _Symbol] = {}
        self._by_module_name: dict[tuple[str, str], list[_Symbol]] = {}
        self._qnames: dict[str, str] = {}

    def analyze(self, path: Path) -> Graph:
        """Analyze a file or directory and return the pruned call graph.

        Args:
            path: File or directory to analyze.

        Returns:
            Graph reachable from detected entry points.
        """
        root = path.resolve()
        files = self._collect_files(root)
        self._log(f"scanning {root} ({len(files)} Python files)")
        modules = self._parse_files(files, root)
        for parsed in modules:
            self._collect_symbols(parsed)

        graph = CallGraph()
        for symbol in self._symbols.values():
            graph.add_node(self._internal_node(symbol, is_entry=False))

        for parsed in modules:
            self._add_calls(graph, parsed)

        entry_ids = self._apply_entry_points(graph, modules)
        if self._entry_filter:
            entry_ids = [
                node_id
                for node_id in entry_ids
                if self._matches_filter(graph.get_node(node_id), self._qnames.get(node_id, ""))
            ]

        reachable = graph.reachable(entry_ids, self._max_depth)
        self._log(f"entries={len(entry_ids)} reachable={len(reachable)} depth={self._max_depth}")
        return graph.to_graph(
            reachable,
            metadata={
                "language": "python",
                "max_depth": self._max_depth,
                "files": len(modules),
            },
        )

    def _log(self, message: str) -> None:
        if self._verbose:
            print(message, file=sys.stderr)

    def _collect_files(self, root: Path) -> list[Path]:
        if root.is_file():
            return [root] if root.suffix == ".py" and not self._is_excluded(root, root.parent) else []

        collected: list[Path] = []

        def walk(directory: Path) -> None:
            try:
                children = sorted(directory.iterdir(), key=lambda item: item.name.lower())
            except OSError as exc:
                self._log(f"skip directory {directory}: {exc}")
                return
            for child in children:
                if child.is_dir():
                    if self.should_skip_dir(child.name) or self._is_excluded(child, root):
                        continue
                    walk(child)
                elif child.suffix == ".py" and not self._is_excluded(child, root):
                    collected.append(child)

        walk(root)
        return collected

    def _is_excluded(self, path: Path, root: Path) -> bool:
        try:
            rel = path.relative_to(root).as_posix()
        except ValueError:
            rel = path.as_posix()
        return any(
            fnmatch.fnmatch(rel, pattern)
            or fnmatch.fnmatch(path.name, pattern)
            or PurePosixPath(rel).match(pattern)
            for pattern in self._exclude
        )

    def _parse_files(self, files: Sequence[Path], root: Path) -> list[_ParsedModule]:
        parsed: list[_ParsedModule] = []
        base = root if root.is_dir() else root.parent
        for file_path in files:
            try:
                source = file_path.read_text(encoding="utf-8-sig")
                tree = ast.parse(source, filename=str(file_path))
            except (OSError, SyntaxError, UnicodeDecodeError) as exc:
                self._log(f"skip {file_path}: {exc}")
                continue
            display = self._display_path(file_path, base)
            module = self._module_name(file_path, base)
            parsed.append(
                _ParsedModule(
                    path=file_path,
                    display=display,
                    module=module,
                    tree=tree,
                    imports=_collect_imports(tree, module),
                )
            )
        return parsed

    def _display_path(self, file_path: Path, base: Path) -> str:
        try:
            return file_path.relative_to(base).as_posix()
        except ValueError:
            return file_path.name

    def _module_name(self, file_path: Path, base: Path) -> str:
        try:
            relative = file_path.relative_to(base)
        except ValueError:
            return file_path.stem
        parts = list(relative.with_suffix("").parts)
        if parts and parts[-1] == "__init__":
            parts = parts[:-1]
        return ".".join(parts) or file_path.stem

    def _collect_symbols(self, parsed: _ParsedModule) -> None:
        self._collect_in_scope(parsed.tree, parsed, owner="", class_name=None)

    def _collect_in_scope(
        self,
        scope: ast.AST,
        parsed: _ParsedModule,
        owner: str,
        class_name: str | None,
    ) -> None:
        body = getattr(scope, "body", [])
        for node in body:
            if isinstance(node, ast.ClassDef):
                nested_class = f"{class_name}.{node.name}" if class_name else node.name
                nested_owner = f"{owner}.{node.name}" if owner else node.name
                self._collect_in_scope(node, parsed, nested_owner, nested_class)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                prefix = f"{parsed.module}.{owner}" if owner else parsed.module
                qualified = f"{prefix}.{node.name}"
                symbol = _Symbol(
                    qualified_name=qualified,
                    short_name=node.name,
                    file_display=parsed.display,
                    line=node.lineno,
                    node=node,
                    module=parsed.module,
                    class_name=class_name,
                )
                self._symbols[qualified] = symbol
                self._by_module_name.setdefault((parsed.module, node.name), []).append(symbol)
                nested_owner = f"{owner}.{node.name}" if owner else node.name
                self._collect_in_scope(node, parsed, nested_owner, class_name)

    def _add_calls(self, graph: CallGraph, parsed: _ParsedModule) -> None:
        for symbol in self._symbols.values():
            if symbol.module != parsed.module or symbol.file_display != parsed.display:
                continue
            source = self._internal_node(symbol)
            graph.add_node(source)
            for call in _calls_in_function(symbol.node):
                callee_qname = self._resolve_call(
                    call.func,
                    module=parsed.module,
                    class_name=symbol.class_name,
                    imports=parsed.imports,
                )
                target = self._node_for_qname(callee_qname)
                graph.upsert_node(target)
                graph.add_edge(source.id, target.id)

    def _apply_entry_points(self, graph: CallGraph, modules: Sequence[_ParsedModule]) -> list[str]:
        entry_ids: list[str] = []
        for parsed in modules:
            for entry in detect_entry_points(parsed.tree):
                if entry.kind == "main":
                    node = self._main_node(parsed, entry.line)
                    graph.upsert_node(node)
                    self._qnames[node.id] = f"{parsed.module}.__main__"
                    for called in entry.called_names:
                        callee_qname = self._resolve_name(called, parsed.module, None, parsed.imports)
                        target = self._node_for_qname(callee_qname)
                        graph.upsert_node(target)
                        graph.add_edge(node.id, target.id)
                    entry_ids.append(node.id)
                    continue
                symbol = self._lookup_function(parsed.module, entry.name, entry.line)
                if symbol is None:
                    continue
                node = self._internal_node(symbol, is_entry=True)
                graph.upsert_node(node)
                self._qnames[node.id] = symbol.qualified_name
                entry_ids.append(node.id)
        return list(dict.fromkeys(entry_ids))

    def _matches_filter(self, node: Node | None, qname: str) -> bool:
        if node is None:
            return False
        return any(
            filt == node.name or filt == qname or qname.endswith(f".{filt}")
            for filt in self._entry_filter
        )

    def _lookup_function(self, module: str, name: str, line: int) -> _Symbol | None:
        candidates = self._by_module_name.get((module, name), [])
        for symbol in candidates:
            if symbol.line == line:
                return symbol
        return candidates[0] if candidates else None

    def _resolve_call(
        self,
        func: ast.expr,
        *,
        module: str,
        class_name: str | None,
        imports: dict[str, _ImportRef],
    ) -> str:
        parts = _attr_parts(func)
        if not parts:
            return "<dynamic>"
        return self._resolve_parts(parts, module, class_name, imports)

    def _resolve_name(
        self,
        name: str,
        module: str,
        class_name: str | None,
        imports: dict[str, _ImportRef],
    ) -> str:
        return self._resolve_parts([name], module, class_name, imports)

    def _resolve_parts(
        self,
        parts: list[str],
        module: str,
        class_name: str | None,
        imports: dict[str, _ImportRef],
    ) -> str:
        head, rest = parts[0], parts[1:]
        if head in _SELF_NAMES and class_name and rest:
            candidate = f"{module}.{class_name}.{rest[-1]}"
            return candidate

        if not rest:
            local = self._prefer_module_level(module, head)
            if local is not None:
                return local.qualified_name
            if head in imports:
                return self._qualify_import(imports[head], [])
            return head

        if head in imports:
            return self._qualify_import(imports[head], rest)

        dotted = f"{module}.{'.'.join(parts)}"
        if dotted in self._symbols:
            return dotted
        if len(rest) == 1:
            method = f"{module}.{head}.{rest[0]}"
            if method in self._symbols:
                return method
        return ".".join(parts)

    def _prefer_module_level(self, module: str, name: str) -> _Symbol | None:
        candidates = self._by_module_name.get((module, name), [])
        for symbol in candidates:
            if symbol.class_name is None:
                return symbol
        return candidates[0] if candidates else None

    def _qualify_import(self, ref: _ImportRef, attrs: Sequence[str]) -> str:
        base = f"{ref.module}.{ref.name}" if ref.name else ref.module
        qname = ".".join([base, *attrs]) if attrs else base
        if qname in self._symbols:
            return qname
        if not attrs and ref.name:
            local = self._prefer_module_level(ref.module, ref.name)
            if local is not None:
                return local.qualified_name
        return qname

    def _node_for_qname(self, qname: str) -> Node:
        symbol = self._symbols.get(qname)
        if symbol is not None:
            return self._internal_node(symbol)
        return Node(
            id=stable_node_id(qname),
            name=qname.rsplit(".", 1)[-1],
            file="",
            line=0,
            is_entry=False,
            is_external=True,
        )

    def _internal_node(self, symbol: _Symbol, *, is_entry: bool = False) -> Node:
        node = Node(
            id=stable_node_id(symbol.qualified_name),
            name=symbol.short_name,
            file=symbol.file_display,
            line=symbol.line,
            is_entry=is_entry,
            is_external=False,
        )
        self._qnames[node.id] = symbol.qualified_name
        return node

    def _main_node(self, parsed: _ParsedModule, line: int) -> Node:
        qname = f"{parsed.module}.__main__"
        node = Node(
            id=stable_node_id(qname),
            name="__main__",
            file=parsed.display,
            line=line,
            is_entry=True,
            is_external=False,
        )
        self._qnames[node.id] = qname
        return node


def _collect_imports(tree: ast.Module, module: str) -> dict[str, _ImportRef]:
    """Map local names to import targets for ``module``."""
    mapping: dict[str, _ImportRef] = {}
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.asname:
                    mapping[alias.asname] = _ImportRef(module=alias.name, name=None)
                else:
                    top = alias.name.split(".", 1)[0]
                    mapping[top] = _ImportRef(module=top, name=None)
        elif isinstance(node, ast.ImportFrom):
            origin = _from_module(module, node.level, node.module)
            for alias in node.names:
                if alias.name == "*":
                    continue
                local = alias.asname or alias.name
                mapping[local] = _ImportRef(module=origin, name=alias.name)
    return mapping


def _from_module(current: str, level: int, module: str | None) -> str:
    """Resolve a relative ``from`` target to a dotted module name."""
    if level <= 0:
        return module or ""
    parts = current.split(".") if current else []
    parts = parts[:-level] if level <= len(parts) else []
    prefix = ".".join(parts)
    if module:
        return f"{prefix}.{module}" if prefix else module
    return prefix


def _calls_in_function(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> list[ast.Call]:
    """Return call nodes in ``fn``'s body, ignoring nested defs and classes."""
    collector = _CallCollector()
    for stmt in fn.body:
        collector.visit(stmt)
    return collector.calls


def _attr_parts(expr: ast.expr) -> list[str]:
    """Split ``foo.bar.baz`` into name parts; empty if the callee is dynamic."""
    if isinstance(expr, ast.Name):
        return [expr.id]
    if isinstance(expr, ast.Attribute):
        parent = _attr_parts(expr.value)
        return [*parent, expr.attr] if parent else [expr.attr]
    return []


class _CallCollector(ast.NodeVisitor):
    """Collect calls without descending into nested functions or classes."""

    def __init__(self) -> None:
        self.calls: list[ast.Call] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        return

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        return

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        return

    def visit_Lambda(self, node: ast.Lambda) -> None:
        return

    def visit_Call(self, node: ast.Call) -> None:
        self.calls.append(node)
        self.generic_visit(node)
