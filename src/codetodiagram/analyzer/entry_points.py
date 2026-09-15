"""Heuristics for discovering Python program entry points."""

from __future__ import annotations

import ast
from dataclasses import dataclass

_HTTP_HANDLER_ATTRS = frozenset(
    {
        "route",
        "get",
        "post",
        "put",
        "patch",
        "delete",
        "head",
        "options",
        "trace",
        "websocket",
        "api_route",
    }
)
_COMMAND_ATTRS = frozenset({"command"})
_TASK_NAMES = frozenset({"shared_task"})
_TASK_ATTRS = frozenset({"task"})


@dataclass(frozen=True)
class EntryPoint:
    """A detected entry point inside one module.

    Attributes:
        name: Function name, or ``__main__`` for a main guard.
        line: 1-based line of the function or ``if`` statement.
        kind: ``main``, ``route``, ``command``, or ``task``.
        called_names: Direct call names inside a ``__main__`` block.
    """

    name: str
    line: int
    kind: str
    called_names: tuple[str, ...] = ()


def detect_entry_points(tree: ast.AST) -> list[EntryPoint]:
    """Find entry points in ``tree`` in source order.

    Args:
        tree: Parsed module AST.

    Returns:
        Detected entries (functions with known decorators, plus ``__main__``).
    """
    found: list[EntryPoint] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            kind = _decorator_kind(node)
            if kind is not None:
                found.append(EntryPoint(name=node.name, line=node.lineno, kind=kind))
        elif isinstance(node, ast.If) and _is_name_main_guard(node.test):
            found.append(
                EntryPoint(
                    name="__main__",
                    line=node.lineno,
                    kind="main",
                    called_names=_direct_call_names(node),
                )
            )
    found.sort(key=lambda entry: (entry.line, entry.name))
    return found


def _decorator_kind(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> str | None:
    """Classify ``fn`` from its decorators, or return ``None``."""
    for decorator in fn.decorator_list:
        target = decorator.func if isinstance(decorator, ast.Call) else decorator
        parts = _name_parts(target)
        if not parts:
            continue
        attr = parts[-1]
        if attr in _HTTP_HANDLER_ATTRS:
            return "route"
        if attr in _COMMAND_ATTRS:
            return "command"
        if parts[0] in _TASK_NAMES or attr in _TASK_ATTRS:
            return "task"
    return None


def _is_name_main_guard(test: ast.expr) -> bool:
    """Return whether ``test`` is ``__name__ == "__main__"`` (either order)."""
    if not isinstance(test, ast.Compare) or len(test.ops) != 1 or len(test.comparators) != 1:
        return False
    if not isinstance(test.ops[0], ast.Eq):
        return False
    left, right = test.left, test.comparators[0]
    return (_is_dunder_name(left) and _is_main_literal(right)) or (
        _is_dunder_name(right) and _is_main_literal(left)
    )


def _is_dunder_name(expr: ast.expr) -> bool:
    return isinstance(expr, ast.Name) and expr.id == "__name__"


def _is_main_literal(expr: ast.expr) -> bool:
    return isinstance(expr, ast.Constant) and expr.value == "__main__"


def _direct_call_names(block: ast.If) -> tuple[str, ...]:
    """Collect callee names invoked directly in a ``__main__`` body."""
    names: list[str] = []
    for stmt in (*block.body, *block.orelse):
        for node in ast.walk(stmt):
            if not isinstance(node, ast.Call):
                continue
            callee = _call_name(node.func)
            if callee is not None:
                names.append(callee)
    return tuple(names)


def _call_name(func: ast.expr) -> str | None:
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _name_parts(expr: ast.expr) -> list[str]:
    """Split ``app.route`` / ``shared_task`` into dotted name parts."""
    if isinstance(expr, ast.Name):
        return [expr.id]
    if isinstance(expr, ast.Attribute):
        parent = _name_parts(expr.value)
        return [*parent, expr.attr] if parent else [expr.attr]
    return []
