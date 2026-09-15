"""Directed call graph used to prune reachable symbols.

Hand-rolled adjacency dict instead of networkx: v0.1 only needs insert,
lookup, bounded DFS, and degree counts for ``--max-nodes`` pruning.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Sequence

from codetodiagram.models import Edge, Graph, MetadataValue, Node


class CallGraph:
    """Mutable directed graph of functions, later frozen into a ``Graph``."""

    def __init__(self) -> None:
        self._nodes: dict[str, Node] = {}
        self._outgoing: dict[str, list[str]] = defaultdict(list)
        self._incoming: dict[str, list[str]] = defaultdict(list)

    def add_node(self, node: Node) -> Node:
        """Insert ``node`` or return the existing node with the same id.

        Args:
            node: Node to store.

        Returns:
            The stored node (existing wins so first write is authoritative).
        """
        existing = self._nodes.get(node.id)
        if existing is not None:
            return existing
        self._nodes[node.id] = node
        return node

    def get_node(self, node_id: str) -> Node | None:
        """Return the node for ``node_id``, or ``None`` if missing."""
        return self._nodes.get(node_id)

    def add_edge(self, source_id: str, target_id: str) -> None:
        """Add a caller-to-callee edge if both ends exist and it is new.

        Args:
            source_id: Caller node id.
            target_id: Callee node id.
        """
        if source_id not in self._nodes or target_id not in self._nodes:
            return
        if target_id in self._outgoing[source_id]:
            return
        self._outgoing[source_id].append(target_id)
        self._incoming[target_id].append(source_id)

    def neighbors(self, node_id: str) -> list[str]:
        """Return callee ids of ``node_id`` in insertion order."""
        return list(self._outgoing.get(node_id, []))

    def degree(self, node_id: str) -> int:
        """Return in-degree plus out-degree for pruning least-connected nodes."""
        return len(self._incoming.get(node_id, [])) + len(self._outgoing.get(node_id, []))

    def reachable(self, entry_ids: Sequence[str], max_depth: int) -> set[str]:
        """Return node ids reachable from ``entry_ids`` within ``max_depth``.

        Depth ``0`` is the entry itself. Depth ``1`` is its direct callees.

        Args:
            entry_ids: Starting node ids (unknown ids are ignored).
            max_depth: Maximum hop count from an entry.

        Returns:
            Reachable node ids, including the entries that exist.
        """
        seen: set[str] = set()
        stack: list[tuple[str, int]] = []
        for entry_id in entry_ids:
            if entry_id in self._nodes:
                stack.append((entry_id, 0))

        while stack:
            node_id, depth = stack.pop()
            if node_id in seen:
                continue
            seen.add(node_id)
            if depth >= max_depth:
                continue
            # Reverse so earlier callees stay first after LIFO pop.
            for callee_id in reversed(self._outgoing.get(node_id, [])):
                if callee_id not in seen:
                    stack.append((callee_id, depth + 1))
        return seen

    def to_graph(
        self,
        node_ids: Iterable[str] | None = None,
        metadata: dict[str, MetadataValue] | None = None,
    ) -> Graph:
        """Freeze a (possibly filtered) snapshot as an immutable ``Graph``.

        Args:
            node_ids: If given, keep only these nodes and edges between them.
            metadata: Optional run metadata copied into the result.

        Returns:
            Immutable graph with nodes and edges in sorted-id order.
        """
        if node_ids is None:
            keep = set(self._nodes)
        else:
            keep = {node_id for node_id in node_ids if node_id in self._nodes}

        nodes = {node_id: self._nodes[node_id] for node_id in sorted(keep)}
        edges = [
            Edge(source_id=source_id, target_id=target_id)
            for source_id in sorted(keep)
            for target_id in self._outgoing.get(source_id, [])
            if target_id in keep
        ]
        return Graph(nodes=nodes, edges=edges, metadata=dict(metadata or {}))
