"""Tests for analyzers/messages.py — all message analysis functions."""

from datetime import datetime

import pytest

from analyzers.messages import (
    _channel_entries,
    _server_name,
    count_messages_by_dm_user,
    count_messages_by_server,
    count_messages_by_channel,
    _parse_timestamp,
    _granularity_format,
    _timeline_key,
    message_timeline,
    full_summary,
    message_summary,
)


class TestChannelEntries:
    def test_yields_all_channels(self, mock_export_dir):
        entries = list(_channel_entries(mock_export_dir))
        channel_ids = {e[1] for e in entries}
        assert "12345" in channel_ids
        assert "67890" in channel_ids
        assert "99999" in channel_ids

    def test_yields_correct_message_count(self, mock_export_dir):
        entries = list(_channel_entries(mock_export_dir))
        msg_counts = {e[1]: len(e[3]) for e in entries}
        assert msg_counts["12345"] == 5
        assert msg_counts["67890"] == 3
        assert msg_counts["99999"] == 0

    def test_resolves_channel_names(self, mock_export_dir):
        entries = list(_channel_entries(mock_export_dir))
        names = {e[1]: e[2] for e in entries}
        assert names["12345"] == "Direct Message with Alice#1234"


class TestServerName:
    def test_extracts_from_in_name(self, mock_export_dir):
        name = _server_name(mock_export_dir / "Nachrichten" / "c99999", "general in MyServer")
        assert name == "MyServer"

    def test_falls_back_to_channel_json(self, mock_export_dir):
        name = _server_name(mock_export_dir / "Nachrichten" / "c77777", "Unknown channel")
        assert name == "Unknown"

    def test_returns_unknown_when_no_guild(self, mock_export_dir):
        name = _server_name(mock_export_dir / "Nachrichten" / "c12345", "Something")
        assert name == "Unknown"


class TestCountMessagesByDmUser:
    def test_returns_sorted_counts(self, mock_export_dir):
        result = count_messages_by_dm_user(mock_export_dir)
        assert len(result) == 2
        assert result[0][0] == "Alice"
        assert result[0][1] == 5
        assert result[1][0] == "Bob"
        assert result[1][1] == 3

    def test_empty_dir(self, tmp_path):
        d = tmp_path / "empty"
        d.mkdir()
        (d / "Nachrichten").mkdir()
        (d / "Nachrichten" / "index.json").write_text("{}")
        result = count_messages_by_dm_user(d)
        assert result == []


class TestCountMessagesByServer:
    def test_excludes_dms(self, mock_export_dir):
        result = count_messages_by_server(mock_export_dir)
        names = [r[0] for r in result]
        assert "Alice" not in names
        assert "Bob" not in names


class TestCountMessagesByChannel:
    def test_returns_triples(self, mock_export_dir):
        result = count_messages_by_channel(mock_export_dir)
        assert all(len(r) == 3 for r in result)

    def test_sorted_descending(self, mock_export_dir):
        result = count_messages_by_channel(mock_export_dir)
        counts = [r[2] for r in result]
        assert counts == sorted(counts, reverse=True)

    def test_empty_channel_has_zero(self, mock_export_dir):
        result = count_messages_by_channel(mock_export_dir)
        empty = [r for r in result if r[0] == "99999"]
        assert len(empty) == 1
        assert empty[0][2] == 0


class TestParseTimestamp:
    def test_parses_valid(self):
        dt = _parse_timestamp("2024-01-15 10:00:00")
        assert dt == datetime(2024, 1, 15, 10, 0, 0)

    def test_returns_none_for_invalid(self):
        assert _parse_timestamp("not a date") is None
        assert _parse_timestamp("") is None

    def test_returns_none_for_wrong_format(self):
        assert _parse_timestamp("15/01/2024") is None


class TestGranularityFormat:
    def test_day_format(self):
        assert _granularity_format("day") == "%Y-%m-%d"
    def test_month_format(self):
        assert _granularity_format("month") == "%Y-%m"
    def test_year_format(self):
        assert _granularity_format("year") == "%Y"
    def test_unknown_defaults_to_month(self):
        assert _granularity_format("week") == "%Y-%m"
        assert _granularity_format("") == "%Y-%m"


class TestTimelineKey:
    def test_returns_formatted_key(self):
        result = _timeline_key("2024-01-15 10:00:00", "%Y-%m")
        assert result == "2024-01"

    def test_day_granularity(self):
        result = _timeline_key("2024-01-15 10:00:00", "%Y-%m-%d")
        assert result == "2024-01-15"

    def test_year_granularity(self):
        result = _timeline_key("2024-01-15 10:00:00", "%Y")
        assert result == "2024"

    def test_invalid_timestamp_returns_none(self):
        assert _timeline_key("bad", "%Y-%m") is None


class TestMessageTimeline:
    def test_monthly_timeline(self, mock_export_dir):
        tl = message_timeline(mock_export_dir, "month")
        assert "2024-01" in tl

    def test_day_timeline(self, mock_export_dir):
        tl = message_timeline(mock_export_dir, "day")
        assert tl["2024-01-15"] == 2

    def test_year_timeline(self, mock_export_dir):
        tl = message_timeline(mock_export_dir, "year")
        assert tl["2024"] == 7

    def test_total_matches_all_messages(self, mock_export_dir):
        tl = message_timeline(mock_export_dir, "month")
        assert sum(tl.values()) == 9

    def test_returns_empty_for_empty_dir(self, tmp_path):
        d = tmp_path / "empty"
        d.mkdir()
        (d / "Nachrichten").mkdir()
        (d / "Nachrichten" / "index.json").write_text("{}")
        assert message_timeline(d) == {}


class TestFullSummary:
    def test_returns_all_keys(self, mock_export_dir):
        s = full_summary(mock_export_dir)
        expected = {"total_messages", "dm_total", "server_total", "dm_users",
                     "servers", "channels", "timeline", "per_month"}
        assert set(s.keys()) == expected

    def test_total_counts(self, mock_export_dir):
        s = full_summary(mock_export_dir)
        assert s["total_messages"] == 9
        assert s["dm_total"] == 8

    def test_dm_users_sorted(self, mock_export_dir):
        s = full_summary(mock_export_dir)
        assert s["dm_users"][0][0] == "Alice"
        assert s["dm_users"][0][1] == 5

    def test_timeline_included(self, mock_export_dir):
        s = full_summary(mock_export_dir)
        assert isinstance(s["timeline"], dict)
        assert len(s["timeline"]) > 0

    def test_channels_sorted_descending(self, mock_export_dir):
        s = full_summary(mock_export_dir)
        counts = [c[2] for c in s["channels"]]
        assert counts == sorted(counts, reverse=True)

    def test_with_day_granularity(self, mock_export_dir):
        s = full_summary(mock_export_dir, granularity="day")
        assert "2024-01-15" in s["timeline"]


class TestMessageSummary:
    def test_returns_subset(self, mock_export_dir):
        s = message_summary(mock_export_dir)
        expected = {"total_messages", "dm_total", "server_total", "dm_users", "servers"}
        assert set(s.keys()) == expected

    def test_values_match_full_summary(self, mock_export_dir):
        fs = full_summary(mock_export_dir)
        ms = message_summary(mock_export_dir)
        for k in ms:
            assert ms[k] == fs[k]
