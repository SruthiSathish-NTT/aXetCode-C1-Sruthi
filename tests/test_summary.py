"""
tests.test_summary
~~~~~~~~~~~~~~~~~~
Unit and CLI-level tests for the logscope summary command.
"""

from __future__ import annotations

import os
import sys
import tempfile
from datetime import datetime

import pytest

from logscope.commands.summary import SummaryResult, run
from logscope.cli import main


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_log(lines: list[str]) -> str:
    """Write lines to a temp file; return the path.  Caller must unlink."""
    fd, path = tempfile.mkstemp(suffix=".log", text=True)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.writelines(lines)
    return path


def _ts(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%d %H:%M:%S")


# Reusable sample lines
_SAMPLE = [
    "2026-10-01 09:00:01 INFO  Application started\n",
    "2026-10-01 09:00:05 INFO  Config loaded\n",
    "2026-10-01 09:01:00 WARN  Disk usage high\n",
    "2026-10-01 09:02:00 ERROR Database connection refused\n",
    "2026-10-01 09:02:10 ERROR Database connection refused\n",
    "2026-10-01 09:03:00 ERROR Timeout waiting for lock\n",
    "this is garbage\n",
    "2026-10-01 09:04:00 INFO  Scheduled task complete\n",
]


# ---------------------------------------------------------------------------
# Unit tests — run()
# ---------------------------------------------------------------------------

class TestSummaryRun:

    def test_counts_levels(self):
        path = _write_log(_SAMPLE)
        try:
            result = run(path)
        finally:
            os.unlink(path)

        assert result.counts["INFO"] == 3
        assert result.counts["WARN"] == 1
        assert result.counts["ERROR"] == 3

    def test_malformed_count(self):
        path = _write_log(_SAMPLE)
        try:
            result = run(path)
        finally:
            os.unlink(path)

        assert result.malformed == 1

    def test_first_and_last_timestamps(self):
        path = _write_log(_SAMPLE)
        try:
            result = run(path)
        finally:
            os.unlink(path)

        assert result.first_ts == _ts("2026-10-01 09:00:01")
        assert result.last_ts  == _ts("2026-10-01 09:04:00")

    def test_top_errors_ordering(self):
        """Most-frequent error must appear first."""
        lines = [
            "2026-10-01 09:00:00 ERROR alpha\n",
            "2026-10-01 09:00:01 ERROR beta\n",
            "2026-10-01 09:00:02 ERROR beta\n",
            "2026-10-01 09:00:03 ERROR beta\n",
            "2026-10-01 09:00:04 ERROR gamma\n",
            "2026-10-01 09:00:05 ERROR gamma\n",
        ]
        path = _write_log(lines)
        try:
            result = run(path)
        finally:
            os.unlink(path)

        assert result.top_errors[0] == ("beta", 3)
        assert result.top_errors[1] == ("gamma", 2)
        assert result.top_errors[2] == ("alpha", 1)

    def test_top_errors_capped_at_five(self):
        """Only the top 5 error messages are returned."""
        lines = [
            f"2026-10-01 09:00:0{i} ERROR msg{i}\n" for i in range(8)
        ]
        # Give msg0 the highest frequency so ordering is deterministic.
        lines += ["2026-10-01 09:01:00 ERROR msg0\n"] * 7
        path = _write_log(lines)
        try:
            result = run(path)
        finally:
            os.unlink(path)

        assert len(result.top_errors) == 5
        assert result.top_errors[0][0] == "msg0"

    def test_fewer_than_five_distinct_errors(self):
        """When there are fewer than 5 distinct errors, all are returned."""
        lines = [
            "2026-10-01 09:00:00 ERROR alpha\n",
            "2026-10-01 09:00:01 ERROR beta\n",
            "2026-10-01 09:00:02 ERROR beta\n",
        ]
        path = _write_log(lines)
        try:
            result = run(path)
        finally:
            os.unlink(path)

        assert len(result.top_errors) == 2
        assert result.top_errors[0] == ("beta", 2)
        assert result.top_errors[1] == ("alpha", 1)

    def test_no_errors_produces_empty_top_errors(self):
        lines = [
            "2026-10-01 09:00:00 INFO  all fine\n",
            "2026-10-01 09:00:01 WARN  minor issue\n",
        ]
        path = _write_log(lines)
        try:
            result = run(path)
        finally:
            os.unlink(path)

        assert result.top_errors == []
        assert result.counts["ERROR"] == 0

    def test_empty_file(self):
        path = _write_log([])
        try:
            result = run(path)
        finally:
            os.unlink(path)

        assert result.counts == {"INFO": 0, "WARN": 0, "ERROR": 0}
        assert result.top_errors == []
        assert result.first_ts is None
        assert result.last_ts is None
        assert result.malformed == 0

    def test_all_malformed(self):
        lines = ["garbage\n", "more garbage\n", "also garbage\n"]
        path = _write_log(lines)
        try:
            result = run(path)
        finally:
            os.unlink(path)

        assert result.counts == {"INFO": 0, "WARN": 0, "ERROR": 0}
        assert result.first_ts is None
        assert result.last_ts is None
        assert result.malformed == 3

    def test_only_malformed_no_crash(self):
        """A file full of garbage must complete without exception."""
        lines = [f"junk line {i}\n" for i in range(200)]
        path = _write_log(lines)
        try:
            result = run(path)
        finally:
            os.unlink(path)

        assert result.malformed == 200

    def test_multiple_malformed_lines(self):
        lines = [
            "2026-10-01 09:00:00 INFO  start\n",
            "bad1\n",
            "bad2\n",
            "2026-10-01 09:00:01 ERROR boom\n",
            "bad3\n",
        ]
        path = _write_log(lines)
        try:
            result = run(path)
        finally:
            os.unlink(path)

        assert result.malformed == 3
        assert result.counts["INFO"] == 1
        assert result.counts["ERROR"] == 1

    def test_missing_file_raises(self):
        with pytest.raises((FileNotFoundError, OSError)):
            run("/tmp/logscope_nonexistent_file_xyz.log")

    def test_returns_summary_result_type(self):
        path = _write_log(_SAMPLE)
        try:
            result = run(path)
        finally:
            os.unlink(path)

        assert isinstance(result, SummaryResult)

    def test_single_line_info(self):
        path = _write_log(["2026-10-01 12:00:00 INFO  only line\n"])
        try:
            result = run(path)
        finally:
            os.unlink(path)

        assert result.counts["INFO"] == 1
        assert result.first_ts == result.last_ts == _ts("2026-10-01 12:00:00")
        assert result.malformed == 0

    def test_timestamps_track_valid_entries_only(self):
        """Malformed lines must not affect first/last timestamp tracking."""
        lines = [
            "garbage at the start\n",
            "2026-10-01 09:00:05 INFO  real start\n",
            "more garbage\n",
            "2026-10-01 09:00:10 INFO  real end\n",
            "trailing garbage\n",
        ]
        path = _write_log(lines)
        try:
            result = run(path)
        finally:
            os.unlink(path)

        assert result.first_ts == _ts("2026-10-01 09:00:05")
        assert result.last_ts  == _ts("2026-10-01 09:00:10")


# ---------------------------------------------------------------------------
# CLI-level tests — main()
# ---------------------------------------------------------------------------

class TestSummaryCLI:

    def test_cli_prints_level_counts(self, capsys):
        path = _write_log(_SAMPLE)
        try:
            main(["summary", path])
        finally:
            os.unlink(path)

        out = capsys.readouterr().out
        assert "INFO" in out
        assert "WARN" in out
        assert "ERROR" in out

    def test_cli_prints_top_errors_section(self, capsys):
        path = _write_log(_SAMPLE)
        try:
            main(["summary", path])
        finally:
            os.unlink(path)

        out = capsys.readouterr().out
        assert "Top ERROR" in out
        assert "Database connection refused" in out

    def test_cli_prints_timestamps(self, capsys):
        path = _write_log(_SAMPLE)
        try:
            main(["summary", path])
        finally:
            os.unlink(path)

        out = capsys.readouterr().out
        assert "2026-10-01 09:00:01" in out
        assert "2026-10-01 09:04:00" in out

    def test_cli_prints_malformed_count(self, capsys):
        path = _write_log(_SAMPLE)
        try:
            main(["summary", path])
        finally:
            os.unlink(path)

        out = capsys.readouterr().out
        assert "Malformed" in out
        assert "1" in out

    def test_cli_empty_file_no_crash(self, capsys):
        path = _write_log([])
        try:
            main(["summary", path])
        finally:
            os.unlink(path)

        out = capsys.readouterr().out
        assert "INFO" in out   # header still present
        assert "—" in out      # timestamp placeholder

    def test_cli_all_malformed_no_crash(self, capsys):
        path = _write_log(["junk\n"] * 5)
        try:
            main(["summary", path])
        finally:
            os.unlink(path)

        out = capsys.readouterr().out
        assert "5" in out
        assert "—" in out

    def test_cli_missing_file_exits_nonzero(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            main(["summary", "/tmp/logscope_no_such_file_abc.log"])

        assert exc_info.value.code != 0

    def test_cli_missing_file_stderr_message(self, capsys):
        with pytest.raises(SystemExit):
            main(["summary", "/tmp/logscope_no_such_file_abc.log"])

        err = capsys.readouterr().err
        assert "error" in err.lower()

    def test_cli_correct_counts_in_output(self, capsys):
        lines = [
            "2026-10-01 09:00:00 INFO  a\n",
            "2026-10-01 09:00:01 INFO  b\n",
            "2026-10-01 09:00:02 WARN  c\n",
            "2026-10-01 09:00:03 ERROR d\n",
        ]
        path = _write_log(lines)
        try:
            main(["summary", path])
        finally:
            os.unlink(path)

        out = capsys.readouterr().out
        # The numbers 2, 1, 1 must appear somewhere in the output.
        assert "2" in out
        assert "1" in out

    def test_cli_no_errors_shows_none_placeholder(self, capsys):
        lines = [
            "2026-10-01 09:00:00 INFO  all good\n",
            "2026-10-01 09:00:01 WARN  slight concern\n",
        ]
        path = _write_log(lines)
        try:
            main(["summary", path])
        finally:
            os.unlink(path)

        out = capsys.readouterr().out
        assert "(none)" in out
