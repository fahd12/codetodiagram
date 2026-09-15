"""Immutable graph models shared by analyzers and renderers."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import TypeAlias

MetadataValue: TypeAlias = str | int | bool


def stable_node_id(qualified_name: str) -> str:
    """Return a deterministic Mermaid-safe ID for ``qualified_name``.

    A hash is used instead of a counter so two runs on the same symbols emit
    identical IDs and diffs stay stable.
    """
    digest = hashlib.sha256(qualified_name.encode("utf-8")).hexdigest()[:16]
    return f"n{digest}"


@dataclass(frozen=True)
class Node:
    """A function (or synthetic entry) in the call graph.

    Attributes:
        id: Stable identifier derived from the fully-qualified name.
        name: Short display name (function name or ``__main__``).
        file: Source path, empty for unresolved externals.
        line: 1-based line number, ``0`` when unknown.
        is_entry: Whether this node is a detected entry point.
        is_external: Whether the callee could not be resolved in-repo.
    """

    id: str
    name: str
    file: str
    line: int
    is_entry: bool
    is_external: bool


@dataclass(frozen=True)
class Edge:
    """A directed call from ``source_id`` to ``target_id``."""

    source_id: str
    target_id: str


@dataclass(frozen=True)
class Graph:
    """A pruned call graph ready for rendering.

    Attributes:
        nodes: Nodes keyed by stable ``id``.
        edges: Directed caller-to-callee edges.
        metadata: Run options and notes (depth, language, truncation).
    """

    nodes: dict[str, Node]
    edges: list[Edge]
    metadata: dict[str, MetadataValue]
