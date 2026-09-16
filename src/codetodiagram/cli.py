"""Command-line interface for codetodiagram."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from codetodiagram import __version__
from codetodiagram.analyzer.python_analyzer import PythonAnalyzer
from codetodiagram.renderer.mermaid import render_json, render_mermaid


def build_parser() -> argparse.ArgumentParser:
    """Build the top-level argument parser.

    Returns:
        Parser with analysis flags and ``--version``.
    """
    parser = argparse.ArgumentParser(
        prog="codetodiagram",
        description="Generate Mermaid flowcharts from Python call graphs.",
    )
    parser.add_argument(
        "path",
        nargs="?",
        type=Path,
        default=None,
        help="Directory or Python file to analyze",
    )
    parser.add_argument(
        "--entry",
        action="append",
        default=None,
        metavar="NAME",
        help="Only show the subgraph reachable from this entry point (repeatable)",
    )
    parser.add_argument(
        "--max-depth",
        type=int,
        default=10,
        metavar="N",
        help="Maximum call-graph depth from each entry point (default: 10)",
    )
    parser.add_argument(
        "--max-nodes",
        type=int,
        default=50,
        metavar="N",
        help="Maximum nodes to render (default: 50)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        metavar="FILE",
        help="Write output to FILE instead of stdout",
    )
    parser.add_argument(
        "--format",
        choices=("mermaid", "json"),
        default="mermaid",
        help="Output format (default: mermaid)",
    )
    parser.add_argument(
        "--exclude",
        action="append",
        default=None,
        metavar="GLOB",
        help="Exclude paths matching GLOB (repeatable)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print analysis progress to stderr",
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
        ``0`` on success, ``1`` on error, ``2`` if no entry points were found.
    """
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.path is None:
        parser.error("the following arguments are required: path")
    try:
        return _run(args)
    except SystemExit:
        raise
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


def _run(args: argparse.Namespace) -> int:
    path: Path = args.path
    if not path.exists():
        print(f"error: path not found: {path}", file=sys.stderr)
        return 1
    if args.max_depth < 0:
        print("error: --max-depth must be >= 0", file=sys.stderr)
        return 1
    if args.max_nodes < 0:
        print("error: --max-nodes must be >= 0", file=sys.stderr)
        return 1

    analyzer = PythonAnalyzer(
        max_depth=args.max_depth,
        entry_filter=args.entry,
        exclude=args.exclude,
        verbose=args.verbose,
    )
    graph = analyzer.analyze(path)
    entries = [node for node in graph.nodes.values() if node.is_entry]
    if not entries:
        print("error: no entry points found", file=sys.stderr)
        return 2

    if args.format == "json":
        text = render_json(graph, max_nodes=args.max_nodes)
    else:
        text = render_mermaid(graph, max_nodes=args.max_nodes)

    if args.output is None:
        sys.stdout.write(text)
        if not text.endswith("\n"):
            sys.stdout.write("\n")
    else:
        args.output.write_text(text, encoding="utf-8")
        if args.verbose:
            print(f"wrote {args.output}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
