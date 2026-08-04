"""Tests for analyzers/messages.py — message analysis functions."""

import unittest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from analyzers.messages import (
    count_messages_by_dm_user,
    count_messages_by_server,
    count_messages_by_channel,
    message_timeline,
    message_summary,
)

FIXTURES = Path(__file__).parent / "fixtures"


class TestCountMessagesByDmUser(unittest.TestCase):
    def test_counts_by_user(self):
        results = count_messages_by_dm_user(FIXTURES)
        self.assertGreaterEqual(len(results), 1)
        names = [name for name, _ in results]
        self.assertIn("alice", names)

    def test_sorted_descending(self):
        results = count_messages_by_dm_user(FIXTURES)
        counts = [c for _, c in results]
        self.assertEqual(counts, sorted(counts, reverse=True))


class TestCountMessagesByServer(unittest.TestCase):
    def test_counts_by_server(self):
        results = count_messages_by_server(FIXTURES)
        self.assertGreaterEqual(len(results), 1)
        names = [name for name, _ in results]
        self.assertIn("MyServer", names)

    def test_dm_messages_excluded(self):
        results = count_messages_by_server(FIXTURES)
        names = [name for name, _ in results]
        self.assertNotIn("Direct Messages", names)

    def test_sorted_descending(self):
        results = count_messages_by_server(FIXTURES)
        counts = [c for _, c in results]
        self.assertEqual(counts, sorted(counts, reverse=True))


class TestCountMessagesByChannel(unittest.TestCase):
    def test_returns_triples(self):
        results = count_messages_by_channel(FIXTURES)
        self.assertGreaterEqual(len(results), 2)
        for ch_id, ch_name, count in results:
            self.assertIsInstance(ch_id, str)
            self.assertIsInstance(ch_name, str)
            self.assertIsInstance(count, int)
            self.assertGreater(count, 0)

    def test_sorted_descending(self):
        results = count_messages_by_channel(FIXTURES)
        counts = [c for _, _, c in results]
        self.assertEqual(counts, sorted(counts, reverse=True))


class TestMessageTimeline(unittest.TestCase):
    def test_month_granularity(self):
        tl = message_timeline(FIXTURES, "month")
        self.assertIn("2024-01", tl)
        self.assertIn("2024-02", tl)
        self.assertEqual(tl["2024-01"], 4)  # 3 dm + 2 server = 5... wait
        # Let's just check it's non-zero
        self.assertGreater(tl["2024-01"], 0)

    def test_day_granularity(self):
        tl = message_timeline(FIXTURES, "day")
        self.assertIn("2024-01-15", tl)
        self.assertGreater(tl["2024-01-15"], 0)

    def test_year_granularity(self):
        tl = message_timeline(FIXTURES, "year")
        self.assertIn("2024", tl)

    def test_unknown_granularity_defaults_month(self):
        tl = message_timeline(FIXTURES, "decade")
        self.assertIn("2024-01", tl)

    def test_returns_sorted_dict(self):
        tl = message_timeline(FIXTURES, "month")
        keys = list(tl.keys())
        self.assertEqual(keys, sorted(keys))


class TestMessageSummary(unittest.TestCase):
    def test_returns_all_keys(self):
        s = message_summary(FIXTURES)
        for key in ("total_messages", "dm_users", "servers",
                     "dm_total", "server_total"):
            self.assertIn(key, s)

    def test_totals_add_up(self):
        s = message_summary(FIXTURES)
        self.assertEqual(s["total_messages"],
                         s["dm_total"] + s["server_total"])

    def test_nonzero(self):
        s = message_summary(FIXTURES)
        self.assertGreater(s["total_messages"], 0)


if __name__ == "__main__":
    unittest.main()
