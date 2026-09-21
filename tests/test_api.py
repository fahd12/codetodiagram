"""Tests for the local FastAPI analyze endpoints."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from codetodiagram.api.app import app
from codetodiagram.api.github import CloneError

FIXTURE = Path(__file__).parent / "fixtures" / "sample_project"


def test_health() -> None:
    client = TestClient(app)
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_analyze_local_fixture() -> None:
    client = TestClient(app)
    response = client.post("/api/analyze", json={"source": str(FIXTURE)})
    assert response.status_code == 200
    body = response.json()
    assert "flowchart TD" in body["mermaid"]
    assert "index" in body["entries"]
    assert "__main__" in body["entries"]
    assert body["metadata"]["language"] == "python"


def test_analyze_rejects_unknown_source() -> None:
    client = TestClient(app)
    response = client.post(
        "/api/analyze",
        json={"source": "https://example.com/not/github"},
    )
    assert response.status_code == 422


def test_analyze_github_uses_clone(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_clone(url: str, dest: Path, *, ref: str | None, timeout: int) -> None:
        assert url == "https://github.com/fahd12/codetodiagram.git"
        assert ref == "main"
        assert timeout > 0
        shutil.copytree(FIXTURE, dest)

    monkeypatch.setattr("codetodiagram.api.service.clone_github_repo", fake_clone)
    client = TestClient(app)
    response = client.post(
        "/api/analyze",
        json={
            "source": "https://github.com/fahd12/codetodiagram",
            "ref": "main",
        },
    )
    assert response.status_code == 200
    assert "index" in response.json()["entries"]


def test_analyze_github_clone_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_clone(url: str, dest: Path, *, ref: str | None, timeout: int) -> None:
        raise CloneError("repository not found")

    monkeypatch.setattr("codetodiagram.api.service.clone_github_repo", fail_clone)
    client = TestClient(app)
    response = client.post(
        "/api/analyze",
        json={"source": "https://github.com/fahd12/does-not-exist-ctd"},
    )
    assert response.status_code == 502
    assert "repository not found" in response.json()["detail"]


def test_analyze_missing_local_dir(tmp_path: Path) -> None:
    client = TestClient(app)
    empty = tmp_path / "empty"
    empty.mkdir()
    response = client.post("/api/analyze", json={"source": str(empty)})
    assert response.status_code == 422
    assert response.json()["detail"] == "no entry points found"
