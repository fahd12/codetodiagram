"""Tests for the hand-rolled directed call graph."""

from __future__ import annotations

from codetodiagram.analyzer.call_graph import CallGraph
from codetodiagram.models import Node


def _node(node_id: str, name: str, *, is_entry: bool = False, is_external: bool = False) -> Node:
    return Node(
        id=node_id,
        name=name,
        file="a.py",
        line=1,
        is_entry=is_entry,
        is_external=is_external,
    )


def test_add_node_keeps_first_write() -> None:
    graph = CallGraph()
    first = graph.add_node(_node("a", "first"))
    second = graph.add_node(_node("a", "second", is_entry=True))
    assert second.name == "first"
    assert first is graph.get_node("a")


def test_upsert_merges_entry_flag() -> None:
    graph = CallGraph()
    graph.add_node(_node("a", "fn"))
    merged = graph.upsert_node(_node("a", "fn", is_entry=True))
    assert merged.is_entry is True
    assert merged.is_external is False


def test_add_edge_ignores_missing_and_duplicates() -> None:
    graph = CallGraph()
    graph.add_node(_node("a", "a"))
    graph.add_node(_node("b", "b"))
    graph.add_edge("a", "missing")
    graph.add_edge("a", "b")
    graph.add_edge("a", "b")
    assert graph.neighbors("a") == ["b"]
    assert graph.degree("a") == 1
    assert graph.degree("b") == 1


def test_reachable_respects_max_depth() -> None:
    graph = CallGraph()
    graph.add_node(_node("a", "a", is_entry=True))
    graph.add_node(_node("b", "b"))
    graph.add_node(_node("c", "c"))
    graph.add_edge("a", "b")
    graph.add_edge("b", "c")
    assert graph.reachable(["a"], 0) == {"a"}
    assert graph.reachable(["a"], 1) == {"a", "b"}
    assert graph.reachable(["a"], 2) == {"a", "b", "c"}
    assert graph.reachable(["missing"], 10) == set()


def test_to_graph_filters_and_sorts() -> None:
    graph = CallGraph()
    graph.add_node(_node("b", "b"))
    graph.add_node(_node("a", "a"))
    graph.add_edge("a", "b")
    frozen = graph.to_graph(["a", "missing"], metadata={"language": "python"})
    assert list(frozen.nodes) == ["a"]
    assert frozen.edges == []
    assert frozen.metadata == {"language": "python"}
