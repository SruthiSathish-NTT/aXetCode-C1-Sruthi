"""
tests.test_output
~~~~~~~~~~~~~~~~~
Tests for --format json and --format md across summary, timeline, and grep.
Also tests that default text output still works when --format is omitted.
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from logscope.cli import main


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_log(lines: list[str]) -> str:
    fd, path = tempfile.mkstemp(suffix=".log", text=True)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.writelines(lines)
    return path


_SUMMARY_LINES = [
    "2026-10-01 09:00:01 INFO  Application started\n",
    "2026-10-01 09:00:05 INFO  Config loaded\n",
    "2026-10-01 09:01:00 WARN  Disk usage high\n",
    "2026-10-01 09:02:00 ERROR Database connection refused\n",
    "2026-10-01 09:02:10 ERROR Database connection refused\n",
    "2026-10-01 09:03:00 ERROR Timeout waiting for lock\n",
    "this is garbage\n",
    "2026-10-01 09:04:00 INFO  Scheduled task complete\n",
]

_TIMELINE_LINES = [
    "2026-10-01 09:05:00 ERROR first bucket\n",
    "2026-10-01 09:07:00 ERROR first bucket too\n",
    "2026-10-01 09:16:00 ERROR second bucket\n",
    "junk\n",
    "2026-10-01 09:00:00 INFO  ignored\n",
]

_GREP_LINES = [
    "2026-10-01 08:59:59 INFO  before\n",
    "2026-10-01 09:00:00 ERROR at boundary\n",
    "2026-10-01 09:05:00 ERROR after boundary\n",
    "garbage line\n",
    "2026-10-01 09:10:00 WARN  warn ignored\n",
]


# ---------------------------------------------------------------------------
# Summary — JSON
# ---------------------------------------------------------------------------

class TestSummaryJSON:

    def _run(self, capsys, extra_lines=None):
        lines = extra_lines if extra_lines is not None else _SUMMARY_LINES
        path = _write_log(lines)
        try:
            main(["summary", path, "--format", "json"])
        finally:
            os.unlink(path)
        return json.loads(capsys.readouterr().out)

    def test_valid_json(self, capsys):
        data = self._run(capsys)
        assert isinstance(data, dict)

    def test_command_field(self, capsys):
        data = self._run(capsys)
        assert data["command"] == "summary"

    def test_file_field(self, capsys):
        path = _write_log(_SUMMARY_LINES)
        try:
            main(["summary", path, "--format", "json"])
        finally:
            os.unlink(path)
        data = json.loads(capsys.readouterr().out)
        assert data["file"] == path

    def test_info_count(self, capsys):
        data = self._run(capsys)
        assert data["counts"]["INFO"] == 3

    def test_warn_count(self, capsys):
        data = self._run(capsys)
        assert data["counts"]["WARN"] == 1

    def test_error_count(self, capsys):
        data = self._run(capsys)
        assert data["counts"]["ERROR"] == 3

    def test_top_errors_present(self, capsys):
        data = self._run(capsys)
        assert isinstance(data["top_errors"], list)
        assert len(data["top_errors"]) > 0

    def test_top_errors_have_message_and_count(self, capsys):
        data = self._run(capsys)
        entry = data["top_errors"][0]
        assert "message" in entry
        assert "count" in entry

    def test_top_errors_ordered_descending(self, capsys):
        data = self._run(capsys)
        counts = [e["count"] for e in data["top_errors"]]
        assert counts == sorted(counts, reverse=True)

    def test_top_errors_most_frequent_first(self, capsys):
        data = self._run(capsys)
        assert data["top_errors"][0]["message"] == "Database connection refused"
        assert data["top_errors"][0]["count"] == 2

    def test_first_timestamp_iso(self, capsys):
        data = self._run(capsys)
        assert data["first_timestamp"] == "2026-10-01T09:00:01"

    def test_last_timestamp_iso(self, capsys):
        data = self._run(capsys)
        assert data["last_timestamp"] == "2026-10-01T09:04:00"

    def test_malformed_lines(self, capsys):
        data = self._run(capsys)
        assert data["malformed_lines"] == 1

    def test_null_timestamps_on_empty_file(self, capsys):
        data = self._run(capsys, extra_lines=[])
        assert data["first_timestamp"] is None
        assert data["last_timestamp"] is None

    def test_no_extra_text_on_stdout(self, capsys):
        path = _write_log(_SUMMARY_LINES)
        try:
            main(["summary", path, "--format", "json"])
        finally:
            os.unlink(path)
        out = capsys.readouterr().out
        # Must parse as JSON without stripping anything
        json.loads(out)


# ---------------------------------------------------------------------------
# Timeline — JSON
# ---------------------------------------------------------------------------

class TestTimelineJSON:

    def _run(self, capsys, bucket="15m", lines=None):
        log_lines = lines if lines is not None else _TIMELINE_LINES
        path = _write_log(log_lines)
        try:
            main(["timeline", path, "--bucket", bucket, "--format", "json"])
        finally:
            os.unlink(path)
        return json.loads(capsys.readouterr().out)

    def test_valid_json(self, capsys):
        data = self._run(capsys)
        assert isinstance(data, dict)

    def test_command_field(self, capsys):
        data = self._run(capsys)
        assert data["command"] == "timeline"

    def test_bucket_field(self, capsys):
        data = self._run(capsys)
        assert data["bucket"] == "15m"

    def test_bucket_field_1h(self, capsys):
        data = self._run(capsys, bucket="1h")
        assert data["bucket"] == "1h"

    def test_timeline_is_list(self, capsys):
        data = self._run(capsys)
        assert isinstance(data["timeline"], list)

    def test_timeline_entries_have_bucket_start(self, capsys):
        data = self._run(capsys)
        for entry in data["timeline"]:
            assert "bucket_start" in entry

    def test_timeline_entries_have_error_count(self, capsys):
        data = self._run(capsys)
        for entry in data["timeline"]:
            assert "error_count" in entry

    def test_chronological_order(self, capsys):
        data = self._run(capsys)
        starts = [e["bucket_start"] for e in data["timeline"]]
        assert starts == sorted(starts)

    def test_error_counts_correct(self, capsys):
        data = self._run(capsys)
        # first 15m bucket (09:00) has 2 errors; second (09:15) has 1
        total = sum(e["error_count"] for e in data["timeline"])
        assert total == 3

    def test_malformed_lines(self, capsys):
        data = self._run(capsys)
        assert data["malformed_lines"] == 1

    def test_empty_timeline_on_no_errors(self, capsys):
        lines = ["2026-10-01 09:00:00 INFO  only info\n"]
        data = self._run(capsys, lines=lines)
        assert data["timeline"] == []

    def test_bucket_start_is_iso_string(self, capsys):
        data = self._run(capsys)
        # Should be parseable as ISO datetime
        for entry in data["timeline"]:
            datetime.fromisoformat(entry["bucket_start"])


# ---------------------------------------------------------------------------
# Grep — JSON
# ---------------------------------------------------------------------------

class TestGrepJSON:

    def _run(self, capsys, level="ERROR", since=None, lines=None):
        log_lines = lines if lines is not None else _GREP_LINES
        path = _write_log(log_lines)
        args = ["grep", path, "--level", level, "--format", "json"]
        if since:
            args += ["--since", since]
        try:
            main(args)
        finally:
            os.unlink(path)
        return json.loads(capsys.readouterr().out)

    def test_valid_json(self, capsys):
        data = self._run(capsys)
        assert isinstance(data, dict)

    def test_command_field(self, capsys):
        data = self._run(capsys)
        assert data["command"] == "grep"

    def test_level_field(self, capsys):
        data = self._run(capsys)
        assert data["level"] == "ERROR"

    def test_since_null_when_not_supplied(self, capsys):
        data = self._run(capsys)
        assert data["since"] is None

    def test_since_iso_when_supplied(self, capsys):
        data = self._run(capsys, since="2026-10-01 09:00")
        assert data["since"] == "2026-10-01T09:00:00"

    def test_match_count(self, capsys):
        data = self._run(capsys)
        assert data["match_count"] == 2

    def test_matches_is_list(self, capsys):
        data = self._run(capsys)
        assert isinstance(data["matches"], list)

    def test_matches_content(self, capsys):
        data = self._run(capsys)
        assert any("at boundary" in m for m in data["matches"])
        assert any("after boundary" in m for m in data["matches"])

    def test_matches_order_preserved(self, capsys):
        data = self._run(capsys)
        assert "at boundary" in data["matches"][0]
        assert "after boundary" in data["matches"][1]

    def test_since_filters_matches(self, capsys):
        data = self._run(capsys, since="2026-10-01 09:05")
        assert data["match_count"] == 1
        assert "after boundary" in data["matches"][0]

    def test_malformed_lines(self, capsys):
        data = self._run(capsys)
        assert data["malformed_lines"] == 1

    def test_zero_matches(self, capsys):
        lines = ["2026-10-01 09:00:00 INFO  only info\n"]
        data = self._run(capsys, lines=lines)
        assert data["match_count"] == 0
        assert data["matches"] == []

    def test_raw_lines_no_trailing_newline(self, capsys):
        data = self._run(capsys)
        for m in data["matches"]:
            assert not m.endswith("\n")


# ---------------------------------------------------------------------------
# Summary — Markdown
# ---------------------------------------------------------------------------

class TestSummaryMarkdown:

    def _run_md(self, capsys, lines=None):
        log_lines = lines if lines is not None else _SUMMARY_LINES
        path = _write_log(log_lines)
        try:
            main(["summary", path, "--format", "md"])
        finally:
            os.unlink(path)
        out = capsys.readouterr().out
        return out

    def _get_report_path(self, capsys, lines=None):
        out = self._run_md(capsys, lines=lines)
        # CLI prints "Report written: <path>"
        assert "Report written:" in out
        return out.strip().split("Report written:")[-1].strip()

    def test_stdout_reports_path(self, capsys):
        out = self._run_md(capsys)
        assert "Report written:" in out

    def test_report_file_created(self, capsys):
        rpt = self._get_report_path(capsys)
        try:
            assert os.path.isfile(rpt)
        finally:
            if os.path.exists(rpt):
                os.unlink(rpt)

    def test_report_filename_contains_summary(self, capsys):
        rpt = self._get_report_path(capsys)
        try:
            assert "summary" in os.path.basename(rpt)
        finally:
            if os.path.exists(rpt):
                os.unlink(rpt)

    def test_report_filename_ends_with_md(self, capsys):
        rpt = self._get_report_path(capsys)
        try:
            assert rpt.endswith(".md")
        finally:
            if os.path.exists(rpt):
                os.unlink(rpt)

    def test_report_heading(self, capsys):
        rpt = self._get_report_path(capsys)
        try:
            content = Path(rpt).read_text(encoding="utf-8")
            assert "# Logscope Summary Report" in content
        finally:
            if os.path.exists(rpt):
                os.unlink(rpt)

    def test_report_contains_info_count(self, capsys):
        rpt = self._get_report_path(capsys)
        try:
            content = Path(rpt).read_text(encoding="utf-8")
            assert "INFO" in content
            assert "3" in content
        finally:
            if os.path.exists(rpt):
                os.unlink(rpt)

    def test_report_contains_top_error(self, capsys):
        rpt = self._get_report_path(capsys)
        try:
            content = Path(rpt).read_text(encoding="utf-8")
            assert "Database connection refused" in content
        finally:
            if os.path.exists(rpt):
                os.unlink(rpt)

    def test_report_contains_malformed_count(self, capsys):
        rpt = self._get_report_path(capsys)
        try:
            content = Path(rpt).read_text(encoding="utf-8")
            assert "Malformed" in content or "malformed" in content
            assert "1" in content
        finally:
            if os.path.exists(rpt):
                os.unlink(rpt)

    def test_report_contains_timestamps(self, capsys):
        rpt = self._get_report_path(capsys)
        try:
            content = Path(rpt).read_text(encoding="utf-8")
            assert "2026-10-01" in content
        finally:
            if os.path.exists(rpt):
                os.unlink(rpt)


# ---------------------------------------------------------------------------
# Timeline — Markdown
# ---------------------------------------------------------------------------

class TestTimelineMarkdown:

    def _get_report(self, capsys, bucket="15m", lines=None):
        log_lines = lines if lines is not None else _TIMELINE_LINES
        path = _write_log(log_lines)
        try:
            main(["timeline", path, "--bucket", bucket, "--format", "md"])
        finally:
            os.unlink(path)
        out = capsys.readouterr().out
        assert "Report written:" in out
        rpt = out.strip().split("Report written:")[-1].strip()
        return rpt

    def test_report_file_created(self, capsys):
        rpt = self._get_report(capsys)
        try:
            assert os.path.isfile(rpt)
        finally:
            if os.path.exists(rpt):
                os.unlink(rpt)

    def test_report_filename_contains_timeline(self, capsys):
        rpt = self._get_report(capsys)
        try:
            assert "timeline" in os.path.basename(rpt)
        finally:
            if os.path.exists(rpt):
                os.unlink(rpt)

    def test_report_heading(self, capsys):
        rpt = self._get_report(capsys)
        try:
            content = Path(rpt).read_text(encoding="utf-8")
            assert "# Logscope Timeline Report" in content
        finally:
            if os.path.exists(rpt):
                os.unlink(rpt)

    def test_report_contains_bucket_value(self, capsys):
        rpt = self._get_report(capsys)
        try:
            content = Path(rpt).read_text(encoding="utf-8")
            assert "15m" in content
        finally:
            if os.path.exists(rpt):
                os.unlink(rpt)

    def test_report_contains_error_counts(self, capsys):
        rpt = self._get_report(capsys)
        try:
            content = Path(rpt).read_text(encoding="utf-8")
            # The two buckets have counts 2 and 1
            assert "2" in content
            assert "1" in content
        finally:
            if os.path.exists(rpt):
                os.unlink(rpt)

    def test_report_contains_malformed_count(self, capsys):
        rpt = self._get_report(capsys)
        try:
            content = Path(rpt).read_text(encoding="utf-8")
            assert "1" in content
            assert "Malformed" in content or "malformed" in content
        finally:
            if os.path.exists(rpt):
                os.unlink(rpt)

    def test_no_errors_shows_placeholder(self, capsys):
        lines = ["2026-10-01 09:00:00 INFO  only info\n"]
        rpt = self._get_report(capsys, lines=lines)
        try:
            content = Path(rpt).read_text(encoding="utf-8")
            assert "none" in content.lower() or "no ERROR" in content
        finally:
            if os.path.exists(rpt):
                os.unlink(rpt)


# ---------------------------------------------------------------------------
# Grep — Markdown
# ---------------------------------------------------------------------------

class TestGrepMarkdown:

    def _get_report(self, capsys, level="ERROR", since=None, lines=None):
        log_lines = lines if lines is not None else _GREP_LINES
        path = _write_log(log_lines)
        args = ["grep", path, "--level", level, "--format", "md"]
        if since:
            args += ["--since", since]
        try:
            main(args)
        finally:
            os.unlink(path)
        out = capsys.readouterr().out
        assert "Report written:" in out
        return out.strip().split("Report written:")[-1].strip()

    def test_report_file_created(self, capsys):
        rpt = self._get_report(capsys)
        try:
            assert os.path.isfile(rpt)
        finally:
            if os.path.exists(rpt):
                os.unlink(rpt)

    def test_report_filename_contains_grep(self, capsys):
        rpt = self._get_report(capsys)
        try:
            assert "grep" in os.path.basename(rpt)
        finally:
            if os.path.exists(rpt):
                os.unlink(rpt)

    def test_report_heading(self, capsys):
        rpt = self._get_report(capsys)
        try:
            content = Path(rpt).read_text(encoding="utf-8")
            assert "# Logscope Grep Report" in content
        finally:
            if os.path.exists(rpt):
                os.unlink(rpt)

    def test_report_contains_level_filter(self, capsys):
        rpt = self._get_report(capsys)
        try:
            content = Path(rpt).read_text(encoding="utf-8")
            assert "ERROR" in content
        finally:
            if os.path.exists(rpt):
                os.unlink(rpt)

    def test_report_contains_since_when_supplied(self, capsys):
        rpt = self._get_report(capsys, since="2026-10-01 09:00")
        try:
            content = Path(rpt).read_text(encoding="utf-8")
            assert "2026-10-01 09:00" in content
        finally:
            if os.path.exists(rpt):
                os.unlink(rpt)

    def test_report_contains_matching_lines(self, capsys):
        rpt = self._get_report(capsys)
        try:
            content = Path(rpt).read_text(encoding="utf-8")
            assert "at boundary" in content
            assert "after boundary" in content
        finally:
            if os.path.exists(rpt):
                os.unlink(rpt)

    def test_report_contains_match_count(self, capsys):
        rpt = self._get_report(capsys)
        try:
            content = Path(rpt).read_text(encoding="utf-8")
            assert "2" in content
        finally:
            if os.path.exists(rpt):
                os.unlink(rpt)

    def test_report_contains_malformed_count(self, capsys):
        rpt = self._get_report(capsys)
        try:
            content = Path(rpt).read_text(encoding="utf-8")
            assert "Malformed" in content or "malformed" in content
            assert "1" in content
        finally:
            if os.path.exists(rpt):
                os.unlink(rpt)

    def test_no_matches_shows_placeholder(self, capsys):
        lines = ["2026-10-01 09:00:00 INFO  only info\n"]
        rpt = self._get_report(capsys, lines=lines)
        try:
            content = Path(rpt).read_text(encoding="utf-8")
            assert "no matching" in content.lower() or "none" in content.lower()
        finally:
            if os.path.exists(rpt):
                os.unlink(rpt)

    def test_lines_in_fenced_block(self, capsys):
        rpt = self._get_report(capsys)
        try:
            content = Path(rpt).read_text(encoding="utf-8")
            assert "```" in content
        finally:
            if os.path.exists(rpt):
                os.unlink(rpt)


# ---------------------------------------------------------------------------
# Default text output still works (no --format)
# ---------------------------------------------------------------------------

class TestDefaultOutputPreserved:

    def test_summary_text_default(self, capsys):
        path = _write_log(_SUMMARY_LINES)
        try:
            main(["summary", path])
        finally:
            os.unlink(path)
        out = capsys.readouterr().out
        assert "Log Summary" in out
        assert "INFO" in out

    def test_timeline_text_default(self, capsys):
        path = _write_log(_TIMELINE_LINES)
        try:
            main(["timeline", path, "--bucket", "15m"])
        finally:
            os.unlink(path)
        out = capsys.readouterr().out
        assert "Timeline" in out or "timeline" in out.lower()
        assert "#" in out

    def test_grep_text_default(self, capsys):
        path = _write_log(_GREP_LINES)
        try:
            main(["grep", path, "--level", "ERROR"])
        finally:
            os.unlink(path)
        out = capsys.readouterr().out
        assert "Grep" in out or "grep" in out.lower()
        assert "at boundary" in out


# ---------------------------------------------------------------------------
# Invalid --format handling
# (argparse rejects unknown choices before our code runs)
# ---------------------------------------------------------------------------

class TestInvalidFormat:

    def test_invalid_format_summary(self, capsys):
        path = _write_log(_SUMMARY_LINES)
        try:
            with pytest.raises(SystemExit) as exc_info:
                main(["summary", path, "--format", "xml"])
        finally:
            os.unlink(path)
        assert exc_info.value.code != 0

    def test_invalid_format_timeline(self, capsys):
        path = _write_log(_TIMELINE_LINES)
        try:
            with pytest.raises(SystemExit) as exc_info:
                main(["timeline", path, "--bucket", "15m", "--format", "csv"])
        finally:
            os.unlink(path)
        assert exc_info.value.code != 0

    def test_invalid_format_grep(self, capsys):
        path = _write_log(_GREP_LINES)
        try:
            with pytest.raises(SystemExit) as exc_info:
                main(["grep", path, "--level", "ERROR", "--format", "html"])
        finally:
            os.unlink(path)
        assert exc_info.value.code != 0
