"""Tests for Mermaid and JSON rendering."""

from __future__ import annotations

from pathlib import Path

from codetodiagram.analyzer.python_analyzer import PythonAnalyzer
from codetodiagram.models import Edge, Graph, Node, stable_node_id
from codetodiagram.renderer.mermaid import prune_graph, render_json, render_mermaid

FIXTURE = Path(__file__).parent / "fixtures" / "sample_project"
EXPECTED = Path(__file__).parent / "fixtures" / "expected_output.mmd"


def _node(
    name: str,
    *,
    is_entry: bool = False,
    is_external: bool = False,
    file: str = "a.py",
    line: int = 1,
) -> Node:
    return Node(
        id=stable_node_id(name),
        name=name,
        file="" if is_external else file,
        line=0 if is_external else line,
        is_entry=is_entry,
        is_external=is_external,
    )


def test_sample_project_matches_snapshot() -> None:
    graph = PythonAnalyzer().analyze(FIXTURE)
    rendered = render_mermaid(graph)
    assert rendered == EXPECTED.read_text(encoding="utf-8")


def test_snapshot_is_deterministic() -> None:
    first = render_mermaid(PythonAnalyzer().analyze(FIXTURE))
    second = render_mermaid(PythonAnalyzer().analyze(FIXTURE))
    assert first == second


def test_groups_nodes_into_file_subgraphs() -> None:
    text = render_mermaid(PythonAnalyzer().analyze(FIXTURE))
    assert '["app.py"]' in text
    assert '["helpers.py"]' in text
    assert '["users.py"]' in text
    assert '["external"]' in text
    assert text.index('["app.py"]') < text.index('["helpers.py"]') < text.index('["external"]')


def test_entry_uses_stadium_and_external_is_dashed() -> None:
    entry = _node("index", is_entry=True)
    helper = _node("helper")
    external = _node("get", is_external=True)
    graph = Graph(
        nodes={entry.id: entry, helper.id: helper, external.id: external},
        edges=[
            Edge(entry.id, helper.id),
            Edge(helper.id, external.id),
        ],
        metadata={},
    )
    text = render_mermaid(graph)
    assert f'{entry.id}(["Entry: index<br/>a.py:1"])' in text
    assert f"{helper.id} --> {external.id}".replace("-->", "-.->") in text
    assert f"{helper.id} -.-> {external.id}" in text
    assert f'{external.id}["get<br/>external"]:::external' in text
    assert "classDef external" in text


def test_escape_breaks_mermaid_syntax() -> None:
    node = _node('foo<"x">(y)', file='a<"b">.py')
    graph = Graph(nodes={node.id: node}, edges=[], metadata={})
    text = render_mermaid(graph)
    assert "#quot;" in text
    assert "#40;" in text
    assert "#41;" in text
    assert "#lt;" in text
    assert "#gt;" in text


def test_prune_drops_least_connected_non_entries() -> None:
    entry = _node("entry", is_entry=True)
    busy = _node("busy")
    lonely = _node("lonely")
    graph = Graph(
        nodes={entry.id: entry, busy.id: busy, lonely.id: lonely},
        edges=[Edge(entry.id, busy.id), Edge(busy.id, entry.id)],
        metadata={"language": "python"},
    )
    pruned, omitted = prune_graph(graph, max_nodes=2)
    assert omitted == 1
    assert lonely.id not in pruned.nodes
    assert entry.id in pruned.nodes
    text = render_mermaid(graph, max_nodes=2)
    assert "%% Truncated: 1 nodes omitted" in text


def test_render_json_includes_sorted_payload() -> None:
    graph = PythonAnalyzer().analyze(FIXTURE)
    payload = render_json(graph)
    again = render_json(graph)
    assert payload == again
    assert '"language": "python"' in payload
    assert payload.endswith("\n")
