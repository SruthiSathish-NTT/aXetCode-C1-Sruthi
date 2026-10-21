"""
logscope.output.json_fmt
~~~~~~~~~~~~~~~~~~~~~~~~
JSON serialisers for all three command result types.

Each function returns a *str* containing valid JSON suitable for writing
directly to stdout.  No banners, headings, or diagnostic text are mixed in.
Datetimes are serialised as ISO-8601 strings (``datetime.isoformat()``).

Public API
----------
summary_to_json   – SummaryResult  → JSON str
timeline_to_json  – TimelineResult → JSON str
grep_to_json      – GrepResult     → JSON str
"""

from __future__ import annotations

import json
from datetime import datetime

from logscope.commands.grep import GrepResult
from logscope.commands.summary import SummaryResult
from logscope.commands.timeline import TimelineResult


def _iso(dt: datetime | None) -> str | None:
    """Return ``dt.isoformat()`` or ``None`` when *dt* is ``None``."""
    return dt.isoformat() if dt is not None else None


def summary_to_json(result: SummaryResult, file: str) -> str:
    """Serialise *result* to a JSON string.

    Schema
    ------
    ::

        {
          "command": "summary",
          "file": "<path>",
          "counts": {"INFO": int, "WARN": int, "ERROR": int},
          "top_errors": [{"message": str, "count": int}, ...],   // up to 5
          "first_timestamp": "<ISO-8601>" | null,
          "last_timestamp":  "<ISO-8601>" | null,
          "malformed_lines": int
        }
    """
    obj = {
        "command": "summary",
        "file": file,
        "counts": result.counts,
        "top_errors": [
            {"message": msg, "count": cnt}
            for msg, cnt in result.top_errors
        ],
        "first_timestamp": _iso(result.first_ts),
        "last_timestamp": _iso(result.last_ts),
        "malformed_lines": result.malformed,
    }
    return json.dumps(obj, indent=2)


def timeline_to_json(result: TimelineResult, file: str) -> str:
    """Serialise *result* to a JSON string.

    Schema
    ------
    ::

        {
          "command": "timeline",
          "file": "<path>",
          "bucket": "<spec>",           // e.g. "15m"
          "timeline": [
            {"bucket_start": "<ISO-8601>", "error_count": int},
            ...
          ],
          "malformed_lines": int
        }
    """
    obj = {
        "command": "timeline",
        "file": file,
        "bucket": result.bucket_label,
        "timeline": [
            {"bucket_start": ts.isoformat(), "error_count": cnt}
            for ts, cnt in result.buckets.items()
        ],
        "malformed_lines": result.malformed,
    }
    return json.dumps(obj, indent=2)


def grep_to_json(
    result: GrepResult,
    file: str,
    level: str,
    since_str: str | None,
) -> str:
    """Serialise *result* to a JSON string.

    Parameters
    ----------
    since_str:
        The raw ``--since`` string as typed by the user (``"YYYY-MM-DD HH:MM"``),
        or ``None`` when omitted.  It is re-formatted to ISO-8601 in the JSON
        output so consumers get a consistent datetime string.

    Schema
    ------
    ::

        {
          "command": "grep",
          "file": "<path>",
          "level": "ERROR"|"WARN"|"INFO",
          "since": "<ISO-8601>" | null,
          "match_count": int,
          "matches": ["<raw log line>", ...],
          "malformed_lines": int
        }
    """
    # Normalise --since to ISO-8601 when present.
    if since_str is not None:
        from logscope.commands.grep import parse_since
        since_iso: str | None = parse_since(since_str).isoformat()
    else:
        since_iso = None

    obj = {
        "command": "grep",
        "file": file,
        "level": level,
        "since": since_iso,
        "match_count": len(result.lines),
        "matches": result.lines,
        "malformed_lines": result.malformed,
    }
    return json.dumps(obj, indent=2)
