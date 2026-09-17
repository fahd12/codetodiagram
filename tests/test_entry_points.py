"""Tests for Python entry-point heuristics."""

from __future__ import annotations

import ast

from codetodiagram.analyzer.entry_points import detect_entry_points


def _kinds(source: str) -> list[tuple[str, str, tuple[str, ...]]]:
    entries = detect_entry_points(ast.parse(source))
    return [(entry.kind, entry.name, entry.called_names) for entry in entries]


def test_flask_route_and_main_guard() -> None:
    source = """
from flask import Flask
app = Flask(__name__)

@app.route("/")
def index():
    helper()

def helper():
    pass

if __name__ == "__main__":
    helper()
"""
    assert _kinds(source) == [
        ("route", "index", ()),
        ("main", "__main__", ("helper",)),
    ]


def test_main_guard_reversed_comparison() -> None:
    source = """
if "__main__" == __name__:
    run()
"""
    assert _kinds(source) == [("main", "__main__", ("run",))]


def test_fastapi_and_router_http_methods() -> None:
    source = """
@app.get("/a")
async def get_item():
    pass

@router.post("/b")
def create_item():
    pass
"""
    assert _kinds(source) == [
        ("route", "get_item", ()),
        ("route", "create_item", ()),
    ]


def test_click_typer_and_celery() -> None:
    source = """
@click.command()
def cli():
    pass

@app.command()
def typer_cmd():
    pass

@shared_task
def job():
    pass

@app.task
def queued():
    pass
"""
    assert _kinds(source) == [
        ("command", "cli", ()),
        ("command", "typer_cmd", ()),
        ("task", "job", ()),
        ("task", "queued", ()),
    ]


def test_plain_function_is_not_an_entry() -> None:
    source = """
def helper():
    return 1
"""
    assert _kinds(source) == []


def test_non_equality_if_is_not_main() -> None:
    source = """
if __name__ != "__main__":
    helper()
"""
    assert _kinds(source) == []
