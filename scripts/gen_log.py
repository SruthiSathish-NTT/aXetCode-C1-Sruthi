#!/usr/bin/env python3
"""
scripts/gen_log.py
~~~~~~~~~~~~~~~~~~
Synthetic log generator for Logscope performance testing.

Generates a realistic log file compatible with the Logscope parser format:

    YYYY-MM-DD HH:MM:SS LEVEL message

Usage
-----
    python scripts/gen_log.py --size-mb 100 --output synthetic-100mb.log
    python scripts/gen_log.py --size-mb 10
    python scripts/gen_log.py --size-mb 100 --malformed-rate 0.02

The generator writes one line at a time and stops once the requested byte
target is reached.  It never accumulates the full output in memory.
"""

from __future__ import annotations

import argparse
import os
import random
import sys
from datetime import datetime, timedelta

# ---------------------------------------------------------------------------
# Message pools — varied enough to produce realistic frequency distributions
# ---------------------------------------------------------------------------

_INFO_MSGS = [
    "Application started",
    "Configuration loaded successfully",
    "Scheduled task complete",
    "Health check passed",
    "Cache warmed up",
    "User session opened",
    "Background worker started",
    "Metrics flushed to collector",
    "Snapshot written",
    "Feature flag evaluated",
    "Config reloaded",
    "Heartbeat received",
]

_WARN_MSGS = [
    "Disk usage above 80%",
    "Retry attempt 1",
    "Retry attempt 2",
    "Slow query detected",
    "Connection pool near capacity",
    "Memory usage elevated",
    "Certificate expiring soon",
    "Rate limit approaching",
    "Queue depth high",
    "Deprecated API call",
]

# Intentionally small pool so top errors repeat with high frequency
_ERROR_MSGS = [
    "Database connection refused",
    "Timeout waiting for lock",
    "Out of memory",
    "Disk write failed",
    "Remote service unavailable",
]

# Malformed-line templates — guaranteed to fail the parser
_MALFORMED_MSGS = [
    "MALFORMED no timestamp here",
    "2026-99-99 bad date ERROR something",
    "just some garbage text",
    "{}",
    "DEBUG this level is not supported",
    "   ",
    "error without timestamp",
]


def _next_ts(current: datetime, rng: random.Random) -> datetime:
    """Advance *current* by a random 1–10 second step."""
    return current + timedelta(seconds=rng.randint(1, 10))


def _make_line(ts: datetime, rng: random.Random, level_weights: dict[str, float]) -> str:
    """Return one valid log line (no trailing newline)."""
    level = rng.choices(
        list(level_weights.keys()),
        weights=list(level_weights.values()),
        k=1,
    )[0]
    if level == "INFO":
        msg = rng.choice(_INFO_MSGS)
    elif level == "WARN":
        msg = rng.choice(_WARN_MSGS)
    else:
        msg = rng.choice(_ERROR_MSGS)
    return f"{ts.strftime('%Y-%m-%d %H:%M:%S')} {level} {msg}"


def _make_malformed(rng: random.Random) -> str:
    """Return one malformed line (no trailing newline)."""
    return rng.choice(_MALFORMED_MSGS)


def generate(
    output_path: str,
    target_bytes: int,
    malformed_rate: float = 0.0,
    seed: int | None = None,
) -> tuple[int, int, int]:
    """Write synthetic log lines to *output_path* until *target_bytes* is reached.

    Returns
    -------
    (actual_bytes, valid_count, malformed_count)
    """
    rng = random.Random(seed)

    level_weights = {"INFO": 0.70, "WARN": 0.20, "ERROR": 0.10}
    current_ts = datetime(2026, 10, 1, 9, 0, 0)

    written_bytes = 0
    valid_count = 0
    malformed_count = 0

    with open(output_path, "w", encoding="utf-8") as fh:
        while written_bytes < target_bytes:
            # Decide whether to emit a malformed line
            if malformed_rate > 0 and rng.random() < malformed_rate:
                line = _make_malformed(rng)
                malformed_count += 1
            else:
                line = _make_line(current_ts, rng, level_weights)
                current_ts = _next_ts(current_ts, rng)
                valid_count += 1

            fh.write(line + "\n")
            written_bytes += len(line) + 1  # +1 for \n

    return written_bytes, valid_count, malformed_count


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="gen_log",
        description="Generate a synthetic Logscope-compatible log file.",
    )
    parser.add_argument(
        "--size-mb",
        type=float,
        default=100.0,
        metavar="MB",
        help="Target output size in megabytes (default: 100).",
    )
    parser.add_argument(
        "--output",
        default="synthetic.log",
        metavar="PATH",
        help="Output file path (default: synthetic.log).",
    )
    parser.add_argument(
        "--malformed-rate",
        type=float,
        default=0.02,
        metavar="RATE",
        help=(
            "Fraction of lines that are malformed, 0.0–1.0 "
            "(default: 0.02 = 2%%)."
        ),
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        metavar="INT",
        help="Random seed for reproducibility (optional).",
    )
    args = parser.parse_args(argv)

    if args.size_mb <= 0:
        print("gen_log: error: --size-mb must be greater than zero.", file=sys.stderr)
        sys.exit(1)
    if not (0.0 <= args.malformed_rate < 1.0):
        print(
            "gen_log: error: --malformed-rate must be in range [0.0, 1.0).",
            file=sys.stderr,
        )
        sys.exit(1)

    target_bytes = int(args.size_mb * 1024 * 1024)

    print(f"Generating ~{args.size_mb:.1f} MB log -> {args.output} ...")

    actual_bytes, valid_count, malformed_count = generate(
        output_path=args.output,
        target_bytes=target_bytes,
        malformed_rate=args.malformed_rate,
        seed=args.seed,
    )

    actual_mb = actual_bytes / (1024 * 1024)
    print(f"Done.")
    print(f"  Output file    : {os.path.abspath(args.output)}")
    print(f"  Requested size : {args.size_mb:.1f} MB")
    print(f"  Actual size    : {actual_mb:.2f} MB  ({actual_bytes:,} bytes)")
    print(f"  Valid lines    : {valid_count:,}")
    print(f"  Malformed lines: {malformed_count:,}")


if __name__ == "__main__":
    main()
