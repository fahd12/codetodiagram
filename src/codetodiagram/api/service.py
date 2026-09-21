"""Run the Python analyzer for API requests."""

from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import HTTPException

from codetodiagram.analyzer.python_analyzer import PythonAnalyzer
from codetodiagram.api.github import (
    CLONE_TIMEOUT_SECONDS,
    CloneError,
    GitHubSourceError,
    clone_github_repo,
    parse_github_url,
    validate_ref,
)
from codetodiagram.api.schemas import AnalyzeRequest, AnalyzeResponse
from codetodiagram.renderer.mermaid import render_mermaid


def analyze_request(payload: AnalyzeRequest) -> AnalyzeResponse:
    """Analyze ``payload.source`` as a local path or GitHub URL.

    Args:
        payload: Incoming analyze request.

    Returns:
        Mermaid source, entry names, and analyzer metadata.

    Raises:
        HTTPException: For invalid input or a failed clone/analyze.
    """
    try:
        ref = validate_ref(payload.ref)
    except GitHubSourceError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    path = Path(payload.source)
    if path.exists():
        return _analyze_path(
            path,
            entry=payload.entry,
            max_depth=payload.max_depth,
            max_nodes=payload.max_nodes,
        )

    try:
        url = parse_github_url(payload.source)
    except GitHubSourceError as exc:
        raise HTTPException(
            status_code=422,
            detail="source is not an existing local path or a github.com HTTPS URL",
        ) from exc

    return _analyze_github(
        url,
        ref=ref,
        entry=payload.entry,
        max_depth=payload.max_depth,
        max_nodes=payload.max_nodes,
    )


def _analyze_github(
    url: str,
    *,
    ref: str | None,
    entry: list[str] | None,
    max_depth: int,
    max_nodes: int,
) -> AnalyzeResponse:
    tmp = tempfile.TemporaryDirectory(prefix="codetodiagram-")
    try:
        dest = Path(tmp.name) / "repo"
        try:
            clone_github_repo(url, dest, ref=ref, timeout=CLONE_TIMEOUT_SECONDS)
        except CloneError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        return _analyze_path(dest, entry=entry, max_depth=max_depth, max_nodes=max_nodes)
    finally:
        tmp.cleanup()


def _analyze_path(
    path: Path,
    *,
    entry: list[str] | None,
    max_depth: int,
    max_nodes: int,
) -> AnalyzeResponse:
    analyzer = PythonAnalyzer(max_depth=max_depth, entry_filter=entry)
    graph = analyzer.analyze(path)
    entries = sorted({node.name for node in graph.nodes.values() if node.is_entry})
    if not entries:
        raise HTTPException(status_code=422, detail="no entry points found")
    mermaid = render_mermaid(graph, max_nodes=max_nodes)
    return AnalyzeResponse(
        mermaid=mermaid,
        entries=entries,
        metadata=dict(graph.metadata),
    )
