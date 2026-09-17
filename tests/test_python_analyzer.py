"""Tests for the Python AST analyzer."""

from __future__ import annotations

from pathlib import Path

import pytest

from codetodiagram.analyzer.python_analyzer import PythonAnalyzer

FIXTURE = Path(__file__).parent / "fixtures" / "sample_project"


def _names(analyzer: PythonAnalyzer, path: Path) -> set[str]:
    graph = analyzer.analyze(path)
    return {node.name for node in graph.nodes.values()}


def test_sample_project_entries_and_shared_helper() -> None:
    graph = PythonAnalyzer().analyze(FIXTURE)
    names = {node.name: node for node in graph.nodes.values()}
    assert names["index"].is_entry
    assert names["__main__"].is_entry
    assert names["greet"].is_entry is False
    assert names["get"].is_external
    assert "unused_view" not in names
    assert "unused_helper" not in names

    by_name = {node.name: node.id for node in graph.nodes.values()}
    edges = {(edge.source_id, edge.target_id) for edge in graph.edges}
    assert (by_name["index"], by_name["greet"]) in edges
    assert (by_name["__main__"], by_name["greet"]) in edges
    assert (by_name["fetch_remote"], by_name["get"]) in edges


def test_entry_filter_limits_subgraph() -> None:
    names = _names(PythonAnalyzer(entry_filter=["index"]), FIXTURE)
    assert "index" in names
    assert "greet" in names
    assert "__main__" not in names


def test_exclude_glob_drops_helpers() -> None:
    graph = PythonAnalyzer(exclude=["helpers.py"]).analyze(FIXTURE)
    internal_files = {node.file for node in graph.nodes.values() if not node.is_external}
    assert "helpers.py" not in internal_files
    assert "app.py" in internal_files


def test_single_file_analyze() -> None:
    graph = PythonAnalyzer().analyze(FIXTURE / "app.py")
    names = {node.name for node in graph.nodes.values()}
    assert "index" in names
    assert "__main__" in names


def test_skips_syntax_error_and_skip_dirs(tmp_path: Path) -> None:
    (tmp_path / "ok.py").write_text(
        "if __name__ == '__main__':\n    helper()\n\ndef helper():\n    return 1\n",
        encoding="utf-8",
    )
    (tmp_path / "bad.py").write_text("def broken(\n", encoding="utf-8")
    skipped = tmp_path / ".venv" / "lib.py"
    skipped.parent.mkdir()
    skipped.write_text("def hidden():\n    pass\n", encoding="utf-8")
    names = _names(PythonAnalyzer(), tmp_path)
    assert names == {"__main__", "helper"}
    assert PythonAnalyzer().should_skip_dir(".venv")


def test_resolves_self_and_imported_calls(tmp_path: Path) -> None:
    (tmp_path / "mod.py").write_text(
        """
from other import helper

class Worker:
    def run(self):
        self.step()
        helper()

    def step(self):
        return 1

@app.route("/")
def start():
    Worker().run()
""",
        encoding="utf-8",
    )
    (tmp_path / "other.py").write_text(
        "def helper():\n    return 2\n",
        encoding="utf-8",
    )
    names = _names(PythonAnalyzer(), tmp_path)
    assert {"start", "run", "step", "helper"} <= names


def test_relative_import_and_from_import(tmp_path: Path) -> None:
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "api.py").write_text(
        "from .util import ping\n\n@app.get('/')\ndef root():\n    return ping()\n",
        encoding="utf-8",
    )
    (pkg / "util.py").write_text("def ping():\n    return 'ok'\n", encoding="utf-8")
    names = _names(PythonAnalyzer(), tmp_path)
    assert {"root", "ping"} <= names


def test_max_depth_stops_recursion() -> None:
    deep = PythonAnalyzer(max_depth=0, entry_filter=["index"]).analyze(FIXTURE)
    assert {node.name for node in deep.nodes.values()} == {"index"}


def test_verbose_writes_stderr(capsys: pytest.CaptureFixture[str]) -> None:
    PythonAnalyzer(verbose=True).analyze(FIXTURE)
    captured = capsys.readouterr()
    assert "scanning" in captured.err
    assert "entries=" in captured.err
