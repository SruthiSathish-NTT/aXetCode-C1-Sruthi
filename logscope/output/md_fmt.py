"""
logscope.output.md_fmt
~~~~~~~~~~~~~~~~~~~~~~
Markdown report writers for all three command result types.

Each ``write_*`` function builds a Markdown string and writes it to a file
in the current working directory.  It then returns the path so the CLI can
print a confirmation line.

Filename strategy
-----------------
``logscope-<command>-<YYYYMMDD>-<HHMMSS>.md``

The timestamp component is taken from ``datetime.now()`` at the moment the
function is called.  This makes filenames deterministic for a given second
and collision-safe across runs.  Example::

    logscope-summary-20261001-090015.md

Public API
----------
write_summary_md   – SummaryResult  → writes file, returns path
write_timeline_md  – TimelineResult → writes file, returns path
write_grep_md      – GrepResult     → writes file, returns path
"""

from __future__ import annotations

import os
from datetime import datetime

from logscope.commands.grep import GrepResult
from logscope.commands.summary import SummaryResult
from logscope.commands.timeline import TimelineResult

_TS_FMT = "%Y-%m-%d %H:%M:%S"
_FILE_TS_FMT = "%Y%m%d-%H%M%S"


def _report_path(command: str, now: datetime) -> str:
    """Return the absolute path for the report file."""
    filename = f"logscope-{command}-{now.strftime(_FILE_TS_FMT)}.md"
    return os.path.join(os.getcwd(), filename)


def _write(path: str, content: str) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

def write_summary_md(result: SummaryResult, file: str, now: datetime | None = None) -> str:
    """Write a Markdown summary report and return the file path.

    Parameters
    ----------
    now:
        Override the generation timestamp (used in tests for determinism).
        Defaults to ``datetime.now()``.
    """
    now = now or datetime.now()
    path = _report_path("summary", now)
    lines: list[str] = []

    lines.append("# Logscope Summary Report")
    lines.append("")
    lines.append(f"**Source file:** `{file}`  ")
    lines.append(f"**Generated:** {now.strftime(_TS_FMT)}  ")
    lines.append("")

    # Level counts table
    lines.append("## Line Counts")
    lines.append("")
    lines.append("| Level | Count |")
    lines.append("|-------|------:|")
    lines.append(f"| INFO  | {result.counts['INFO']} |")
    lines.append(f"| WARN  | {result.counts['WARN']} |")
    lines.append(f"| ERROR | {result.counts['ERROR']} |")
    lines.append("")

    # Timestamps
    lines.append("## Timestamps")
    lines.append("")
    first = result.first_ts.strftime(_TS_FMT) if result.first_ts else "—"
    last  = result.last_ts.strftime(_TS_FMT)  if result.last_ts  else "—"
    lines.append(f"- **First:** {first}")
    lines.append(f"- **Last:**  {last}")
    lines.append("")

    # Top errors table
    lines.append("## Top ERROR Messages")
    lines.append("")
    if result.top_errors:
        lines.append("| Count | Message |")
        lines.append("|------:|---------|")
        for msg, cnt in result.top_errors:
            safe_msg = msg.replace("|", "\\|")
            lines.append(f"| {cnt} | {safe_msg} |")
    else:
        lines.append("_(none)_")
    lines.append("")

    # Malformed
    lines.append("## Data Quality")
    lines.append("")
    lines.append(f"- **Malformed lines:** {result.malformed}")
    lines.append("")

    _write(path, "\n".join(lines))
    return path


# ---------------------------------------------------------------------------
# Timeline
# ---------------------------------------------------------------------------

def write_timeline_md(result: TimelineResult, file: str, now: datetime | None = None) -> str:
    """Write a Markdown timeline report and return the file path."""
    now = now or datetime.now()
    path = _report_path("timeline", now)
    lines: list[str] = []

    lines.append("# Logscope Timeline Report")
    lines.append("")
    lines.append(f"**Source file:** `{file}`  ")
    lines.append(f"**Bucket size:** `{result.bucket_label}`  ")
    lines.append(f"**Generated:** {now.strftime(_TS_FMT)}  ")
    lines.append("")

    lines.append("## Error Timeline")
    lines.append("")
    if result.buckets:
        lines.append("| Bucket Start        | Error Count |")
        lines.append("|---------------------|------------:|")
        for ts, cnt in result.buckets.items():
            lines.append(f"| {ts.strftime(_TS_FMT)} | {cnt} |")
    else:
        lines.append("_(no ERROR records found)_")
    lines.append("")

    lines.append("## Data Quality")
    lines.append("")
    lines.append(f"- **Malformed lines:** {result.malformed}")
    lines.append("")

    _write(path, "\n".join(lines))
    return path


# ---------------------------------------------------------------------------
# Grep
# ---------------------------------------------------------------------------

def write_grep_md(
    result: GrepResult,
    file: str,
    level: str,
    since_str: str | None,
    now: datetime | None = None,
) -> str:
    """Write a Markdown grep report and return the file path."""
    now = now or datetime.now()
    path = _report_path("grep", now)
    lines: list[str] = []

    lines.append("# Logscope Grep Report")
    lines.append("")
    lines.append(f"**Source file:** `{file}`  ")
    lines.append(f"**Level filter:** `{level}`  ")
    since_display = since_str if since_str is not None else "_(not set)_"
    lines.append(f"**Since:** {since_display}  ")
    lines.append(f"**Generated:** {now.strftime(_TS_FMT)}  ")
    lines.append("")

    lines.append("## Results")
    lines.append("")
    lines.append(f"**Match count:** {len(result.lines)}")
    lines.append("")

    if result.lines:
        lines.append("```text")
        for raw in result.lines:
            lines.append(raw)
        lines.append("```")
    else:
        lines.append("_(no matching lines)_")
    lines.append("")

    lines.append("## Data Quality")
    lines.append("")
    lines.append(f"- **Malformed lines:** {result.malformed}")
    lines.append("")

    _write(path, "\n".join(lines))
    return path
