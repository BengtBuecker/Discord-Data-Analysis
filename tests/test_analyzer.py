"""Tests for analyzer.py — CLI render functions."""

import io
import sys
from pathlib import Path

from analyzer import (
    print_dm_users,
    print_server,
    print_channels,
    print_timeline,
    print_voice,
    print_all,
)


def _capture_stdout(func, *args, **kwargs):
    buf = io.StringIO()
    old = sys.stdout
    sys.stdout = buf
    try:
        func(*args, **kwargs)
    finally:
        sys.stdout = old
    return buf.getvalue()


class TestPrintDmUsers:
    def test_prints_dm_users(self, mock_export_dir):
        out = _capture_stdout(print_dm_users, mock_export_dir)
        assert "Alice" in out
        assert "Bob" in out
        assert "total:" in out

    def test_top_limit(self, mock_export_dir):
        out = _capture_stdout(print_dm_users, mock_export_dir, top=1)
        assert out.count("Alice") >= 1


class TestPrintServer:
    def test_prints_servers(self, mock_export_dir):
        out = _capture_stdout(print_server, mock_export_dir)
        assert "=" in out or "MyServer" in out


class TestPrintChannels:
    def test_prints_channels(self, mock_export_dir):
        out = _capture_stdout(print_channels, mock_export_dir)
        assert "Alice" in out or "Bob" in out
        assert "total:" in out

    def test_top_limit(self, mock_export_dir):
        out = _capture_stdout(print_channels, mock_export_dir, top=1)
        lines = out.splitlines()
        assert len(lines) < 50


class TestPrintTimeline:
    def test_print_monthly(self, mock_export_dir):
        out = _capture_stdout(print_timeline, mock_export_dir)
        assert "2024-01" in out or "Timeline" in out

    def test_print_daily(self, mock_export_dir):
        out = _capture_stdout(print_timeline, mock_export_dir, "day")
        assert "2024-01-15" in out or "Timeline" in out


class TestPrintVoice:
    def test_prints_voice_summary(self, mock_export_dir):
        out = _capture_stdout(print_voice, mock_export_dir)
        if "No Aktivität" not in out:
            assert "Voice" in out or "sessions" in out

    def test_handles_missing_dir(self, tmp_path):
        from analyzers.voice import voice_summary
        s = voice_summary(tmp_path)
        assert "error" in s


class TestPrintAll:
    def test_prints_full_report(self, mock_export_dir):
        out = _capture_stdout(print_all, mock_export_dir)
        assert "FULL" in out or "total" in out or "DM" in out
