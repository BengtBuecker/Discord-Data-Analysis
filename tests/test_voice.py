"""Tests for analyzers/voice.py — voice call analysis."""

import json
import unittest
from datetime import datetime
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from analyzers.voice import (
    _parse_ts,
    _stream_rtc_events_via_grep,
    _stream_leave_voice_events,
    detect_voice_sessions,
    aggregate_channel_durations,
    voice_summary,
    VoiceSession,
)

FIXTURES = Path(__file__).parent / "fixtures"


class TestParseTs(unittest.TestCase):
    def test_utc_format(self):
        dt = _parse_ts("2025-01-15 10:00:00.000 UTC")
        self.assertIsInstance(dt, datetime)
        self.assertEqual(dt.year, 2025)
        self.assertEqual(dt.month, 1)

    def test_iso_format(self):
        dt = _parse_ts("2025-01-15T10:00:00.000Z")
        self.assertIsInstance(dt, datetime)

    def test_iso_no_ms(self):
        dt = _parse_ts("2025-01-15T10:00:00Z")
        self.assertIsInstance(dt, datetime)

    def test_plain_format(self):
        dt = _parse_ts("2025-01-15 10:00:00")
        self.assertIsInstance(dt, datetime)

    def test_quoted_string(self):
        dt = _parse_ts('"2025-01-15 10:00:00.000 UTC"')
        self.assertIsInstance(dt, datetime)

    def test_none_input(self):
        self.assertIsNone(_parse_ts(None))

    def test_empty_string(self):
        self.assertIsNone(_parse_ts(""))

    def test_garbage_string(self):
        self.assertIsNone(_parse_ts("not-a-date"))

    def test_zero(self):
        self.assertIsNone(_parse_ts(0))


class TestStreamRtcEventsViaGrep(unittest.TestCase):
    def test_yields_rtc_events(self):
        events = list(_stream_rtc_events_via_grep(FIXTURES / "Aktivität"))
        rtc_states = [e[2] for e in events]
        self.assertIn("RTC_CONNECTED", rtc_states)
        self.assertIn("RTC_DISCONNECTED", rtc_states)

    def test_yields_correct_structure(self):
        events = list(_stream_rtc_events_via_grep(FIXTURES / "Aktivität"))
        for ev in events:
            sid, uptime, rtc, init_ts = ev
            self.assertIsInstance(sid, str)
            self.assertIsInstance(uptime, int)
            self.assertIn(rtc, ("RTC_CONNECTED", "RTC_DISCONNECTED"))
            self.assertIsInstance(init_ts, str)

    def test_skips_non_rtc_events(self):
        events = list(_stream_rtc_events_via_grep(FIXTURES / "Aktivität"))
        rtc_values = [e[2] for e in events]
        self.assertNotIn("SOMETHING_ELSE", rtc_values)

    def test_empty_dir(self):
        events = list(_stream_rtc_events_via_grep(Path("/nonexistent_dir_xyz")))
        self.assertEqual(len(events), 0)


class TestStreamLeaveVoiceEvents(unittest.TestCase):
    def test_yields_leave_events(self):
        events = list(_stream_leave_voice_events(FIXTURES / "Aktivität"))
        self.assertGreaterEqual(len(events), 2)

    def test_yields_correct_structure(self):
        events = list(_stream_leave_voice_events(FIXTURES / "Aktivität"))
        for ev in events:
            cid, gid, dur, ts = ev
            self.assertIsInstance(cid, str)
            self.assertIsInstance(gid, str)
            self.assertIsInstance(dur, int)
            self.assertGreater(dur, 0)
            self.assertIsInstance(ts, str)

    def test_includes_dm_and_server_channels(self):
        events = list(_stream_leave_voice_events(FIXTURES / "Aktivität"))
        cids = [e[0] for e in events]
        self.assertIn("1234", cids)   # DM channel
        self.assertIn("5678", cids)   # server channel

    def test_skips_reporting_events(self):
        """Only leave_voice_channel events, not guild_viewed etc."""
        events = list(_stream_leave_voice_events(FIXTURES / "Aktivität"))
        for ev in events:
            self.assertNotEqual(ev[0], "")  # must have channel_id

    def test_empty_dir(self):
        events = list(_stream_leave_voice_events(Path("/nonexistent_dir_xyz")))
        self.assertEqual(len(events), 0)


class TestDetectVoiceSessions(unittest.TestCase):
    def test_detects_sessions(self):
        sessions = detect_voice_sessions(FIXTURES / "Aktivität",
                                          min_duration_seconds=0)
        self.assertGreaterEqual(len(sessions), 1)
        for s in sessions:
            self.assertIsInstance(s, VoiceSession)
            self.assertIsInstance(s.start, datetime)
            self.assertGreater(s.duration_seconds, 0)

    def test_min_duration_filter(self):
        sessions = detect_voice_sessions(FIXTURES / "Aktivität",
                                          min_duration_seconds=99999)
        self.assertEqual(len(sessions), 0)

    def test_sessions_sorted_by_start(self):
        sessions = detect_voice_sessions(FIXTURES / "Aktivität",
                                          min_duration_seconds=0)
        starts = [s.start for s in sessions]
        self.assertEqual(starts, sorted(starts))


class TestAggregateChannelDurations(unittest.TestCase):
    def test_aggregates_by_channel(self):
        result = aggregate_channel_durations(FIXTURES / "Aktivität", FIXTURES)
        self.assertGreaterEqual(len(result), 2)

    def test_dm_channels_have_usernames(self):
        result = aggregate_channel_durations(FIXTURES / "Aktivität", FIXTURES)
        dm_names = [k for k, v in result.items() if v["name_type"] == "dm"]
        self.assertIn("alice", dm_names)
        self.assertIn("bob", dm_names)

    def test_server_entries_have_server_name(self):
        result = aggregate_channel_durations(FIXTURES / "Aktivität", FIXTURES)
        sv = [v for v in result.values() if v["name_type"] == "server"]
        self.assertGreaterEqual(len(sv), 1)
        self.assertIn("MyServer", sv[0]["name"])

    def test_unknown_channels_use_channel_id(self):
        result = aggregate_channel_durations(FIXTURES / "Aktivität", FIXTURES)
        unknown = [v for v in result.values() if v["name_type"] == "unknown"]
        self.assertGreaterEqual(len(unknown), 1)
        self.assertTrue(unknown[0]["name"].startswith("#"))

    def test_duration_fields_present(self):
        result = aggregate_channel_durations(FIXTURES / "Aktivität", FIXTURES)
        for v in result.values():
            self.assertIn("duration_seconds", v)
            self.assertIn("duration_minutes", v)
            self.assertIn("duration_hours", v)
            self.assertIn("call_count", v)
            self.assertIn("name_type", v)
            self.assertIn("channel_id", v)
            self.assertGreaterEqual(v["call_count"], 1)

    def test_sorted_by_duration_desc(self):
        """voice_summary returns channel_durations sorted by duration."""
        summary = voice_summary(FIXTURES)
        cd = summary.get("channel_durations", [])
        if len(cd) >= 2:
            for i in range(len(cd) - 1):
                self.assertGreaterEqual(cd[i]["duration_seconds"],
                                        cd[i + 1]["duration_seconds"])


class TestVoiceSummary(unittest.TestCase):
    def test_returns_expected_keys(self):
        s = voice_summary(FIXTURES)
        for key in ("total_sessions", "total_duration_seconds",
                     "total_duration_formatted", "average_duration_seconds",
                     "longest_session_seconds", "sessions_by_day",
                     "sessions", "channel_durations"):
            self.assertIn(key, s)

    def test_missing_activity_dir(self):
        s = voice_summary(Path("/nonexistent_dir_xyz"))
        self.assertEqual(s["total_sessions"], 0)
        self.assertEqual(s["total_duration_seconds"], 0)
        self.assertIn("error", s)

    def test_total_duration_formatted(self):
        s = voice_summary(FIXTURES)
        self.assertRegex(s["total_duration_formatted"], r"^\d+h \d+m")


if __name__ == "__main__":
    unittest.main()
