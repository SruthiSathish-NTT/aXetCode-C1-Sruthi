"""
tests.test_timeline
~~~~~~~~~~~~~~~~~~~
Unit and CLI-level tests for the logscope timeline command.
"""

from __future__ import annotations

import os
import tempfile
from datetime import datetime, timedelta

import pytest

from logscope.commands.timeline import (
    TimelineResult,
    bucket_key,
    parse_bucket,
    run,
)
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


# ---------------------------------------------------------------------------
# parse_bucket
# ---------------------------------------------------------------------------

class TestParseBucket:

    def test_15m(self):
        assert parse_bucket("15m") == timedelta(minutes=15)

    def test_1h(self):
        assert parse_bucket("1h") == timedelta(hours=1)

    def test_5m(self):
        assert parse_bucket("5m") == timedelta(minutes=5)

    def test_2h(self):
        assert parse_bucket("2h") == timedelta(hours=2)

    def test_60m(self):
        assert parse_bucket("60m") == timedelta(hours=1)

    def test_1m(self):
        assert parse_bucket("1m") == timedelta(minutes=1)

    def test_leading_whitespace_stripped(self):
        # strip() is applied inside parse_bucket
        assert parse_bucket(" 15m") == timedelta(minutes=15)

    def test_invalid_no_unit(self):
        with pytest.raises(ValueError):
            parse_bucket("15")

    def test_invalid_wrong_unit(self):
        with pytest.raises(ValueError):
            parse_bucket("15s")

    def test_invalid_empty_string(self):
        with pytest.raises(ValueError):
            parse_bucket("")

    def test_invalid_zero(self):
        with pytest.raises(ValueError):
            parse_bucket("0m")

    def test_invalid_letters_only(self):
        with pytest.raises(ValueError):
            parse_bucket("abc")

    def test_invalid_negative(self):
        with pytest.raises(ValueError):
            parse_bucket("-5m")


# ---------------------------------------------------------------------------
# bucket_key — boundary assignment
# ---------------------------------------------------------------------------

class TestBucketKey:

    # 15-minute boundaries
    def test_15m_exact_boundary(self):
        assert bucket_key(_ts("2026-10-01 09:00:00"), timedelta(minutes=15)) == _ts("2026-10-01 09:00:00")

    def test_15m_one_second_before_next(self):
        assert bucket_key(_ts("2026-10-01 09:14:59"), timedelta(minutes=15)) == _ts("2026-10-01 09:00:00")

    def test_15m_next_boundary(self):
        assert bucket_key(_ts("2026-10-01 09:15:00"), timedelta(minutes=15)) == _ts("2026-10-01 09:15:00")

    def test_15m_mid_bucket(self):
        assert bucket_key(_ts("2026-10-01 09:07:30"), timedelta(minutes=15)) == _ts("2026-10-01 09:00:00")

    def test_15m_third_bucket(self):
        assert bucket_key(_ts("2026-10-01 09:30:00"), timedelta(minutes=15)) == _ts("2026-10-01 09:30:00")

    def test_15m_fourth_bucket_inside(self):
        assert bucket_key(_ts("2026-10-01 09:44:59"), timedelta(minutes=15)) == _ts("2026-10-01 09:30:00")

    # 1-hour boundaries
    def test_1h_exact_boundary(self):
        assert bucket_key(_ts("2026-10-01 09:00:00"), timedelta(hours=1)) == _ts("2026-10-01 09:00:00")

    def test_1h_one_second_before_next(self):
        assert bucket_key(_ts("2026-10-01 09:59:59"), timedelta(hours=1)) == _ts("2026-10-01 09:00:00")

    def test_1h_next_boundary(self):
        assert bucket_key(_ts("2026-10-01 10:00:00"), timedelta(hours=1)) == _ts("2026-10-01 10:00:00")

    def test_1h_mid_bucket(self):
        assert bucket_key(_ts("2026-10-01 09:30:00"), timedelta(hours=1)) == _ts("2026-10-01 09:00:00")

    # Spec examples verbatim
    def test_spec_example_09_00_00_15m(self):
        assert bucket_key(_ts("2026-10-01 09:00:00"), timedelta(minutes=15)) == _ts("2026-10-01 09:00:00")

    def test_spec_example_09_14_59_15m(self):
        assert bucket_key(_ts("2026-10-01 09:14:59"), timedelta(minutes=15)) == _ts("2026-10-01 09:00:00")

    def test_spec_example_09_15_00_15m(self):
        assert bucket_key(_ts("2026-10-01 09:15:00"), timedelta(minutes=15)) == _ts("2026-10-01 09:15:00")

    def test_spec_example_09_59_59_1h(self):
        assert bucket_key(_ts("2026-10-01 09:59:59"), timedelta(hours=1)) == _ts("2026-10-01 09:00:00")


# ---------------------------------------------------------------------------
# run() — aggregation
# ---------------------------------------------------------------------------

class TestTimelineRun:

    def test_counts_only_errors(self):
        lines = [
            "2026-10-01 09:00:00 INFO  ignored\n",
            "2026-10-01 09:00:01 WARN  ignored\n",
            "2026-10-01 09:00:02 ERROR counted\n",
        ]
        path = _write_log(lines)
        try:
            result = run(path, "15m")
        finally:
            os.unlink(path)

        total = sum(result.buckets.values())
        assert total == 1

    def test_info_and_warn_not_counted(self):
        lines = [
            "2026-10-01 09:00:00 INFO  a\n",
            "2026-10-01 09:00:01 INFO  b\n",
            "2026-10-01 09:00:02 WARN  c\n",
        ]
        path = _write_log(lines)
        try:
            result = run(path, "15m")
        finally:
            os.unlink(path)

        assert result.buckets == {}

    def test_single_error_goes_to_correct_bucket(self):
        lines = ["2026-10-01 09:07:30 ERROR boom\n"]
        path = _write_log(lines)
        try:
            result = run(path, "15m")
        finally:
            os.unlink(path)

        assert _ts("2026-10-01 09:00:00") in result.buckets
        assert result.buckets[_ts("2026-10-01 09:00:00")] == 1

    def test_multiple_errors_same_bucket(self):
        lines = [
            "2026-10-01 09:00:00 ERROR a\n",
            "2026-10-01 09:07:00 ERROR b\n",
            "2026-10-01 09:14:59 ERROR c\n",
        ]
        path = _write_log(lines)
        try:
            result = run(path, "15m")
        finally:
            os.unlink(path)

        assert result.buckets == {_ts("2026-10-01 09:00:00"): 3}

    def test_errors_across_two_15m_buckets(self):
        lines = [
            "2026-10-01 09:05:00 ERROR in first\n",
            "2026-10-01 09:15:00 ERROR in second\n",
            "2026-10-01 09:20:00 ERROR in second\n",
        ]
        path = _write_log(lines)
        try:
            result = run(path, "15m")
        finally:
            os.unlink(path)

        assert result.buckets[_ts("2026-10-01 09:00:00")] == 1
        assert result.buckets[_ts("2026-10-01 09:15:00")] == 2

    def test_buckets_are_chronologically_ordered(self):
        lines = [
            "2026-10-01 09:30:00 ERROR late\n",
            "2026-10-01 09:00:00 ERROR early\n",
            "2026-10-01 09:15:00 ERROR middle\n",
        ]
        path = _write_log(lines)
        try:
            result = run(path, "15m")
        finally:
            os.unlink(path)

        keys = list(result.buckets.keys())
        assert keys == sorted(keys)

    def test_1h_bucket(self):
        lines = [
            "2026-10-01 09:00:00 ERROR a\n",
            "2026-10-01 09:45:00 ERROR b\n",
            "2026-10-01 10:00:00 ERROR c\n",
        ]
        path = _write_log(lines)
        try:
            result = run(path, "1h")
        finally:
            os.unlink(path)

        assert result.buckets[_ts("2026-10-01 09:00:00")] == 2
        assert result.buckets[_ts("2026-10-01 10:00:00")] == 1

    def test_malformed_counted(self):
        lines = [
            "garbage line\n",
            "2026-10-01 09:00:00 ERROR real\n",
            "more garbage\n",
        ]
        path = _write_log(lines)
        try:
            result = run(path, "15m")
        finally:
            os.unlink(path)

        assert result.malformed == 2

    def test_empty_file(self):
        path = _write_log([])
        try:
            result = run(path, "15m")
        finally:
            os.unlink(path)

        assert result.buckets == {}
        assert result.malformed == 0

    def test_no_errors_empty_buckets(self):
        lines = [
            "2026-10-01 09:00:00 INFO  only info\n",
            "2026-10-01 09:01:00 WARN  only warn\n",
        ]
        path = _write_log(lines)
        try:
            result = run(path, "15m")
        finally:
            os.unlink(path)

        assert result.buckets == {}
        assert result.malformed == 0

    def test_all_malformed_no_crash(self):
        lines = [f"junk {i}\n" for i in range(50)]
        path = _write_log(lines)
        try:
            result = run(path, "15m")
        finally:
            os.unlink(path)

        assert result.buckets == {}
        assert result.malformed == 50

    def test_missing_file_raises(self):
        with pytest.raises((FileNotFoundError, OSError)):
            run("/tmp/logscope_no_such_file_timeline.log", "15m")

    def test_invalid_bucket_raises_before_opening_file(self):
        """parse_bucket is called before iter_log; bad spec raises immediately."""
        with pytest.raises(ValueError):
            run("/tmp/logscope_irrelevant.log", "bad_spec")

    def test_returns_timeline_result_type(self):
        path = _write_log(["2026-10-01 09:00:00 ERROR x\n"])
        try:
            result = run(path, "15m")
        finally:
            os.unlink(path)

        assert isinstance(result, TimelineResult)

    def test_bucket_label_preserved(self):
        path = _write_log(["2026-10-01 09:00:00 ERROR x\n"])
        try:
            result = run(path, "1h")
        finally:
            os.unlink(path)

        assert result.bucket_label == "1h"

    def test_sparse_buckets_not_filled(self):
        """Buckets with zero errors must not appear in the result."""
        lines = [
            "2026-10-01 09:00:00 ERROR first\n",
            # deliberate 30-minute gap — 09:15 bucket is empty
            "2026-10-01 09:30:00 ERROR third\n",
        ]
        path = _write_log(lines)
        try:
            result = run(path, "15m")
        finally:
            os.unlink(path)

        assert _ts("2026-10-01 09:15:00") not in result.buckets
        assert len(result.buckets) == 2

    def test_mixed_malformed_and_valid(self):
        lines = [
            "2026-10-01 09:00:00 ERROR counted\n",
            "not a log line\n",
            "2026-10-01 09:01:00 INFO  ignored\n",
            "also garbage\n",
        ]
        path = _write_log(lines)
        try:
            result = run(path, "15m")
        finally:
            os.unlink(path)

        assert sum(result.buckets.values()) == 1
        assert result.malformed == 2


# ---------------------------------------------------------------------------
# CLI-level tests
# ---------------------------------------------------------------------------

class TestTimelineCLI:

    def test_cli_prints_header(self, capsys):
        path = _write_log(["2026-10-01 09:00:00 ERROR x\n"])
        try:
            main(["timeline", path, "--bucket", "15m"])
        finally:
            os.unlink(path)

        out = capsys.readouterr().out
        assert "Timeline" in out or "timeline" in out.lower()

    def test_cli_shows_bucket_label(self, capsys):
        path = _write_log(["2026-10-01 09:00:00 ERROR x\n"])
        try:
            main(["timeline", path, "--bucket", "15m"])
        finally:
            os.unlink(path)

        out = capsys.readouterr().out
        assert "15m" in out

    def test_cli_shows_timestamp_and_count(self, capsys):
        path = _write_log([
            "2026-10-01 09:00:00 ERROR a\n",
            "2026-10-01 09:05:00 ERROR b\n",
        ])
        try:
            main(["timeline", path, "--bucket", "15m"])
        finally:
            os.unlink(path)

        out = capsys.readouterr().out
        assert "2026-10-01 09:00:00" in out
        assert "2" in out

    def test_cli_shows_bar(self, capsys):
        path = _write_log(["2026-10-01 09:00:00 ERROR x\n"])
        try:
            main(["timeline", path, "--bucket", "15m"])
        finally:
            os.unlink(path)

        out = capsys.readouterr().out
        assert "#" in out

    def test_cli_shows_malformed_count(self, capsys):
        path = _write_log([
            "garbage\n",
            "2026-10-01 09:00:00 ERROR x\n",
        ])
        try:
            main(["timeline", path, "--bucket", "15m"])
        finally:
            os.unlink(path)

        out = capsys.readouterr().out
        assert "Malformed" in out
        assert "1" in out

    def test_cli_default_bucket_is_15m(self, capsys):
        """--bucket defaults to 15m; omitting it must not crash."""
        path = _write_log(["2026-10-01 09:00:00 ERROR x\n"])
        try:
            main(["timeline", path])
        finally:
            os.unlink(path)

        out = capsys.readouterr().out
        assert "15m" in out

    def test_cli_1h_bucket(self, capsys):
        path = _write_log(["2026-10-01 09:30:00 ERROR x\n"])
        try:
            main(["timeline", path, "--bucket", "1h"])
        finally:
            os.unlink(path)

        out = capsys.readouterr().out
        assert "1h" in out
        assert "2026-10-01 09:00:00" in out

    def test_cli_empty_file_no_crash(self, capsys):
        path = _write_log([])
        try:
            main(["timeline", path, "--bucket", "15m"])
        finally:
            os.unlink(path)

        out = capsys.readouterr().out
        assert "no ERROR" in out or "none" in out.lower()

    def test_cli_all_malformed_no_crash(self, capsys):
        path = _write_log(["junk\n"] * 5)
        try:
            main(["timeline", path, "--bucket", "15m"])
        finally:
            os.unlink(path)

        out = capsys.readouterr().out
        assert "5" in out

    def test_cli_invalid_bucket_exits_nonzero(self, capsys):
        path = _write_log(["2026-10-01 09:00:00 ERROR x\n"])
        try:
            with pytest.raises(SystemExit) as exc_info:
                main(["timeline", path, "--bucket", "bad"])
        finally:
            os.unlink(path)

        assert exc_info.value.code != 0

    def test_cli_invalid_bucket_stderr_message(self, capsys):
        path = _write_log(["2026-10-01 09:00:00 ERROR x\n"])
        try:
            with pytest.raises(SystemExit):
                main(["timeline", path, "--bucket", "bad"])
        finally:
            os.unlink(path)

        err = capsys.readouterr().err
        assert "error" in err.lower()

    def test_cli_missing_file_exits_nonzero(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            main(["timeline", "/tmp/logscope_no_such_file_xyz.log", "--bucket", "15m"])

        assert exc_info.value.code != 0

    def test_cli_missing_file_stderr_message(self, capsys):
        with pytest.raises(SystemExit):
            main(["timeline", "/tmp/logscope_no_such_file_xyz.log", "--bucket", "15m"])

        err = capsys.readouterr().err
        assert "error" in err.lower()

    def test_cli_only_info_warn_shows_no_errors_placeholder(self, capsys):
        path = _write_log([
            "2026-10-01 09:00:00 INFO  a\n",
            "2026-10-01 09:00:01 WARN  b\n",
        ])
        try:
            main(["timeline", path, "--bucket", "15m"])
        finally:
            os.unlink(path)

        out = capsys.readouterr().out
        assert "no ERROR" in out or "none" in out.lower()
