"""Abstract analyzer contract for current and future languages."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import ClassVar

from codetodiagram.models import Graph


class LanguageAnalyzer(ABC):
    """Build a pruned call graph from source in one language.

    Subclasses (Python now, TypeScript later) own parsing and symbol
    resolution. Shared types stay on ``Graph`` so the CLI and renderer
    do not change when a language is added.
    """

    SKIP_DIR_NAMES: ClassVar[frozenset[str]] = frozenset(
        {
            "__pycache__",
            ".venv",
            "venv",
            "node_modules",
            ".git",
            "build",
            "dist",
        }
    )

    def should_skip_dir(self, name: str) -> bool:
        """Return whether a directory name is excluded from walks.

        Args:
            name: Bare directory name, not a full path.

        Returns:
            ``True`` if the directory must be skipped.
        """
        return name in self.SKIP_DIR_NAMES

    @abstractmethod
    def analyze(self, path: Path) -> Graph:
        """Analyze a file or directory and return the pruned call graph.

        Args:
            path: File or directory to analyze.

        Returns:
            Graph reachable from detected entry points.
        """
