"""Tests for utils/parser.py — all 8 parser functions."""

import json
from pathlib import Path

import pytest

from utils.parser import (
    load_json,
    load_index,
    load_channel_info,
    load_messages,
    iter_message_channels,
    dirname_to_channel_id,
    iter_analytics_files,
    extract_dm_username,
)


class TestLoadJson:
    def test_loads_valid_json(self, tmp_path):
        p = tmp_path / "test.json"
        p.write_text('{"a": 1, "b": [2]}')
        assert load_json(p) == {"a": 1, "b": [2]}

    def test_loads_empty_object(self, tmp_path):
        p = tmp_path / "empty.json"
        p.write_text("{}")
        assert load_json(p) == {}

    def test_loads_array(self, tmp_path):
        p = tmp_path / "arr.json"
        p.write_text('[1, 2, 3]')
        assert load_json(p) == [1, 2, 3]

    def test_raises_on_missing_file(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_json(tmp_path / "nope.json")

    def test_raises_on_invalid_json(self, tmp_path):
        p = tmp_path / "bad.json"
        p.write_text("{invalid")
        with pytest.raises(json.JSONDecodeError):
            load_json(p)

    def test_loads_unicode(self, tmp_path):
        p = tmp_path / "uni.json"
        p.write_text('{"name": "Müller", "emoji": "🎄"}')
        assert load_json(p)["name"] == "Müller"


class TestLoadIndex:
    def test_loads_mapping(self, mock_export_dir):
        result = load_index(mock_export_dir)
        assert "12345" in result
        assert result["12345"] == "Direct Message with Alice#1234"
        assert result["99999"] == "general in MyServer"

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_index(tmp_path)


class TestLoadChannelInfo:
    def test_loads_channel_json(self, mock_export_dir):
        info = load_channel_info(mock_export_dir / "Nachrichten" / "c12345")
        assert info["id"] == "12345"
        assert info["type"] == 0

    def test_missing_channel_json(self, mock_export_dir):
        with pytest.raises(FileNotFoundError):
            load_channel_info(mock_export_dir / "Nachrichten" / "nonexistent")


class TestLoadMessages:
    def test_loads_message_array(self, mock_export_dir):
        msgs = load_messages(mock_export_dir / "Nachrichten" / "c12345")
        assert len(msgs) == 5
        assert msgs[0]["Contents"] == "Hello Alice"

    def test_empty_channel(self, mock_export_dir):
        msgs = load_messages(mock_export_dir / "Nachrichten" / "c99999")
        assert msgs == []


class TestIterMessageChannels:
    def test_iterates_valid_channels(self, mock_export_dir):
        channels = list(iter_message_channels(mock_export_dir / "Nachrichten"))
        names = {c.name for c in channels}
        assert "c12345" in names
        assert "c99999" in names

    def test_skips_dirs_without_messages_json(self, tmp_path):
        d = tmp_path / "chans"
        d.mkdir()
        (d / "c1").mkdir()
        (d / "c1" / "messages.json").write_text("[]")
        (d / "c2").mkdir()
        channels = list(iter_message_channels(d))
        assert len(channels) == 1
        assert channels[0].name == "c1"

    def test_empty_dir(self, tmp_path):
        d = tmp_path / "empty"
        d.mkdir()
        assert list(iter_message_channels(d)) == []


class TestDirnameToChannelId:
    def test_strips_c_prefix(self):
        assert dirname_to_channel_id("c12345") == "12345"
        assert dirname_to_channel_id("c999") == "999"

    def test_no_prefix_passthrough(self):
        assert dirname_to_channel_id("12345") == "12345"
        assert dirname_to_channel_id("abc") == "abc"

    def test_empty_string(self):
        assert dirname_to_channel_id("") == ""

    def test_single_c(self):
        assert dirname_to_channel_id("c") == ""


class TestIterAnalyticsFiles:
    def test_finds_json_files(self, mock_export_dir):
        files = iter_analytics_files(mock_export_dir / "Aktivität")
        assert len(files) >= 1

    def test_missing_dir_returns_empty(self, tmp_path):
        assert iter_analytics_files(tmp_path / "nope") == []

    def test_skips_non_json(self, tmp_path):
        d = tmp_path / "data"
        d.mkdir()
        (d / "events.txt").write_text("hello")
        assert iter_analytics_files(d) == []


class TestExtractDmUsername:
    def test_extracts_username(self):
        assert extract_dm_username("Direct Message with Alice#1234") == "Alice"
        assert extract_dm_username("Direct Message with Bob") == "Bob"

    def test_extracts_username_with_spaces(self):
        assert extract_dm_username("Direct Message with John Doe#5678") == "John Doe"

    def test_returns_none_for_server_channel(self):
        assert extract_dm_username("general in MyServer") is None

    def test_returns_none_for_unknown(self):
        assert extract_dm_username("Unknown channel") is None
        assert extract_dm_username("") is None
        assert extract_dm_username("random text") is None

    def test_handles_no_discriminator(self):
        assert extract_dm_username("Direct Message with userName") == "userName"

    def test_handles_zero_discriminator(self):
        assert extract_dm_username("Direct Message with user#0") == "user"
