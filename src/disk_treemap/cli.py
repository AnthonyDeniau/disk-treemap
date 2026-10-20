"""The disk-treemap command line interface."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .report import generate_report
from .scanner import ScanOptions, ScanStats


def positive_integer(value: str) -> int:
    try:
        result = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a positive integer") from exc
    if result < 1:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return result


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        description="Create an interactive, offline HTML treemap of a directory.",
        epilog="Reports contain filenames and paths. Keep real scans private.",
    )
    result.add_argument(
        "root",
        nargs="?",
        type=Path,
        default=Path.cwd(),
        help="directory to scan (default: current directory)",
    )
    result.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("disk-treemap.html"),
        help="new HTML file to create (default: disk-treemap.html)",
    )
    result.add_argument(
        "--size",
        choices=("allocated", "logical"),
        default="allocated",
        help="rectangle weights (default: allocated disk blocks)",
    )
    result.add_argument(
        "--exclude",
        action="append",
        default=[],
        metavar="GLOB",
        help="exclude a name or relative POSIX path glob; repeatable",
    )
    result.add_argument(
        "--one-file-system",
        action="store_true",
        help="do not descend into directories on another device",
    )
    result.add_argument(
        "--count-hard-links",
        action="store_true",
        help="count every hard-linked filename instead of one per inode",
    )
    result.add_argument(
        "--chunk-size",
        type=positive_integer,
        default=5000,
        metavar="N",
        help="subtree threshold for lazy loading (default: 5000 nodes)",
    )
    result.add_argument("--label", help="replace the root path in the report (other names remain)")
    result.add_argument(
        "--strict",
        action="store_true",
        help="return exit code 1 after reporting any unreadable entries",
    )
    result.add_argument("--json", action="store_true", help="print a machine-readable summary")
    result.add_argument("-q", "--quiet", action="store_true", help="suppress progress and summary")
    result.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)

    def progress(stats: ScanStats) -> None:
        if not args.quiet:
            print(
                f"Scanned {stats.files:,} files in {stats.directories:,} directories",
                file=sys.stderr,
            )

    options = ScanOptions(
        args.size, tuple(args.exclude), args.one_file_system, args.count_hard_links, args.chunk_size
    )
    try:
        summary = generate_report(
            args.root, args.output, options, label=args.label, progress=progress
        )
    except FileExistsError:
        print(
            "disk-treemap: output already exists; choose a new filename with --output",
            file=sys.stderr,
        )
        return 1
    except (OSError, ValueError) as exc:
        print(f"disk-treemap: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("disk-treemap: interrupted; unfinished temporary output cleaned up", file=sys.stderr)
        return 130
    if args.json:
        print(json.dumps(summary, ensure_ascii=True))
    elif not args.quiet:
        print(f"Created {summary['output']}")
        print(
            f"{summary['files']:,} files, {summary['directories']:,} directories, "
            f"{summary['bytes'] / 1024**3:.2f} GiB, {summary['chunks']} data blocks"
        )
        if summary["chunks"]:
            print("Keep the HTML and its " + summary["chunkDirectory"] + " folder together.")
    if summary["unreadable"] and not args.quiet:
        print(
            f"Warning: {summary['unreadable']} entries were unreadable; the report is partial.",
            file=sys.stderr,
        )
    if summary["allocated_fallbacks"] and not args.quiet:
        print(
            f"Warning: used logical size for {summary['allocated_fallbacks']} entries "
            "because allocated-block metadata was unavailable.",
            file=sys.stderr,
        )
    return 1 if args.strict and summary["unreadable"] else 0
