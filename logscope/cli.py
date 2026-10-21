"""
logscope.cli
~~~~~~~~~~~~
Command-line entry point.
"""

from __future__ import annotations

import argparse
import sys


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="logscope",
        description="Streaming analysis of application logs.",
    )
    sub = parser.add_subparsers(dest="command", metavar="COMMAND")

    # summary
    sp_summary = sub.add_parser("summary", help="Summarise a log file.")
    sp_summary.add_argument("file", metavar="LOG_FILE")
    sp_summary.add_argument("--format", choices=["json", "md"], default=None)

    # timeline
    sp_timeline = sub.add_parser("timeline", help="Show ERROR timeline bucketed by interval.")
    sp_timeline.add_argument("file", metavar="LOG_FILE")
    sp_timeline.add_argument(
        "--bucket",
        default="15m",
        metavar="BUCKET",
        help="Bucket duration, e.g. 15m or 1h (default: 15m).",
    )
    sp_timeline.add_argument("--format", choices=["json", "md"], default=None)

    # grep
    sp_grep = sub.add_parser("grep", help="Filter log lines by level and optional start time.")
    sp_grep.add_argument("file", metavar="LOG_FILE")
    sp_grep.add_argument(
        "--level",
        required=True,
        metavar="LEVEL",
        help="Level to match: INFO, WARN, or ERROR.",
    )
    sp_grep.add_argument(
        "--since",
        default=None,
        metavar="SINCE",
        help='Inclusive start timestamp, format: "YYYY-MM-DD HH:MM".',
    )
    sp_grep.add_argument("--format", choices=["json", "md"], default=None)

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    if args.command == "summary":
        _run_summary(args)
    elif args.command == "timeline":
        _run_timeline(args)
    elif args.command == "grep":
        _run_grep(args)
    else:
        print(f"[stub] command '{args.command}' not yet implemented.")
        sys.exit(1)


def _run_summary(args: argparse.Namespace) -> None:
    from logscope.commands.summary import run
    from logscope.output.text import format_summary
    from logscope.output.json_fmt import summary_to_json
    from logscope.output.md_fmt import write_summary_md

    try:
        result = run(args.file)
    except FileNotFoundError:
        print(f"logscope: error: file not found: {args.file}", file=sys.stderr)
        sys.exit(2)
    except OSError as exc:
        print(f"logscope: error: cannot read file: {exc}", file=sys.stderr)
        sys.exit(2)

    if args.format == "json":
        print(summary_to_json(result, args.file))
    elif args.format == "md":
        path = write_summary_md(result, args.file)
        print(f"Report written: {path}")
    else:
        print(format_summary(result))


def _run_timeline(args: argparse.Namespace) -> None:
    from logscope.commands.timeline import run, parse_bucket
    from logscope.output.text import format_timeline
    from logscope.output.json_fmt import timeline_to_json
    from logscope.output.md_fmt import write_timeline_md

    try:
        parse_bucket(args.bucket)
    except ValueError as exc:
        print(f"logscope: error: {exc}", file=sys.stderr)
        sys.exit(2)

    try:
        result = run(args.file, args.bucket)
    except FileNotFoundError:
        print(f"logscope: error: file not found: {args.file}", file=sys.stderr)
        sys.exit(2)
    except OSError as exc:
        print(f"logscope: error: cannot read file: {exc}", file=sys.stderr)
        sys.exit(2)

    if args.format == "json":
        print(timeline_to_json(result, args.file))
    elif args.format == "md":
        path = write_timeline_md(result, args.file)
        print(f"Report written: {path}")
    else:
        print(format_timeline(result))


def _run_grep(args: argparse.Namespace) -> None:
    from logscope.commands.grep import VALID_LEVELS, parse_since, run
    from logscope.output.text import format_grep
    from logscope.output.json_fmt import grep_to_json
    from logscope.output.md_fmt import write_grep_md

    if args.level not in VALID_LEVELS:
        print(
            f"logscope: error: invalid --level {args.level!r}. "
            "Must be one of: ERROR, INFO, WARN.",
            file=sys.stderr,
        )
        sys.exit(2)

    since_dt = None
    if args.since is not None:
        try:
            since_dt = parse_since(args.since)
        except ValueError as exc:
            print(f"logscope: error: {exc}", file=sys.stderr)
            sys.exit(2)

    try:
        result = run(args.file, args.level, since_dt)
    except FileNotFoundError:
        print(f"logscope: error: file not found: {args.file}", file=sys.stderr)
        sys.exit(2)
    except OSError as exc:
        print(f"logscope: error: cannot read file: {exc}", file=sys.stderr)
        sys.exit(2)

    if args.format == "json":
        print(grep_to_json(result, args.file, args.level, args.since))
    elif args.format == "md":
        path = write_grep_md(result, args.file, args.level, args.since)
        print(f"Report written: {path}")
    else:
        print(format_grep(result, args.level, args.since))


if __name__ == "__main__":
    main()
