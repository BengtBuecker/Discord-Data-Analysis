"""Tests for utils/parser.py — data access layer."""

import json
import unittest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

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


class TestLoadHelpers(unittest.TestCase):
    def test_load_index(self):
        idx = load_index(FIXTURES)
        self.assertEqual(idx["1234"], "Direct Message with alice#0")
        self.assertEqual(idx["5678"], "general-chat in MyServer")

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


if __name__ == "__main__":
    unittest.main()
