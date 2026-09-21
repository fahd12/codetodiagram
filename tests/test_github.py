"""Tests for GitHub URL validation."""

from __future__ import annotations

import pytest

from codetodiagram.api.github import GitHubSourceError, parse_github_url, validate_ref


def test_parse_normalizes_https_repo_url() -> None:
    assert parse_github_url("https://github.com/fahd12/codetodiagram") == (
        "https://github.com/fahd12/codetodiagram.git"
    )
    assert parse_github_url("https://github.com/fahd12/codetodiagram.git/") == (
        "https://github.com/fahd12/codetodiagram.git"
    )


def test_parse_rejects_non_github_hosts() -> None:
    with pytest.raises(GitHubSourceError):
        parse_github_url("https://gitlab.com/foo/bar")
    with pytest.raises(GitHubSourceError):
        parse_github_url("https://github.com.evil.example/foo/bar")
    with pytest.raises(GitHubSourceError):
        parse_github_url("https://github.com/foo/bar/tree/main")


def test_validate_ref_rejects_unsafe_names() -> None:
    assert validate_ref(None) is None
    assert validate_ref("main") == "main"
    with pytest.raises(GitHubSourceError):
        validate_ref("--upload-pack=evil")
    with pytest.raises(GitHubSourceError):
        validate_ref("bad ref")
