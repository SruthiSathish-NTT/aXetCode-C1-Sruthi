"""
logscope.commands.grep
~~~~~~~~~~~~~~~~~~~~~~
Single-pass streaming grep over a log file.

Public API
----------
GrepResult      – dataclass holding matched lines and malformed count
VALID_LEVELS    – frozenset of accepted level strings
parse_since     – parse an optional --since string → datetime | None
run             – consume iter_log and yield / collect results
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Iterator

from logscope.parser import LogEntry, MalformedLine, iter_log

# Grep accepts the same three levels as the parser.
VALID_LEVELS: frozenset[str] = frozenset({"INFO", "WARN", "ERROR"})

# The --since argument uses minute-precision only (no seconds).
_SINCE_FMT = "%Y-%m-%d %H:%M"


def parse_since(value: str) -> datetime:
    """Parse a ``--since`` string and return a datetime.

    Accepts exactly ``YYYY-MM-DD HH:MM``.

    Raises
    ------
    ValueError
        If *value* does not match the expected format.
    """
    try:
        return datetime.strptime(value, _SINCE_FMT)
    except ValueError:
        raise ValueError(
            f"Invalid --since value {value!r}. "
            "Expected format: YYYY-MM-DD HH:MM  (e.g. \"2026-10-01 09:00\")."
        )


@dataclass
class GrepResult:
    """Result produced by the grep command."""

    lines: list[str]   # original raw log lines that matched (no trailing newline)
    malformed: int


def run(path: str, level: str, since: datetime | None = None) -> GrepResult:
    """Stream *path* and return a GrepResult.

    Only entries whose level equals *level* (case-sensitive) and whose
    timestamp is >= *since* (when supplied) are included.

    The ``lines`` list holds only the raw strings of matching entries, so
    memory use is O(matching lines), not O(file size).  The streaming
    guarantee holds because entries are evaluated and appended one at a time
    as they arrive from ``iter_log``.

    Raises
    ------
    ValueError
        If *level* is not one of INFO / WARN / ERROR.
    OSError / FileNotFoundError
        If the file cannot be opened.
    """
    if level not in VALID_LEVELS:
        raise ValueError(
            f"Invalid level {level!r}. Must be one of: "
            + ", ".join(sorted(VALID_LEVELS))
            + "."
        )

    matched: list[str] = []
    malformed: int = 0

    for entry in iter_log(path):
        if isinstance(entry, MalformedLine):
            malformed += 1
            continue

        if entry.level != level:
            continue

        if since is not None and entry.timestamp < since:
            continue

        matched.append(entry.raw)

    return GrepResult(lines=matched, malformed=malformed)
