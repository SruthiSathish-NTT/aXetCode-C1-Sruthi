"""
tests.test_grep
~~~~~~~~~~~~~~~
Unit and CLI-level tests for the logscope grep command.
"""

from __future__ import annotations

import os
import tempfile
from datetime import datetime

import pytest

from logscope.commands.grep import VALID_LEVELS, GrepResult, parse_since, run
from logscope.cli import main


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_log(lines: list[str]) -> str:
    """Write lines to a temp file and return the path.  Caller must unlink."""
    fd, path = tempfile.mkstemp(suffix=".log", text=True)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.writelines(lines)
    return path


def _ts(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%d %H:%M:%S")


# Reusable mixed sample
_SAMPLE = [
    "2026-10-01 08:59:59 INFO  before window\n",
    "2026-10-01 09:00:00 INFO  start of window\n",
    "2026-10-01 09:00:00 WARN  warn at boundary\n",
    "2026-10-01 09:00:00 ERROR error at boundary\n",
    "2026-10-01 09:05:00 INFO  mid window info\n",
    "2026-10-01 09:05:00 ERROR mid window error\n",
    "2026-10-01 09:10:00 WARN  later warn\n",
    "this is garbage\n",
    "2026-10-01 09:15:00 ERROR late error\n",
]


# ---------------------------------------------------------------------------
# VALID_LEVELS constant
# ---------------------------------------------------------------------------

class TestValidLevels:
    def test_contains_info(self):
        assert "INFO" in VALID_LEVELS

    def test_contains_warn(self):
        assert "WARN" in VALID_LEVELS

    def test_contains_error(self):
        assert "ERROR" in VALID_LEVELS

    def test_is_frozenset(self):
        assert isinstance(VALID_LEVELS, frozenset)

    def test_exactly_three_levels(self):
        assert len(VALID_LEVELS) == 3

    def test_debug_not_valid(self):
        assert "DEBUG" not in VALID_LEVELS

    def test_lowercase_not_valid(self):
        assert "error" not in VALID_LEVELS
        assert "info" not in VALID_LEVELS


# ---------------------------------------------------------------------------
# parse_since
# ---------------------------------------------------------------------------

class TestParseSince:

    def test_valid_format(self):
        dt = parse_since("2026-10-01 09:00")
        assert dt == datetime(2026, 10, 1, 9, 0)

    def test_midnight(self):
        dt = parse_since("2026-01-01 00:00")
        assert dt == datetime(2026, 1, 1, 0, 0)

    def test_end_of_day(self):
        dt = parse_since("2026-12-31 23:59")
        assert dt == datetime(2026, 12, 31, 23, 59)

    def test_returns_datetime(self):
        assert isinstance(parse_since("2026-10-01 09:00"), datetime)

    def test_invalid_includes_seconds(self):
        # YYYY-MM-DD HH:MM:SS is NOT the accepted format
        with pytest.raises(ValueError):
            parse_since("2026-10-01 09:00:00")

    def test_invalid_date_only(self):
        with pytest.raises(ValueError):
            parse_since("2026-10-01")

    def test_invalid_empty_string(self):
        with pytest.raises(ValueError):
            parse_since("")

    def test_invalid_garbage(self):
        with pytest.raises(ValueError):
            parse_since("not-a-date")

    def test_invalid_wrong_separator(self):
        with pytest.raises(ValueError):
            parse_since("2026/10/01 09:00")

    def test_error_message_contains_format_hint(self):
        with pytest.raises(ValueError, match="YYYY-MM-DD HH:MM"):
            parse_since("bad input")


# ---------------------------------------------------------------------------
# run() — filtering by level
# ---------------------------------------------------------------------------

class TestGrepRunLevelFilter:

    def test_filter_error_only(self):
        path = _write_log(_SAMPLE)
        try:
            result = run(path, "ERROR")
        finally:
            os.unlink(path)

        assert all("ERROR" in line for line in result.lines)

    def test_filter_info_only(self):
        path = _write_log(_SAMPLE)
        try:
            result = run(path, "INFO")
        finally:
            os.unlink(path)

        assert all("INFO" in line for line in result.lines)

    def test_filter_warn_only(self):
        path = _write_log(_SAMPLE)
        try:
            result = run(path, "WARN")
        finally:
            os.unlink(path)

        assert all("WARN" in line for line in result.lines)

    def test_error_count_correct(self):
        path = _write_log(_SAMPLE)
        try:
            result = run(path, "ERROR")
        finally:
            os.unlink(path)

        # _SAMPLE has 3 ERROR lines
        assert len(result.lines) == 3

    def test_info_count_correct(self):
        path = _write_log(_SAMPLE)
        try:
            result = run(path, "INFO")
        finally:
            os.unlink(path)

        # _SAMPLE has 3 INFO lines
        assert len(result.lines) == 3

    def test_warn_count_correct(self):
        path = _write_log(_SAMPLE)
        try:
            result = run(path, "WARN")
        finally:
            os.unlink(path)

        # _SAMPLE has 2 WARN lines
        assert len(result.lines) == 2

    def test_invalid_level_raises(self):
        path = _write_log(["2026-10-01 09:00:00 ERROR x\n"])
        try:
            with pytest.raises(ValueError, match="Invalid level"):
                run(path, "DEBUG")
        finally:
            os.unlink(path)

    def test_lowercase_level_raises(self):
        path = _write_log(["2026-10-01 09:00:00 ERROR x\n"])
        try:
            with pytest.raises(ValueError):
                run(path, "error")
        finally:
            os.unlink(path)

    def test_empty_level_raises(self):
        path = _write_log(["2026-10-01 09:00:00 ERROR x\n"])
        try:
            with pytest.raises(ValueError):
                run(path, "")
        finally:
            os.unlink(path)

    def test_invalid_level_raises_before_opening_file(self):
        """ValueError must be raised even if the file does not exist."""
        with pytest.raises(ValueError):
            run("/tmp/logscope_no_such_file.log", "BAD")


# ---------------------------------------------------------------------------
# run() — --since filtering
# ---------------------------------------------------------------------------

class TestGrepRunSinceFilter:

    def test_since_at_exact_boundary_inclusive(self):
        """Entry at exactly the --since timestamp must be included."""
        lines = [
            "2026-10-01 09:00:00 ERROR exactly at boundary\n",
            "2026-10-01 09:00:01 ERROR after boundary\n",
        ]
        path = _write_log(lines)
        try:
            result = run(path, "ERROR", since=datetime(2026, 10, 1, 9, 0))
        finally:
            os.unlink(path)

        assert len(result.lines) == 2
        assert "exactly at boundary" in result.lines[0]

    def test_since_excludes_entries_before(self):
        lines = [
            "2026-10-01 08:59:59 ERROR before\n",
            "2026-10-01 09:00:00 ERROR at boundary\n",
            "2026-10-01 09:01:00 ERROR after\n",
        ]
        path = _write_log(lines)
        try:
            result = run(path, "ERROR", since=datetime(2026, 10, 1, 9, 0))
        finally:
            os.unlink(path)

        assert len(result.lines) == 2
        assert not any("before" in line for line in result.lines)

    def test_since_before_all_entries_returns_all(self):
        lines = [
            "2026-10-01 10:00:00 ERROR a\n",
            "2026-10-01 11:00:00 ERROR b\n",
        ]
        path = _write_log(lines)
        try:
            result = run(path, "ERROR", since=datetime(2026, 1, 1, 0, 0))
        finally:
            os.unlink(path)

        assert len(result.lines) == 2

    def test_since_after_all_entries_returns_none(self):
        lines = [
            "2026-10-01 08:00:00 ERROR a\n",
            "2026-10-01 08:30:00 ERROR b\n",
        ]
        path = _write_log(lines)
        try:
            result = run(path, "ERROR", since=datetime(2026, 10, 1, 9, 0))
        finally:
            os.unlink(path)

        assert result.lines == []

    def test_since_within_range(self):
        lines = [
            "2026-10-01 09:00:00 ERROR first\n",
            "2026-10-01 09:30:00 ERROR mid\n",
            "2026-10-01 10:00:00 ERROR last\n",
        ]
        path = _write_log(lines)
        try:
            result = run(path, "ERROR", since=datetime(2026, 10, 1, 9, 30))
        finally:
            os.unlink(path)

        assert len(result.lines) == 2
        assert "mid" in result.lines[0]
        assert "last" in result.lines[1]

    def test_no_since_returns_all_matching(self):
        lines = [
            "2026-10-01 09:00:00 ERROR a\n",
            "2026-10-01 09:01:00 ERROR b\n",
        ]
        path = _write_log(lines)
        try:
            result = run(path, "ERROR", since=None)
        finally:
            os.unlink(path)

        assert len(result.lines) == 2

    def test_since_with_level_filter_combined(self):
        """--since and --level must both be applied."""
        path = _write_log(_SAMPLE)
        try:
            # since 09:00 → excludes the 08:59:59 INFO line
            result = run(path, "ERROR", since=datetime(2026, 10, 1, 9, 0))
        finally:
            os.unlink(path)

        # All returned lines are ERROR and at or after 09:00:00
        assert all("ERROR" in line for line in result.lines)
        assert len(result.lines) == 3


# ---------------------------------------------------------------------------
# run() — raw line fidelity and ordering
# ---------------------------------------------------------------------------

class TestGrepRunRawOutput:

    def test_raw_line_preserved_exactly(self):
        raw = "2026-10-01 09:00:00 ERROR  message with   spaces"
        path = _write_log([raw + "\n"])
        try:
            result = run(path, "ERROR")
        finally:
            os.unlink(path)

        assert result.lines == [raw]

    def test_no_trailing_newline_in_output(self):
        path = _write_log(["2026-10-01 09:00:00 ERROR msg\n"])
        try:
            result = run(path, "ERROR")
        finally:
            os.unlink(path)

        assert not result.lines[0].endswith("\n")

    def test_order_preserved(self):
        lines = [
            "2026-10-01 09:00:00 ERROR first\n",
            "2026-10-01 09:01:00 ERROR second\n",
            "2026-10-01 09:02:00 ERROR third\n",
        ]
        path = _write_log(lines)
        try:
            result = run(path, "ERROR")
        finally:
            os.unlink(path)

        assert "first" in result.lines[0]
        assert "second" in result.lines[1]
        assert "third" in result.lines[2]


# ---------------------------------------------------------------------------
# run() — edge cases
# ---------------------------------------------------------------------------

class TestGrepRunEdgeCases:

    def test_empty_file(self):
        path = _write_log([])
        try:
            result = run(path, "ERROR")
        finally:
            os.unlink(path)

        assert result.lines == []
        assert result.malformed == 0

    def test_all_malformed_no_crash(self):
        lines = [f"garbage {i}\n" for i in range(20)]
        path = _write_log(lines)
        try:
            result = run(path, "ERROR")
        finally:
            os.unlink(path)

        assert result.lines == []
        assert result.malformed == 20

    def test_malformed_counted_alongside_matches(self):
        lines = [
            "bad line\n",
            "2026-10-01 09:00:00 ERROR good\n",
            "also bad\n",
        ]
        path = _write_log(lines)
        try:
            result = run(path, "ERROR")
        finally:
            os.unlink(path)

        assert len(result.lines) == 1
        assert result.malformed == 2

    def test_zero_matches_no_crash(self):
        lines = [
            "2026-10-01 09:00:00 INFO  only info\n",
            "2026-10-01 09:01:00 WARN  only warn\n",
        ]
        path = _write_log(lines)
        try:
            result = run(path, "ERROR")
        finally:
            os.unlink(path)

        assert result.lines == []
        assert result.malformed == 0

    def test_missing_file_raises(self):
        with pytest.raises((FileNotFoundError, OSError)):
            run("/tmp/logscope_no_such_file_grep.log", "ERROR")

    def test_returns_grep_result_type(self):
        path = _write_log(["2026-10-01 09:00:00 ERROR x\n"])
        try:
            result = run(path, "ERROR")
        finally:
            os.unlink(path)

        assert isinstance(result, GrepResult)

    def test_only_malformed_lines_file(self):
        lines = ["garbage\n", "more garbage\n"]
        path = _write_log(lines)
        try:
            result = run(path, "ERROR")
        finally:
            os.unlink(path)

        assert result.lines == []
        assert result.malformed == 2


# ---------------------------------------------------------------------------
# CLI-level tests
# ---------------------------------------------------------------------------

class TestGrepCLI:

    def test_cli_prints_matching_line(self, capsys):
        path = _write_log(["2026-10-01 09:00:00 ERROR database down\n"])
        try:
            main(["grep", path, "--level", "ERROR"])
        finally:
            os.unlink(path)

        out = capsys.readouterr().out
        assert "database down" in out

    def test_cli_prints_header_with_level(self, capsys):
        path = _write_log(["2026-10-01 09:00:00 ERROR x\n"])
        try:
            main(["grep", path, "--level", "ERROR"])
        finally:
            os.unlink(path)

        out = capsys.readouterr().out
        assert "ERROR" in out

    def test_cli_shows_match_count(self, capsys):
        lines = [
            "2026-10-01 09:00:00 ERROR a\n",
            "2026-10-01 09:01:00 ERROR b\n",
        ]
        path = _write_log(lines)
        try:
            main(["grep", path, "--level", "ERROR"])
        finally:
            os.unlink(path)

        out = capsys.readouterr().out
        assert "2" in out

    def test_cli_shows_malformed_count(self, capsys):
        lines = [
            "garbage\n",
            "2026-10-01 09:00:00 ERROR x\n",
        ]
        path = _write_log(lines)
        try:
            main(["grep", path, "--level", "ERROR"])
        finally:
            os.unlink(path)

        out = capsys.readouterr().out
        assert "Malformed" in out
        assert "1" in out

    def test_cli_zero_matches_no_crash(self, capsys):
        path = _write_log(["2026-10-01 09:00:00 INFO  only info\n"])
        try:
            main(["grep", path, "--level", "ERROR"])
        finally:
            os.unlink(path)

        out = capsys.readouterr().out
        assert "no matching" in out.lower() or "0" in out

    def test_cli_since_filters_correctly(self, capsys):
        lines = [
            "2026-10-01 08:00:00 ERROR before\n",
            "2026-10-01 09:00:00 ERROR after\n",
        ]
        path = _write_log(lines)
        try:
            main(["grep", path, "--level", "ERROR", "--since", "2026-10-01 09:00"])
        finally:
            os.unlink(path)

        out = capsys.readouterr().out
        assert "after" in out
        assert "before" not in out

    def test_cli_since_boundary_inclusive(self, capsys):
        """Entry exactly at --since must appear in output."""
        path = _write_log(["2026-10-01 09:00:00 ERROR exactly at boundary\n"])
        try:
            main(["grep", path, "--level", "ERROR", "--since", "2026-10-01 09:00"])
        finally:
            os.unlink(path)

        out = capsys.readouterr().out
        assert "exactly at boundary" in out

    def test_cli_shows_since_in_header(self, capsys):
        path = _write_log(["2026-10-01 09:00:00 ERROR x\n"])
        try:
            main(["grep", path, "--level", "ERROR", "--since", "2026-10-01 09:00"])
        finally:
            os.unlink(path)

        out = capsys.readouterr().out
        assert "2026-10-01 09:00" in out

    def test_cli_empty_file_no_crash(self, capsys):
        path = _write_log([])
        try:
            main(["grep", path, "--level", "ERROR"])
        finally:
            os.unlink(path)

        out = capsys.readouterr().out
        assert "Malformed" in out

    def test_cli_all_malformed_no_crash(self, capsys):
        path = _write_log(["junk\n"] * 3)
        try:
            main(["grep", path, "--level", "ERROR"])
        finally:
            os.unlink(path)

        out = capsys.readouterr().out
        assert "3" in out

    def test_cli_invalid_level_exits_nonzero(self, capsys):
        path = _write_log(["2026-10-01 09:00:00 ERROR x\n"])
        try:
            with pytest.raises(SystemExit) as exc_info:
                main(["grep", path, "--level", "DEBUG"])
        finally:
            os.unlink(path)

        assert exc_info.value.code != 0

    def test_cli_invalid_level_stderr_message(self, capsys):
        path = _write_log(["2026-10-01 09:00:00 ERROR x\n"])
        try:
            with pytest.raises(SystemExit):
                main(["grep", path, "--level", "DEBUG"])
        finally:
            os.unlink(path)

        err = capsys.readouterr().err
        assert "error" in err.lower()

    def test_cli_invalid_since_exits_nonzero(self, capsys):
        path = _write_log(["2026-10-01 09:00:00 ERROR x\n"])
        try:
            with pytest.raises(SystemExit) as exc_info:
                main(["grep", path, "--level", "ERROR", "--since", "not-a-date"])
        finally:
            os.unlink(path)

        assert exc_info.value.code != 0

    def test_cli_invalid_since_stderr_message(self, capsys):
        path = _write_log(["2026-10-01 09:00:00 ERROR x\n"])
        try:
            with pytest.raises(SystemExit):
                main(["grep", path, "--level", "ERROR", "--since", "not-a-date"])
        finally:
            os.unlink(path)

        err = capsys.readouterr().err
        assert "error" in err.lower()

    def test_cli_since_with_seconds_rejected(self, capsys):
        """HH:MM:SS format must be rejected (spec requires HH:MM only)."""
        path = _write_log(["2026-10-01 09:00:00 ERROR x\n"])
        try:
            with pytest.raises(SystemExit) as exc_info:
                main(["grep", path, "--level", "ERROR", "--since", "2026-10-01 09:00:00"])
        finally:
            os.unlink(path)

        assert exc_info.value.code != 0

    def test_cli_missing_file_exits_nonzero(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            main(["grep", "/tmp/logscope_no_such_file_grep.log", "--level", "ERROR"])

        assert exc_info.value.code != 0

    def test_cli_missing_file_stderr_message(self, capsys):
        with pytest.raises(SystemExit):
            main(["grep", "/tmp/logscope_no_such_file_grep.log", "--level", "ERROR"])

        err = capsys.readouterr().err
        assert "error" in err.lower()

    def test_cli_info_level_filter(self, capsys):
        lines = [
            "2026-10-01 09:00:00 INFO  info line\n",
            "2026-10-01 09:00:01 ERROR error line\n",
        ]
        path = _write_log(lines)
        try:
            main(["grep", path, "--level", "INFO"])
        finally:
            os.unlink(path)

        out = capsys.readouterr().out
        assert "info line" in out
        assert "error line" not in out

    def test_cli_warn_level_filter(self, capsys):
        lines = [
            "2026-10-01 09:00:00 WARN  warn line\n",
            "2026-10-01 09:00:01 ERROR error line\n",
        ]
        path = _write_log(lines)
        try:
            main(["grep", path, "--level", "WARN"])
        finally:
            os.unlink(path)

        out = capsys.readouterr().out
        assert "warn line" in out
        assert "error line" not in out

    def test_cli_output_preserves_raw_line(self, capsys):
        raw = "2026-10-01 09:00:00 ERROR  message with   spaces inside"
        path = _write_log([raw + "\n"])
        try:
            main(["grep", path, "--level", "ERROR"])
        finally:
            os.unlink(path)

        out = capsys.readouterr().out
        assert raw in out
