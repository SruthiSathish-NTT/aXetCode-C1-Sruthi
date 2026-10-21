"""
logscope.output.text
~~~~~~~~~~~~~~~~~~~~
Human-readable terminal renderers.  Each function accepts the relevant
result dataclass and returns a formatted string.  Nothing is printed here;
callers decide how to emit the output (print, write to file, etc.).
"""

from __future__ import annotations

import shutil

from logscope.commands.summary import SummaryResult
from logscope.commands.timeline import TimelineResult
from logscope.commands.grep import GrepResult

_TS_FMT = "%Y-%m-%d %H:%M:%S"

# Maximum bar width used when the terminal width cannot be determined.
_DEFAULT_BAR_WIDTH = 40
# Characters reserved for the non-bar columns:
#   "YYYY-MM-DD HH:MM:SS" (19) + "  " (2) + count field (6) + "  " (2) = 29
_RESERVED_COLS = 29


def format_summary(result: SummaryResult) -> str:
    """Return a multi-line human-readable summary report."""
    lines: list[str] = []

    lines.append("=== Log Summary ===")
    lines.append("")

    # Level counts
    lines.append("Line counts:")
    lines.append(f"  INFO   : {result.counts['INFO']}")
    lines.append(f"  WARN   : {result.counts['WARN']}")
    lines.append(f"  ERROR  : {result.counts['ERROR']}")
    lines.append("")

    # Timestamps
    first = result.first_ts.strftime(_TS_FMT) if result.first_ts else "—"
    last  = result.last_ts.strftime(_TS_FMT)  if result.last_ts  else "—"
    lines.append(f"First timestamp : {first}")
    lines.append(f"Last timestamp  : {last}")
    lines.append("")

    # Top errors
    lines.append("Top ERROR messages:")
    if result.top_errors:
        for msg, count in result.top_errors:
            lines.append(f"  [{count:>5}]  {msg}")
    else:
        lines.append("  (none)")
    lines.append("")

    # Malformed
    lines.append(f"Malformed lines : {result.malformed}")

    return "\n".join(lines)


def format_timeline(result: TimelineResult) -> str:
    """Return a multi-line bar-chart timeline report.

    Layout per row::

        2026-10-01 09:00:00  [   42]  ████████████████████

    The bar is scaled so the bucket with the highest count fills the
    available terminal width (capped at _DEFAULT_BAR_WIDTH when the
    terminal is too narrow or cannot be measured).
    """
    lines: list[str] = []

    lines.append(f"=== Error Timeline (bucket: {result.bucket_label}) ===")
    lines.append("")

    if not result.buckets:
        lines.append("  (no ERROR records found)")
    else:
        # Determine bar width from terminal, with a sensible minimum.
        try:
            term_cols = shutil.get_terminal_size(fallback=(0, 0)).columns
        except Exception:
            term_cols = 0

        available = term_cols - _RESERVED_COLS if term_cols > _RESERVED_COLS else 0
        max_bar = max(available, _DEFAULT_BAR_WIDTH)
        # Cap at DEFAULT so very wide terminals don't produce absurd bars.
        bar_width = min(max_bar, _DEFAULT_BAR_WIDTH)

        max_count = max(result.buckets.values())

        for bucket_start, count in result.buckets.items():
            ts_str = bucket_start.strftime(_TS_FMT)
            bar_len = round((count / max_count) * bar_width) if max_count > 0 else 0
            bar = "#" * bar_len
            lines.append(f"{ts_str}  [{count:>5}]  {bar}")

    lines.append("")
    lines.append(f"Malformed lines : {result.malformed}")

    return "\n".join(lines)


def format_grep(result: GrepResult, level: str, since_str: str | None) -> str:
    """Return a human-readable grep report.

    Matching lines are printed verbatim (one per output line), followed by a
    summary footer.  When there are no matches the footer still appears so the
    user always sees the malformed-line count.
    """
    out: list[str] = []

    since_note = f"  since : {since_str}" if since_str else ""
    out.append(f"=== Grep results (level: {level}){since_note} ===")
    out.append("")

    if result.lines:
        for raw_line in result.lines:
            out.append(raw_line)
    else:
        out.append("  (no matching lines)")

    out.append("")
    out.append(f"Matches         : {len(result.lines)}")
    out.append(f"Malformed lines : {result.malformed}")

    return "\n".join(out)
