"""
logscope.parser
~~~~~~~~~~~~~~~
Streaming log parser.  Reads one line at a time; never loads the full file.

Public API
----------
LogEntry      – dataclass for a successfully parsed line
MalformedLine – dataclass for an unparseable line
parse_line    – parse a single raw string
iter_log      – yield LogEntry | MalformedLine for every line in a file
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Iterator

# Valid log levels defined by the spec.
VALID_LEVELS: frozenset[str] = frozenset({"INFO", "WARN", "ERROR"})

# Pre-compiled pattern: date SP time SP level SP message
# We split on whitespace with maxsplit=3 so the message may contain spaces.
_SPLIT_RE = re.compile(r"\S+")


@dataclass(frozen=True, slots=True)
class LogEntry:
    """A successfully parsed log line."""

    timestamp: datetime
    level: str
    message: str
    raw: str  # original untouched line (stripped of trailing newline)


@dataclass(frozen=True, slots=True)
class MalformedLine:
    """A line that could not be parsed."""

    raw: str


def parse_line(line: str) -> LogEntry | MalformedLine:
    """Parse *line* and return a LogEntry or MalformedLine.

    Rules:
    - Split on whitespace (maxsplit=3) → must produce exactly 4 parts.
    - Parts[0] must be a valid date (YYYY-MM-DD).
    - Parts[1] must be a valid time (HH:MM:SS).
    - Parts[2] must be one of INFO / WARN / ERROR.
    - Parts[3] is the message (may be empty string after a level with no text,
      but the level token must be present).
    """
    raw = line.rstrip("\n\r")

    parts = raw.split(None, 3)  # split on any whitespace, at most 3 splits
    if len(parts) < 4:
        return MalformedLine(raw=raw)

    date_str, time_str, level, message = parts

    # Validate level first (cheap check before datetime parsing).
    if level not in VALID_LEVELS:
        return MalformedLine(raw=raw)

    # Validate and parse timestamp.
    try:
        timestamp = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return MalformedLine(raw=raw)

    return LogEntry(timestamp=timestamp, level=level, message=message, raw=raw)


def iter_log(path: str) -> Iterator[LogEntry | MalformedLine]:
    """Yield one LogEntry or MalformedLine per line in the file at *path*.

    The file is opened with ``errors='replace'`` so non-UTF-8 bytes are
    substituted rather than raising an exception.  The generator itself never
    raises; all errors result in MalformedLine values.
    """
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for line in fh:  # one line at a time — no read() / readlines()
            yield parse_line(line)
