"""Tests for utils/parser.py — data access layer."""

import json
import unittest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.parser import (
    load_json,
    load_json_lines,
    load_user,
    load_index,
    load_server_index,
    load_channel_info,
    load_messages,
    iter_message_channels,
    dirname_to_channel_id,
    iter_analytics_files,
    extract_dm_username,
    categorize_channels,
)

FIXTURES = Path(__file__).parent / "fixtures"


class TestLoadJson(unittest.TestCase):
    def test_loads_valid_json(self):
        result = load_json(FIXTURES / "Account" / "user.json")
        self.assertEqual(result["id"], "123456789")
        self.assertEqual(result["username"], "testuser")

    def test_raises_on_missing_file(self):
        with self.assertRaises(FileNotFoundError):
            load_json(FIXTURES / "nonexistent.json")

    def test_raises_on_invalid_json(self):
        bad = FIXTURES / "_bad.json"
        bad.write_text("not json")
        with self.assertRaises(json.JSONDecodeError):
            load_json(bad)
        bad.unlink()


class TestLoadJsonLines(unittest.TestCase):
    def test_iterates_lines(self):
        lines = list(load_json_lines(FIXTURES / "Aktivität" / "tns" / "events-00001.json"))
        self.assertEqual(len(lines), 5)
        self.assertEqual(lines[0]["event_id"], "evt_101")

    def test_skips_empty_lines(self):
        f = FIXTURES / "_test_lines.json"
        f.write_text('{"a":1}\n\n{"b":2}\n')
        lines = list(load_json_lines(f))
        self.assertEqual(len(lines), 2)
        f.unlink()

    def test_raises_on_bad_line(self):
        f = FIXTURES / "_bad_line.json"
        f.write_text('{"a":1}\nnot json\n')
        with self.assertRaises(json.JSONDecodeError):
            list(load_json_lines(f))
        f.unlink()


class TestLoadHelpers(unittest.TestCase):
    def test_load_user(self):
        u = load_user(FIXTURES)
        self.assertEqual(u["id"], "123456789")

    def test_load_index(self):
        idx = load_index(FIXTURES)
        self.assertEqual(idx["1234"], "Direct Message with alice#0")
        self.assertEqual(idx["5678"], "general-chat in MyServer")

    def test_load_server_index(self):
        sidx = load_server_index(FIXTURES)
        self.assertEqual(sidx["9876"], "MyServer")

    def test_load_channel_info(self):
        info = load_channel_info(FIXTURES / "Nachrichten" / "c1234")
        self.assertEqual(info["id"], "1234")

    def test_load_messages(self):
        msgs = load_messages(FIXTURES / "Nachrichten" / "c1234")
        self.assertEqual(len(msgs), 3)

    def test_load_index_missing(self):
        with self.assertRaises(FileNotFoundError):
            load_index(Path("/nonexistent"))


class TestIterMessageChannels(unittest.TestCase):
    def test_yields_channel_dirs(self):
        dirs = list(iter_message_channels(FIXTURES / "Nachrichten"))
        names = sorted(d.name for d in dirs)
        self.assertEqual(names, ["c1234", "c5678"])

    def test_skips_missing_messages(self):
        empty = FIXTURES / "_empty_ch"
        empty.mkdir(exist_ok=True)
        dirs = list(iter_message_channels(empty))
        self.assertEqual(len(dirs), 0)
        empty.rmdir()


class TestDirnameToChannelId(unittest.TestCase):
    def test_strips_c_prefix(self):
        self.assertEqual(dirname_to_channel_id("c1234"), "1234")

    def test_no_c_prefix_passthrough(self):
        self.assertEqual(dirname_to_channel_id("1234"), "1234")


class TestIterAnalyticsFiles(unittest.TestCase):
    def test_finds_all_json(self):
        files = iter_analytics_files(FIXTURES / "Aktivität")
        names = sorted(f.name for f in files)
        self.assertIn("events-00001.json", names)
        self.assertGreaterEqual(len(files), 3)

    def test_empty_dir(self):
        files = iter_analytics_files(Path("/nonexistent_dir_xyz"))
        self.assertEqual(len(files), 0)


class TestExtractDmUsername(unittest.TestCase):
    def test_extracts_direct_message(self):
        self.assertEqual(
            extract_dm_username("Direct Message with alice#0"), "alice")

    def test_extracts_without_discriminator(self):
        self.assertEqual(
            extract_dm_username("Direct Message with bob"), "bob")

    def test_returns_none_for_server(self):
        self.assertIsNone(
            extract_dm_username("general-chat in MyServer"))

    def test_returns_none_for_plain(self):
        self.assertIsNone(extract_dm_username("general-chat"))


class TestCategorizeChannels(unittest.TestCase):
    def test_categorizes_dm_and_server(self):
        index = {
            "ch1": "Direct Message with alice#0",
            "ch2": "general in MyServer",
            "ch3": "plain-channel",
        }
        server_index = {"srv1": "MyServer"}
        result = categorize_channels(index, server_index)

        self.assertIn("alice", result["dm_users"])
        self.assertIn("MyServer", result["guild_channels"])
        self.assertIn("ch3", result["unknown"])

    def test_multiple_users_same_name(self):
        index = {"ch1": "Direct Message with alice#0",
                  "ch2": "Direct Message with alice#1234"}
        result = categorize_channels(index, {})
        self.assertEqual(len(result["dm_users"]["alice"]), 2)


if __name__ == "__main__":
    unittest.main()
