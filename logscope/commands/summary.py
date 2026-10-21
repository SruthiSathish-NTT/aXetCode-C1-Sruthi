"""
logscope.commands.summary
~~~~~~~~~~~~~~~~~~~~~~~~~
Single-pass streaming summary of a log file.

Public API
----------
SummaryResult  – dataclass holding all aggregated data
run            – consume iter_log and return a SummaryResult
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime

from logscope.parser import LogEntry, MalformedLine, iter_log


@dataclass
class SummaryResult:
    """All data produced by the summary command."""

    counts: dict[str, int]                   # {"INFO": n, "WARN": n, "ERROR": n}
    top_errors: list[tuple[str, int]]         # up to 5, descending frequency
    first_ts: datetime | None
    last_ts: datetime | None
    malformed: int


def run(path: str) -> SummaryResult:
    """Stream *path* once and return a SummaryResult.

    Raises OSError / FileNotFoundError if the file cannot be opened; the
    caller (cli.py) is responsible for surfacing that to the user.
    """
    counts: dict[str, int] = {"INFO": 0, "WARN": 0, "ERROR": 0}
    error_freq: Counter[str] = Counter()
    first_ts: datetime | None = None
    last_ts: datetime | None = None
    malformed: int = 0

    for entry in iter_log(path):
        if isinstance(entry, MalformedLine):
            malformed += 1
            continue

        counts[entry.level] += 1

        if entry.level == "ERROR":
            error_freq[entry.message] += 1

        if first_ts is None:
            first_ts = entry.timestamp
        last_ts = entry.timestamp

    top_errors = error_freq.most_common(5)

    return SummaryResult(
        counts=counts,
        top_errors=top_errors,
        first_ts=first_ts,
        last_ts=last_ts,
        malformed=malformed,
    )
