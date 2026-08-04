"""Tests for analyzers/voice.py — all voice analysis functions."""

from datetime import datetime
from unittest.mock import patch

from analyzers.voice import (
    VoiceSession,
    _parse_ts,
    _iter_matching_lines,
    _grep_json_lines,
    _stream_rtc_events_via_grep,
    _stream_leave_voice_events,
    _append_session,
    detect_voice_sessions,
    aggregate_channel_durations,
    voice_summary,
)


class TestParseTs:
    def test_parses_standard_format(self):
        dt = _parse_ts("2024-06-01 12:00:00")
        assert dt == datetime(2024, 6, 1, 12, 0, 0)

    def test_parses_with_microseconds(self):
        dt = _parse_ts("2024-06-01 12:00:00.123456")
        assert dt.microsecond == 123456

    def test_parses_iso_format(self):
        dt = _parse_ts("2024-06-01T12:00:00Z")
        assert dt == datetime(2024, 6, 1, 12, 0, 0)

    def test_parses_iso_with_ms(self):
        dt = _parse_ts("2024-06-01T12:00:00.500Z")
        assert dt.microsecond == 500000

    def test_parses_with_utc_suffix(self):
        dt = _parse_ts("2024-06-01 12:00:00 UTC")
        assert dt == datetime(2024, 6, 1, 12, 0, 0)

    def test_strips_quotes(self):
        dt = _parse_ts('"2024-06-01 12:00:00"')
        assert dt == datetime(2024, 6, 1, 12, 0, 0)

    def test_returns_none_for_empty(self):
        assert _parse_ts("") is None
        assert _parse_ts(None) is None

    def test_returns_none_for_invalid(self):
        assert _parse_ts("not a date at all") is None

    def test_returns_none_for_zero(self):
        assert _parse_ts(0) is None

    def test_returns_none_for_numeric_string(self):
        assert _parse_ts("1000") is None


class TestIterMatchingLines:
    def test_yields_matching_lines(self, tmp_path):
        f = tmp_path / "events.json"
        f.write_text('{"type":"RTC_CONNECTED","data":"a"}\n{"type":"OTHER","data":"b"}\n{"type":"RTC_DISCONNECTED","data":"c"}\n')
        lines = list(_iter_matching_lines(f, "RTC_CONNECTED|RTC_DISCONNECTED"))
        assert len(lines) == 2

    def test_no_matches_returns_empty(self, tmp_path):
        f = tmp_path / "events.json"
        f.write_text('{"type":"OTHER"}\n')
        assert list(_iter_matching_lines(f, "RTC_CONNECTED")) == []

    def test_empty_file(self, tmp_path):
        f = tmp_path / "events.json"
        f.write_text("")
        assert list(_iter_matching_lines(f, "RTC_CONNECTED")) == []


class TestGrepJsonLines:
    def test_parses_json_objects(self, mock_export_dir):
        files = list(mock_export_dir.glob("Aktivität/analytics/*.json"))
        results = list(_grep_json_lines(files, "RTC_CONNECTED|RTC_DISCONNECTED"))
        assert len(results) == 5
        assert all(isinstance(r, dict) for r in results)

    def test_falls_back_on_missing_grep(self, mock_export_dir):
        files = list(mock_export_dir.glob("Aktivität/analytics/*.json"))
        with patch("subprocess.run", side_effect=FileNotFoundError):
            results = list(_grep_json_lines(files, "RTC_CONNECTED"))
            assert len(results) == 3

    def test_skips_invalid_json(self, tmp_path):
        f = tmp_path / "bad.json"
        f.write_text('{"valid":1}\nnot json\n{"also":2}\n')
        results = list(_grep_json_lines([f], "valid|also"))
        assert len(results) == 2


class TestStreamRtcEvents:
    def test_yields_correct_tuples(self, mock_export_dir):
        events = list(_stream_rtc_events_via_grep(mock_export_dir / "Aktivität" / "analytics"))
        assert len(events) == 5
        assert all(len(e) == 4 for e in events)

    def test_sessions_include_both_states(self, mock_export_dir):
        events = list(_stream_rtc_events_via_grep(mock_export_dir / "Aktivität" / "analytics"))
        states = {e[2] for e in events}
        assert "RTC_CONNECTED" in states
        assert "RTC_DISCONNECTED" in states


class TestStreamLeaveVoiceEvents:
    def test_yields_events(self, mock_export_dir):
        events = list(_stream_leave_voice_events(mock_export_dir / "Aktivität"))
        assert len(events) >= 1

    def test_yields_channel_id_and_duration(self, mock_export_dir):
        events = list(_stream_leave_voice_events(mock_export_dir / "Aktivität"))
        for cid, gid, dur, ts in events:
            assert cid
            assert dur > 0


class TestAppendSession:
    def test_appends_long_enough_session(self):
        sessions = []
        init = datetime(2024, 6, 1, 12, 0, 0)
        _append_session(sessions, init, 0, 3600, 30)
        assert len(sessions) == 1
        assert sessions[0].duration_seconds == 3600

    def test_skips_short_session(self):
        sessions = []
        init = datetime(2024, 6, 1, 12, 0, 0)
        _append_session(sessions, init, 0, 10, 30)
        assert len(sessions) == 0

    def test_duration_at_threshold(self):
        sessions = []
        init = datetime(2024, 6, 1, 12, 0, 0)
        _append_session(sessions, init, 0, 30, 30)
        assert len(sessions) == 1


class TestDetectVoiceSessions:
    def test_detects_sessions(self, mock_export_dir):
        sessions = detect_voice_sessions(mock_export_dir / "Aktivität")
        assert len(sessions) >= 1

    def test_sessions_have_start_and_duration(self, mock_export_dir):
        sessions = detect_voice_sessions(mock_export_dir / "Aktivität")
        for s in sessions:
            assert isinstance(s.start, datetime)
            assert s.duration_seconds > 0

    def test_min_duration_filter(self, mock_export_dir):
        sessions = detect_voice_sessions(mock_export_dir / "Aktivität", min_duration_seconds=10000)
        assert len(sessions) == 0

    def test_progress_callback_receives(self, mock_export_dir):
        calls = []
        detect_voice_sessions(mock_export_dir / "Aktivität", progress_callback=lambda c, t: calls.append((c, t)))
        assert len(calls) > 0


class TestAggregateChannelDurations:
    def test_aggregates_by_channel(self, mock_export_dir):
        result = aggregate_channel_durations(mock_export_dir / "Aktivität", mock_export_dir)
        assert len(result) >= 1

    def test_includes_duration_and_count(self, mock_export_dir):
        result = aggregate_channel_durations(mock_export_dir / "Aktivität", mock_export_dir)
        for info in result.values():
            assert "duration_seconds" in info
            assert "call_count" in info
            assert "name_type" in info

    def test_resolves_dm_channel_names(self, mock_export_dir):
        result = aggregate_channel_durations(mock_export_dir / "Aktivität", mock_export_dir)
        dm = {k: v for k, v in result.items() if v["name_type"] == "dm"}
        assert len(dm) >= 1
        assert "Alice" in dm


class TestVoiceSummary:
    def test_returns_full_dict(self, mock_export_dir):
        s = voice_summary(mock_export_dir)
        assert "total_sessions" in s
        assert "total_duration_seconds" in s
        assert "total_duration_formatted" in s
        assert "average_duration_seconds" in s
        assert "longest_session_seconds" in s
        assert "sessions_by_day" in s
        assert "sessions" in s
        assert "channel_durations" in s

    def test_no_sessions_returns_empty(self, mock_export_dir):
        (mock_export_dir / "Aktivität" / "analytics" / "events-0.json").unlink()
        (mock_export_dir / "Aktivität" / "analytics" / "events-0.json").write_text("")
        with patch("analyzers.voice.detect_voice_sessions", return_value=[]):
            s = voice_summary(mock_export_dir)
            assert s["total_sessions"] == 0
            assert s["total_duration_seconds"] == 0
            assert s["sessions_by_day"] == {}
            assert s["sessions"] == []

    def test_missing_activity_dir(self, tmp_path):
        s = voice_summary(tmp_path)
        assert s["total_sessions"] == 0
        assert "error" in s
