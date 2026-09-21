"""Validate GitHub URLs and shallow-clone public repositories."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

_GITHUB_REPO = re.compile(
    r"^https://github\.com/(?P<owner>[A-Za-z0-9_.-]+)/(?P<repo>[A-Za-z0-9_.-]+?)(?:\.git)?/?$"
)
_SAFE_REF = re.compile(r"^[A-Za-z0-9._/-]+$")

CLONE_TIMEOUT_SECONDS = 60


class GitHubSourceError(ValueError):
    """The source string is not a cloneable public GitHub repo URL."""


class CloneError(RuntimeError):
    """git clone failed or timed out."""


def parse_github_url(source: str) -> str:
    """Return a normalized ``https://github.com/owner/repo.git`` URL.

    Args:
        source: User-supplied source string.

    Returns:
        Normalized clone URL.

    Raises:
        GitHubSourceError: If the URL is not a github.com HTTPS repo root.
    """
    stripped = source.strip()
    match = _GITHUB_REPO.fullmatch(stripped)
    if match is None:
        raise GitHubSourceError("only https://github.com/owner/repo URLs are allowed")
    owner = match.group("owner")
    repo = match.group("repo")
    if repo.endswith(".git"):
        repo = repo[: -len(".git")]
    return f"https://github.com/{owner}/{repo}.git"


def validate_ref(ref: str | None) -> str | None:
    """Return ``ref`` if it is a safe branch/tag name.

    Args:
        ref: Optional git ref.

    Returns:
        The same ref, or ``None``.

    Raises:
        GitHubSourceError: If the ref contains unsafe characters.
    """
    if ref is None or ref == "":
        return None
    if ref.startswith("-") or not _SAFE_REF.fullmatch(ref):
        raise GitHubSourceError("ref must be a simple branch or tag name")
    return ref


def clone_github_repo(url: str, dest: Path, *, ref: str | None, timeout: int) -> None:
    """Shallow-clone ``url`` into ``dest``.

    Args:
        url: Normalized GitHub HTTPS URL.
        dest: Empty directory path for the clone.
        ref: Optional branch or tag.
        timeout: Subprocess timeout in seconds.

    Raises:
        CloneError: If git is missing, times out, or returns non-zero.
    """
    command = ["git", "clone", "--depth", "1"]
    if ref is not None:
        command.extend(["--branch", ref])
    command.extend(["--", url, str(dest)])
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError as exc:
        raise CloneError("git is not installed") from exc
    except subprocess.TimeoutExpired as exc:
        raise CloneError(f"git clone timed out after {timeout}s") from exc
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "clone failed").strip()
        raise CloneError(detail.splitlines()[-1] if detail else "clone failed")
