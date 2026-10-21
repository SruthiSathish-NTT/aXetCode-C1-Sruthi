"""
tests.test_gen_log
~~~~~~~~~~~~~~~~~~
Unit tests for scripts/gen_log.py.

All tests generate only small files (a few KB at most) so the suite remains
fast.  The 100 MB benchmark is run separately as a manual step.
"""

from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Import the generator module portably regardless of the scripts/ directory
# not being a Python package.
# ---------------------------------------------------------------------------

_GEN_LOG_PATH = Path(__file__).parent.parent / "scripts" / "gen_log.py"

def _load_gen_log():
    spec = importlib.util.spec_from_file_location("gen_log", _GEN_LOG_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

gen_log = _load_gen_log()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _tmp_path() -> str:
    fd, path = tempfile.mkstemp(suffix=".log")
    os.close(fd)
    return path


# ---------------------------------------------------------------------------
# generate() — low-level API
# ---------------------------------------------------------------------------

class TestGenerateFunction:

    def test_file_is_created(self):
        path = _tmp_path()
        try:
            gen_log.generate(path, target_bytes=4096, malformed_rate=0.0, seed=42)
            assert os.path.isfile(path)
        finally:
            os.unlink(path)

    def test_actual_size_at_least_target(self):
        path = _tmp_path()
        target = 8192
        try:
            actual, _, _ = gen_log.generate(path, target_bytes=target, seed=1)
            # Allowed overshoot: one full line (~80 bytes).  Must reach target.
            assert actual >= target
            assert actual < target + 200
        finally:
            os.unlink(path)

    def test_returns_valid_and_malformed_counts(self):
        path = _tmp_path()
        try:
            actual, valid, mal = gen_log.generate(
                path, target_bytes=4096, malformed_rate=0.0, seed=0
            )
            assert valid > 0
            assert mal == 0
            assert actual > 0
        finally:
            os.unlink(path)

    def test_malformed_rate_produces_malformed_lines(self):
        path = _tmp_path()
        try:
            _, valid, mal = gen_log.generate(
                path, target_bytes=65536, malformed_rate=0.5, seed=7
            )
            assert mal > 0
            assert valid > 0
        finally:
            os.unlink(path)

    def test_zero_malformed_rate_produces_no_malformed(self):
        path = _tmp_path()
        try:
            _, _, mal = gen_log.generate(
                path, target_bytes=16384, malformed_rate=0.0, seed=3
            )
            assert mal == 0
        finally:
            os.unlink(path)

    def test_output_contains_info_lines(self):
        path = _tmp_path()
        try:
            gen_log.generate(path, target_bytes=32768, malformed_rate=0.0, seed=5)
            content = Path(path).read_text(encoding="utf-8")
            assert " INFO " in content
        finally:
            os.unlink(path)

    def test_output_contains_warn_lines(self):
        path = _tmp_path()
        try:
            gen_log.generate(path, target_bytes=32768, malformed_rate=0.0, seed=5)
            content = Path(path).read_text(encoding="utf-8")
            assert " WARN " in content
        finally:
            os.unlink(path)

    def test_output_contains_error_lines(self):
        path = _tmp_path()
        try:
            gen_log.generate(path, target_bytes=32768, malformed_rate=0.0, seed=5)
            content = Path(path).read_text(encoding="utf-8")
            assert " ERROR " in content
        finally:
            os.unlink(path)

    def test_repeated_error_messages(self):
        """ERROR pool is small enough that messages repeat; summary top-errors works."""
        path = _tmp_path()
        try:
            gen_log.generate(path, target_bytes=65536, malformed_rate=0.0, seed=99)
            content = Path(path).read_text(encoding="utf-8")
            error_lines = [l for l in content.splitlines() if " ERROR " in l]
            messages = [l.split(" ERROR ", 1)[1] for l in error_lines]
            assert len(messages) > len(set(messages)), "Expected repeated ERROR messages"
        finally:
            os.unlink(path)

    def test_valid_lines_parse_correctly(self):
        """All non-malformed lines must be accepted by the existing parser."""
        path = _tmp_path()
        try:
            gen_log.generate(path, target_bytes=16384, malformed_rate=0.0, seed=11)
            from logscope.parser import LogEntry, MalformedLine, iter_log
            for entry in iter_log(path):
                assert isinstance(entry, LogEntry), (
                    f"Unexpected MalformedLine: {entry.raw!r}"
                )
        finally:
            os.unlink(path)

    def test_malformed_lines_fail_parser(self):
        """Lines generated when malformed_rate > 0 must produce MalformedLine."""
        path = _tmp_path()
        try:
            gen_log.generate(path, target_bytes=32768, malformed_rate=1.0, seed=22)
            from logscope.parser import MalformedLine, iter_log
            for entry in iter_log(path):
                assert isinstance(entry, MalformedLine), (
                    f"Expected MalformedLine, got: {entry!r}"
                )
        finally:
            os.unlink(path)

    def test_timestamps_span_multiple_15m_buckets(self):
        """Generated timestamps must cover more than one 15-minute bucket."""
        from datetime import datetime
        from logscope.parser import LogEntry, iter_log
        path = _tmp_path()
        try:
            gen_log.generate(path, target_bytes=65536, malformed_rate=0.0, seed=33)
            timestamps = [
                e.timestamp for e in iter_log(path) if isinstance(e, LogEntry)
            ]
            first, last = min(timestamps), max(timestamps)
            assert (last - first).total_seconds() >= 900, (
                "Expected timestamps spanning at least one 15-minute bucket"
            )
        finally:
            os.unlink(path)

    def test_seed_reproducibility(self):
        """Same seed must produce identical files."""
        p1, p2 = _tmp_path(), _tmp_path()
        try:
            gen_log.generate(p1, target_bytes=8192, seed=77)
            gen_log.generate(p2, target_bytes=8192, seed=77)
            assert Path(p1).read_bytes() == Path(p2).read_bytes()
        finally:
            os.unlink(p1)
            os.unlink(p2)

    def test_different_seeds_produce_different_files(self):
        p1, p2 = _tmp_path(), _tmp_path()
        try:
            gen_log.generate(p1, target_bytes=8192, seed=1)
            gen_log.generate(p2, target_bytes=8192, seed=2)
            assert Path(p1).read_bytes() != Path(p2).read_bytes()
        finally:
            os.unlink(p1)
            os.unlink(p2)


# ---------------------------------------------------------------------------
# Integration: generated file is processed by logscope commands without error
# ---------------------------------------------------------------------------

class TestGeneratedFileIntegration:

    def test_summary_runs_on_generated_file(self, capsys):
        path = _tmp_path()
        try:
            gen_log.generate(path, target_bytes=32768, malformed_rate=0.02, seed=55)
            from logscope.cli import main
            main(["summary", path])
        finally:
            os.unlink(path)
        out = capsys.readouterr().out
        assert "Log Summary" in out
        assert "ERROR" in out

    def test_timeline_runs_on_generated_file(self, capsys):
        path = _tmp_path()
        try:
            gen_log.generate(path, target_bytes=65536, malformed_rate=0.02, seed=66)
            from logscope.cli import main
            main(["timeline", path, "--bucket", "15m"])
        finally:
            os.unlink(path)
        out = capsys.readouterr().out
        assert "Timeline" in out or "timeline" in out.lower()

    def test_summary_json_on_generated_file(self, capsys):
        import json
        path = _tmp_path()
        try:
            gen_log.generate(path, target_bytes=16384, malformed_rate=0.0, seed=88)
            from logscope.cli import main
            main(["summary", path, "--format", "json"])
        finally:
            os.unlink(path)
        data = json.loads(capsys.readouterr().out)
        assert data["command"] == "summary"
        assert data["counts"]["ERROR"] > 0

    def test_malformed_lines_counted_in_summary(self, capsys):
        import json
        path = _tmp_path()
        try:
            gen_log.generate(path, target_bytes=32768, malformed_rate=0.3, seed=44)
            from logscope.cli import main
            main(["summary", path, "--format", "json"])
        finally:
            os.unlink(path)
        data = json.loads(capsys.readouterr().out)
        assert data["malformed_lines"] > 0


# ---------------------------------------------------------------------------
# CLI argument validation (main())
# ---------------------------------------------------------------------------

class TestGenLogCLI:

    def test_invalid_size_zero_exits_nonzero(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            gen_log.main(["--size-mb", "0", "--output", "/tmp/logscope_gen_unused.log"])
        assert exc_info.value.code != 0

    def test_invalid_size_negative_exits_nonzero(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            gen_log.main(["--size-mb", "-5", "--output", "/tmp/logscope_gen_unused.log"])
        assert exc_info.value.code != 0

    def test_invalid_malformed_rate_one_exits_nonzero(self, capsys):
        path = _tmp_path()
        try:
            with pytest.raises(SystemExit) as exc_info:
                gen_log.main(["--size-mb", "0.01", "--output", path, "--malformed-rate", "1.0"])
        finally:
            if os.path.exists(path):
                os.unlink(path)
        assert exc_info.value.code != 0

    def test_invalid_malformed_rate_above_one_exits_nonzero(self, capsys):
        path = _tmp_path()
        try:
            with pytest.raises(SystemExit) as exc_info:
                gen_log.main(["--size-mb", "0.01", "--output", path, "--malformed-rate", "1.5"])
        finally:
            if os.path.exists(path):
                os.unlink(path)
        assert exc_info.value.code != 0

    def test_valid_small_run_creates_file(self, capsys):
        path = _tmp_path()
        try:
            gen_log.main(["--size-mb", "0.01", "--output", path, "--seed", "42"])
            assert os.path.isfile(path)
            assert os.path.getsize(path) > 0
        finally:
            os.unlink(path)

    def test_completion_summary_printed(self, capsys):
        path = _tmp_path()
        try:
            gen_log.main(["--size-mb", "0.01", "--output", path, "--seed", "1"])
        finally:
            os.unlink(path)
        out = capsys.readouterr().out
        assert "Actual size" in out
        assert "Valid lines" in out

    def test_default_output_filename_used_when_not_supplied(self, capsys):
        default_path = os.path.join(os.getcwd(), "synthetic.log")
        try:
            gen_log.main(["--size-mb", "0.005", "--seed", "9"])
            assert os.path.isfile(default_path)
        finally:
            if os.path.exists(default_path):
                os.unlink(default_path)
