"""
logscope.commands.timeline
~~~~~~~~~~~~~~~~~~~~~~~~~~
Single-pass streaming ERROR timeline bucketed by configurable time interval.

Public API
----------
TimelineResult  – dataclass holding all aggregated data
parse_bucket    – parse a bucket string such as "15m" or "1h" → timedelta
bucket_key      – floor a datetime to the nearest bucket boundary
run             – consume iter_log and return a TimelineResult
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from logscope.parser import LogEntry, MalformedLine, iter_log

# Epoch used as the fixed reference for bucket alignment.
# Using the UNIX epoch (midnight 1970-01-01 UTC, treated as naive) gives
# stable, deterministic bucket boundaries regardless of the log's date range.
_EPOCH = datetime(1970, 1, 1)

_BUCKET_RE = re.compile(r"^(\d+)(m|h)$")


def parse_bucket(spec: str) -> timedelta:
    """Parse a bucket specification string and return a timedelta.

    Accepted formats
    ----------------
    ``<N>m``  – N minutes (e.g. ``15m``, ``5m``)
    ``<N>h``  – N hours  (e.g. ``1h``, ``2h``)

    Raises
    ------
    ValueError
        If *spec* does not match the expected format or the numeric part is
        zero.
    """
    m = _BUCKET_RE.match(spec.strip())
    if not m:
        raise ValueError(
            f"Invalid bucket specification {spec!r}. "
            "Expected a positive integer followed by 'm' (minutes) or 'h' (hours), "
            "e.g. '15m' or '1h'."
        )
    value = int(m.group(1))
    unit = m.group(2)
    if value == 0:
        raise ValueError(
            f"Bucket size must be greater than zero, got {spec!r}."
        )
    if unit == "m":
        return timedelta(minutes=value)
    # unit == "h"
    return timedelta(hours=value)


def bucket_key(ts: datetime, bucket_td: timedelta) -> datetime:
    """Return the bucket-start datetime for *ts* given bucket width *bucket_td*.

    The bucket boundary is computed by flooring the elapsed time since
    ``_EPOCH`` to a multiple of *bucket_td*.  This produces stable,
    deterministic boundaries (e.g. every 15 minutes on the hour) regardless
    of the data range.

    Examples (bucket_td = 15 minutes)
    -----------------------------------
    09:00:00 → 09:00:00
    09:14:59 → 09:00:00
    09:15:00 → 09:15:00
    09:59:59 → 09:45:00
    """
    delta = ts - _EPOCH
    bucket_seconds = int(bucket_td.total_seconds())
    elapsed_seconds = int(delta.total_seconds())
    floored_seconds = (elapsed_seconds // bucket_seconds) * bucket_seconds
    return _EPOCH + timedelta(seconds=floored_seconds)


@dataclass
class TimelineResult:
    """All data produced by the timeline command."""

    # Ordered dict: bucket start datetime → error count (only non-empty buckets)
    buckets: dict[datetime, int]
    malformed: int
    bucket_label: str   # e.g. "15m"


def run(path: str, bucket_spec: str) -> TimelineResult:
    """Stream *path* once and return a TimelineResult.

    Only ERROR-level entries are counted.  INFO and WARN entries are read and
    discarded (they still consume one line of streaming I/O, so the pass
    remains truly single-pass and O(1) in memory relative to file size).

    Raises
    ------
    ValueError
        If *bucket_spec* is invalid (propagated from parse_bucket).
    OSError / FileNotFoundError
        If the file cannot be opened.
    """
    bucket_td = parse_bucket(bucket_spec)   # raises ValueError early if bad

    raw_buckets: defaultdict[datetime, int] = defaultdict(int)
    malformed: int = 0

    for entry in iter_log(path):
        if isinstance(entry, MalformedLine):
            malformed += 1
            continue

        if entry.level != "ERROR":
            continue

        key = bucket_key(entry.timestamp, bucket_td)
        raw_buckets[key] += 1

    # Sort buckets chronologically for deterministic output.
    sorted_buckets: dict[datetime, int] = dict(sorted(raw_buckets.items()))

    return TimelineResult(
        buckets=sorted_buckets,
        malformed=malformed,
        bucket_label=bucket_spec.strip(),
    )
