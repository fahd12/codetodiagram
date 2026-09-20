"""Render a call graph as Mermaid flowchart or JSON."""

from __future__ import annotations

import json
from collections.abc import Iterable

from codetodiagram.models import Graph, Node, stable_node_id

_ESCAPE = (
    ("&", "&amp;"),
    ('"', "#quot;"),
    ("<", "#lt;"),
    (">", "#gt;"),
    ("(", "#40;"),
    (")", "#41;"),
)


def render_mermaid(graph: Graph, *, max_nodes: int = 50) -> str:
    """Render ``graph`` as a Mermaid ``flowchart TD`` document.

    Args:
        graph: Pruned call graph from an analyzer.
        max_nodes: Drop the least-connected nodes when this limit is exceeded.

    Returns:
        Mermaid source ending with a newline.
    """
    pruned, omitted = prune_graph(graph, max_nodes)
    lines = ["flowchart TD"]
    if omitted:
        lines.append(f"    %% Truncated: {omitted} nodes omitted")
    for file_key, nodes in _nodes_by_file(pruned.nodes.values()).items():
        title = file_key or "external"
        lines.append(f'    subgraph {_subgraph_id(file_key)}["{_escape(title)}"]')
        for node in nodes:
            lines.append(f"        {_node_declaration(node)}")
        lines.append("    end")
    for edge in pruned.edges:
        target = pruned.nodes[edge.target_id]
        arrow = "-.->" if target.is_external else "-->"
        lines.append(f"    {edge.source_id} {arrow} {edge.target_id}")
    if any(node.is_external for node in pruned.nodes.values()):
        lines.append("    classDef external stroke-dasharray: 5 5")
    return "\n".join(lines) + "\n"


def render_json(graph: Graph, *, max_nodes: int = 50) -> str:
    """Render ``graph`` as deterministic JSON.

    Args:
        graph: Pruned call graph from an analyzer.
        max_nodes: Same truncation rule as the Mermaid renderer.

    Returns:
        JSON text ending with a newline.
    """
    pruned, omitted = prune_graph(graph, max_nodes)
    payload = {
        "edges": [
            {"source_id": edge.source_id, "target_id": edge.target_id} for edge in pruned.edges
        ],
        "metadata": {
            **pruned.metadata,
            "omitted": omitted,
            "truncated": omitted > 0,
        },
        "nodes": [
            {
                "file": node.file,
                "id": node.id,
                "is_entry": node.is_entry,
                "is_external": node.is_external,
                "line": node.line,
                "name": node.name,
            }
            for node in pruned.nodes.values()
        ],
    }
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def prune_graph(graph: Graph, max_nodes: int) -> tuple[Graph, int]:
    """Drop the least-connected nodes until ``max_nodes`` remain.

    Entry points are kept until only entries are left to drop. Ties break by
    node id so two runs omit the same nodes.

    Args:
        graph: Graph to maybe truncate.
        max_nodes: Maximum nodes to keep.

    Returns:
        The (possibly smaller) graph and the number of omitted nodes.
    """
    if max_nodes < 0:
        raise ValueError("max_nodes must be >= 0")
    if len(graph.nodes) <= max_nodes:
        return graph, 0

    degrees = {node_id: 0 for node_id in graph.nodes}
    for edge in graph.edges:
        degrees[edge.source_id] += 1
        degrees[edge.target_id] += 1

    ranked = sorted(
        graph.nodes.values(),
        key=lambda node: (node.is_entry, degrees[node.id], node.id),
    )
    omitted = len(ranked) - max_nodes
    drop = {node.id for node in ranked[:omitted]}
    keep_ids = [node_id for node_id in graph.nodes if node_id not in drop]
    nodes = {node_id: graph.nodes[node_id] for node_id in keep_ids}
    edges = [
        edge
        for edge in graph.edges
        if edge.source_id in nodes and edge.target_id in nodes
    ]
    metadata = dict(graph.metadata)
    metadata["truncated"] = True
    metadata["omitted"] = omitted
    return Graph(nodes=nodes, edges=edges, metadata=metadata), omitted


def _nodes_by_file(nodes: Iterable[Node]) -> dict[str, list[Node]]:
    """Group nodes by source file; externals last under an empty key."""
    grouped: dict[str, list[Node]] = {}
    for node in nodes:
        key = "" if node.is_external or not node.file else node.file
        grouped.setdefault(key, []).append(node)
    for key in grouped:
        grouped[key].sort(key=lambda item: item.id)
    ordered = {key: grouped[key] for key in sorted(key for key in grouped if key)}
    if "" in grouped:
        ordered[""] = grouped[""]
    return ordered


def _subgraph_id(file_key: str) -> str:
    """Return a stable Mermaid subgraph id for a file path."""
    return "sg" + stable_node_id(file_key or "external")[1:]


def _node_declaration(node: Node) -> str:
    location = f"{node.file}:{node.line}" if node.file else "external"
    if node.is_entry:
        label = f"{_escape(f'Entry: {node.name}')}<br/>{_escape(location)}"
        return f'{node.id}(["{label}"])'
    label = f"{_escape(node.name)}<br/>{_escape(location)}"
    suffix = ":::external" if node.is_external else ""
    return f'{node.id}["{label}"]{suffix}'


def _escape(text: str) -> str:
    """Escape characters that break Mermaid node labels."""
    escaped = text
    for src, dest in _ESCAPE:
        escaped = escaped.replace(src, dest)
    return escaped
