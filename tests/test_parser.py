"""
tests.test_parser
~~~~~~~~~~~~~~~~~
Unit tests for logscope.parser — parse_line and iter_log.
"""

from __future__ import annotations

import os
import tempfile
from datetime import datetime

import pytest

from logscope.parser import (
    VALID_LEVELS,
    LogEntry,
    MalformedLine,
    iter_log,
    parse_line,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ts(s: str) -> datetime:
    """Build a datetime from a compact string like '2026-10-01 09:05:10'."""
    return datetime.strptime(s, "%Y-%m-%d %H:%M:%S")


def _write_log(lines: list[str]) -> str:
    """Write lines to a temp file; return the path."""
    fd, path = tempfile.mkstemp(suffix=".log", text=True)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.writelines(lines)
    return path


# ---------------------------------------------------------------------------
# parse_line — happy path
# ---------------------------------------------------------------------------

class TestParseLineValid:
    def test_info_line(self):
        entry = parse_line("2026-10-01 09:00:01 INFO Application started\n")
        assert isinstance(entry, LogEntry)
        assert entry.timestamp == _ts("2026-10-01 09:00:01")
        assert entry.level == "INFO"
        assert entry.message == "Application started"

    def test_warn_line(self):
        entry = parse_line("2026-10-01 09:06:00 WARN Retry attempt 1\n")
        assert isinstance(entry, LogEntry)
        assert entry.level == "WARN"
        assert entry.message == "Retry attempt 1"

    def test_error_line(self):
        entry = parse_line("2026-10-01 09:05:10 ERROR Database connection refused\n")
        assert isinstance(entry, LogEntry)
        assert entry.level == "ERROR"
        assert entry.message == "Database connection refused"

    def test_message_with_multiple_spaces(self):
        line = "2026-10-01 10:00:00 INFO msg with   many   spaces"
        entry = parse_line(line)
        assert isinstance(entry, LogEntry)
        assert entry.message == "msg with   many   spaces"

    def test_raw_field_strips_newline(self):
        line = "2026-10-01 10:00:00 INFO hello\n"
        entry = parse_line(line)
        assert isinstance(entry, LogEntry)
        assert entry.raw == "2026-10-01 10:00:00 INFO hello"

    def test_raw_field_no_newline(self):
        line = "2026-10-01 10:00:00 INFO hello"
        entry = parse_line(line)
        assert isinstance(entry, LogEntry)
        assert entry.raw == line

    def test_windows_line_ending(self):
        line = "2026-10-01 10:00:00 INFO crlf\r\n"
        entry = parse_line(line)
        assert isinstance(entry, LogEntry)
        assert entry.raw == "2026-10-01 10:00:00 INFO crlf"

    def test_all_valid_levels(self):
        for level in ("INFO", "WARN", "ERROR"):
            entry = parse_line(f"2026-01-01 00:00:00 {level} test")
            assert isinstance(entry, LogEntry)
            assert entry.level == level

    def test_timestamp_precision(self):
        entry = parse_line("2026-12-31 23:59:59 ERROR midnight edge")
        assert isinstance(entry, LogEntry)
        assert entry.timestamp == _ts("2026-12-31 23:59:59")


# ---------------------------------------------------------------------------
# parse_line — malformed inputs
# ---------------------------------------------------------------------------

class TestParseLineMalformed:
    def test_empty_line(self):
        assert isinstance(parse_line(""), MalformedLine)

    def test_whitespace_only(self):
        assert isinstance(parse_line("   \n"), MalformedLine)

    def test_missing_message_field(self):
        # Only 3 tokens — message missing.
        assert isinstance(parse_line("2026-10-01 09:00:00 INFO"), MalformedLine)

    def test_invalid_level(self):
        assert isinstance(parse_line("2026-10-01 09:00:00 DEBUG something"), MalformedLine)

    def test_lowercase_level(self):
        assert isinstance(parse_line("2026-10-01 09:00:00 info something"), MalformedLine)

    def test_bad_date_format(self):
        assert isinstance(parse_line("01-10-2026 09:00:00 INFO bad date"), MalformedLine)

    def test_bad_time_format(self):
        assert isinstance(parse_line("2026-10-01 9:00 INFO bad time"), MalformedLine)

    def test_impossible_date(self):
        assert isinstance(parse_line("2026-13-01 09:00:00 INFO bad month"), MalformedLine)

    def test_impossible_time(self):
        assert isinstance(parse_line("2026-10-01 25:00:00 INFO bad hour"), MalformedLine)

    def test_garbage_line(self):
        assert isinstance(parse_line("xxxxxxxxxxxxxxxxxxxxxxxxxxx"), MalformedLine)

    def test_random_json(self):
        assert isinstance(parse_line('{"key": "value", "n": 42}'), MalformedLine)

    def test_partial_timestamp(self):
        assert isinstance(parse_line("2026-10-01 ERROR something"), MalformedLine)

    def test_raw_field_preserved_on_malformed(self):
        raw = "this is garbage"
        result = parse_line(raw)
        assert isinstance(result, MalformedLine)
        assert result.raw == raw

    def test_level_with_trailing_colon(self):
        assert isinstance(parse_line("2026-10-01 09:00:00 ERROR: message"), MalformedLine)


# ---------------------------------------------------------------------------
# iter_log — file streaming
# ---------------------------------------------------------------------------

class TestIterLog:
    def test_yields_correct_types(self):
        lines = [
            "2026-10-01 09:00:01 INFO Application started\n",
            "this is garbage\n",
            "2026-10-01 09:05:10 ERROR Database connection refused\n",
        ]
        path = _write_log(lines)
        try:
            results = list(iter_log(path))
        finally:
            os.unlink(path)

        assert len(results) == 3
        assert isinstance(results[0], LogEntry)
        assert isinstance(results[1], MalformedLine)
        assert isinstance(results[2], LogEntry)

    def test_all_valid_lines(self):
        lines = [
            "2026-10-01 09:00:01 INFO line one\n",
            "2026-10-01 09:00:02 WARN line two\n",
            "2026-10-01 09:00:03 ERROR line three\n",
        ]
        path = _write_log(lines)
        try:
            results = list(iter_log(path))
        finally:
            os.unlink(path)

        assert all(isinstance(r, LogEntry) for r in results)
        assert [r.level for r in results] == ["INFO", "WARN", "ERROR"]

    def test_all_malformed_lines(self):
        lines = ["garbage\n", "more garbage\n", "\n"]
        path = _write_log(lines)
        try:
            results = list(iter_log(path))
        finally:
            os.unlink(path)

        assert all(isinstance(r, MalformedLine) for r in results)

    def test_empty_file(self):
        path = _write_log([])
        try:
            results = list(iter_log(path))
        finally:
            os.unlink(path)

        assert results == []

    def test_single_line_no_newline(self):
        path = _write_log(["2026-10-01 09:00:00 INFO no newline at eof"])
        try:
            results = list(iter_log(path))
        finally:
            os.unlink(path)

        assert len(results) == 1
        assert isinstance(results[0], LogEntry)

    def test_malformed_line_does_not_crash(self):
        """A file full of garbage must be processed without exception."""
        lines = [f"garbage line {i}\n" for i in range(100)]
        path = _write_log(lines)
        try:
            results = list(iter_log(path))
        finally:
            os.unlink(path)

        assert len(results) == 100
        assert all(isinstance(r, MalformedLine) for r in results)

    def test_mixed_malformed_count(self):
        lines = [
            "2026-10-01 09:00:01 INFO ok\n",
            "bad\n",
            "2026-10-01 09:00:02 ERROR ok\n",
            "also bad\n",
        ]
        path = _write_log(lines)
        try:
            results = list(iter_log(path))
        finally:
            os.unlink(path)

        malformed = sum(1 for r in results if isinstance(r, MalformedLine))
        good = sum(1 for r in results if isinstance(r, LogEntry))
        assert malformed == 2
        assert good == 2

    def test_iter_log_is_generator(self):
        """iter_log must return a generator, not a fully-materialised list."""
        import types
        lines = ["2026-10-01 09:00:00 INFO hello\n"]
        path = _write_log(lines)
        try:
            result = iter_log(path)
            assert isinstance(result, types.GeneratorType)
            # Consume it to close file handle cleanly.
            list(result)
        finally:
            os.unlink(path)

    def test_line_order_preserved(self):
        messages = ["first", "second", "third"]
        lines = [f"2026-10-01 09:00:0{i+1} INFO {msg}\n" for i, msg in enumerate(messages)]
        path = _write_log(lines)
        try:
            results = list(iter_log(path))
        finally:
            os.unlink(path)

        assert [r.message for r in results] == messages

    def test_non_utf8_bytes_do_not_crash(self):
        """Binary garbage in the file must not raise; lines become MalformedLine."""
        fd, path = tempfile.mkstemp(suffix=".log")
        try:
            with os.fdopen(fd, "wb") as fh:
                fh.write(b"\xff\xfe bad bytes\n")
                fh.write(b"2026-10-01 09:00:00 INFO after bytes\n")
            results = list(iter_log(path))
        finally:
            os.unlink(path)

        # The second line should parse fine; the first will be malformed.
        assert any(isinstance(r, LogEntry) for r in results)


# ---------------------------------------------------------------------------
# VALID_LEVELS constant
# ---------------------------------------------------------------------------

class TestValidLevels:
    def test_contains_expected_levels(self):
        assert VALID_LEVELS == {"INFO", "WARN", "ERROR"}

    def test_is_frozenset(self):
        assert isinstance(VALID_LEVELS, frozenset)
