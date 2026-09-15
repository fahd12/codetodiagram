"""Command-line interface for codetodiagram."""

from __future__ import annotations

import argparse
import sys

from codetodiagram import __version__


def build_parser() -> argparse.ArgumentParser:
    """Build the top-level argument parser.

    Returns:
        Parser with `--version` registered. Additional flags land in a later step.
    """
    parser = argparse.ArgumentParser(
        prog="codetodiagram",
        description="Generate Mermaid flowcharts from Python call graphs.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the CLI.

    Args:
        argv: Argument list, or ``None`` to use ``sys.argv[1:]``.

    Returns:
        Process exit code. ``0`` on success.
    """
    parser = build_parser()
    parser.parse_args(argv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
