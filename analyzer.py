#!/usr/bin/env python3
"""Discord Data Export Analyzer.

Usage:
    python analyzer.py --dir "DC Daten" messages-dm
    python analyzer.py --dir "DC Daten" messages-server
    python analyzer.py --dir "DC Daten" messages-channel
    python analyzer.py --dir "DC Daten" messages-timeline [--granularity day|month|year]
    python analyzer.py --dir "DC Daten" voice
    python analyzer.py --dir "DC Daten" all
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from analyzers.messages import (
    count_messages_by_dm_user,
    count_messages_by_server,
    count_messages_by_channel,
    message_timeline,
    full_summary,
)
from analyzers.voice import voice_summary
from utils.formatting import format_hours_minutes


_SEPARATOR_WIDTH = 60


def _render_ranked_table(title, col_name, rows, name_width,
                         width=_SEPARATOR_WIDTH, top=None, more_noun=None):
    """Print a ranked name/count table with percentage column."""
    total = sum(c for _, c in rows)
    print(f"\n{'=' * width}")
    print(f"  {title}  (total: {total} messages)")
    print(f"{'=' * width}")
    print(f"  {col_name:<{name_width}} {'Messages':>8}  {'%':>6}")
    print(f"  {'-' * name_width} {'-' * 8}  {'-' * 6}")
    shown = rows[:top] if top else rows
    for name, count in shown:
        display = name if len(name) <= name_width else name[:name_width - 3] + "..."
        pct = (count / total * 100) if total else 0
        print(f"  {display:<{name_width}} {count:>8}  {pct:>5.1f}%")
    if top and len(rows) > top:
        print(f"  ... and {len(rows) - top} more {more_noun}")
    print()


def _render_timeline(timeline, granularity="month"):
    print(f"\n{'=' * _SEPARATOR_WIDTH}")
    print(f"  Message Timeline (by {granularity})")
    print(f"{'=' * _SEPARATOR_WIDTH}")
    max_count = max(timeline.values()) if timeline else 1
    for period, count in timeline.items():
        bar = "#" * min(int(count / max_count * 30), 30)
        print(f"  {period}  {count:>6}  {bar}")
    print()


def _render_duration_section(title, entries, name_width, unit):
    if not entries:
        return
    print(f"\n  {title}:")
    for c in entries:
        duration = format_hours_minutes(c["duration_seconds"])
        print(f"    {c['name']:<{name_width}} {duration}  ({c['call_count']} {unit})")


def _render_voice(summary):
    print(f"\n{'=' * _SEPARATOR_WIDTH}")
    print("  Voice Call Analysis")
    print(f"{'=' * _SEPARATOR_WIDTH}")
    print(f"  Total sessions:       {summary['total_sessions']}")
    print(f"  Total voice time:     {summary['total_duration_formatted']} ({summary['total_duration_seconds']}s)")
    print(f"  Average session:      {summary['average_duration_seconds'] // 60}m {summary['average_duration_seconds'] % 60}s")
    print(f"  Longest session:      {summary['longest_session_seconds'] // 60}m {summary['longest_session_seconds'] % 60}s")

    if summary["sessions_by_day"]:
        print("\n  Sessions per day:")
        for day, count in summary["sessions_by_day"].items():
            bar = "#" * count
            print(f"    {day}  {count:>2}  {bar}")

    durations = summary.get("channel_durations", [])
    _render_duration_section(
        "DM Call Duration by User",
        [c for c in durations if c["name_type"] == "dm"], 30, "calls")
    _render_duration_section(
        "Server Voice Channel Duration",
        [c for c in durations if c["name_type"] == "server"], 50, "sessions")
    _render_duration_section(
        "Other Voice Channels",
        [c for c in durations if c["name_type"] == "unknown"], 50, "sessions")

    if summary.get("sessions"):
        print("\n  Recent sessions:")
        for s in summary["sessions"][-10:]:
            print(f"    {s['start']} -- {s['duration_minutes']}min")

    print()


def print_dm_users(export_dir: Path, top: int = 50):
    """Print the most-messaged DM contacts, ranked."""
    _render_ranked_table("DM Messages by User", "User",
                         count_messages_by_dm_user(export_dir), 30,
                         top=top, more_noun="users")


def print_server(export_dir: Path):
    """Print message volume per server."""
    _render_ranked_table("Messages by Server", "Server",
                         count_messages_by_server(export_dir), 40)


def print_channels(export_dir: Path, top: int = 30):
    """Print detailed per-channel message counts."""
    rows = [(name, count) for _id, name, count in count_messages_by_channel(export_dir)]
    _render_ranked_table("Messages by Channel", "Channel", rows, 45,
                         width=80, top=top, more_noun="channels")


def print_timeline(export_dir: Path, granularity: str = "month"):
    """Print message activity over time."""
    _render_timeline(message_timeline(export_dir, granularity), granularity)


def print_voice(export_dir: Path):
    """Print voice call duration analysis."""
    _render_voice(voice_summary(export_dir))


def print_all(export_dir: Path):
    """Print the full report: messages, servers, channels, timeline, voice."""
    s = full_summary(export_dir)
    print(f"\n{'=' * _SEPARATOR_WIDTH}")
    print("  FULL DISCORD DATA ANALYSIS")
    print(f"{'=' * _SEPARATOR_WIDTH}")
    print(f"  Total messages sent:  {s['total_messages']}")
    print(f"    - DM messages:       {s['dm_total']}")
    print(f"    - Server messages:   {s['server_total']}")

    _render_ranked_table("DM Messages by User", "User", s["dm_users"], 30,
                         top=50, more_noun="users")
    _render_ranked_table("Messages by Server", "Server", s["servers"], 40)
    _render_ranked_table("Messages by Channel", "Channel",
                         [(name, count) for _id, name, count in s["channels"]],
                         45, width=80, top=30, more_noun="channels")
    _render_timeline(s["timeline"])
    _render_voice(voice_summary(export_dir))


def main():
    parser = argparse.ArgumentParser(
        description="Discord Data Export Analyzer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python analyzer.py --dir "DC Daten" messages-dm
  python analyzer.py --dir "DC Daten" messages-server
  python analyzer.py --dir "DC Daten" messages-timeline --granularity day
  python analyzer.py --dir "DC Daten" voice
  python analyzer.py --dir "DC Daten" all
        """,
    )
    parser.add_argument(
        "--dir",
        required=True,
        type=Path,
        help="Path to the Discord data export directory",
    )

    sub = parser.add_subparsers(dest="command", help="Analysis type")

    sub.add_parser("messages-dm", help="Count messages per DM user")
    sub.add_parser("messages-server", help="Count messages per server")
    sub.add_parser("messages-channel", help="Count messages per channel")
    timeline = sub.add_parser("messages-timeline", help="Message count over time")
    timeline.add_argument(
        "--granularity",
        choices=["day", "month", "year"],
        default="month",
        help="Timeline granularity (default: month)",
    )
    sub.add_parser("voice", help="Voice call duration analysis")
    sub.add_parser("all", help="Full analysis (all of the above)")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if not args.dir.exists():
        print(f"Error: Directory not found: {args.dir}", file=sys.stderr)
        sys.exit(1)

    commands = {
        "messages-dm": lambda: print_dm_users(args.dir),
        "messages-server": lambda: print_server(args.dir),
        "messages-channel": lambda: print_channels(args.dir),
        "messages-timeline": lambda: print_timeline(args.dir, args.granularity),
        "voice": lambda: print_voice(args.dir),
        "all": lambda: print_all(args.dir),
    }

    commands[args.command]()


if __name__ == "__main__":
    main()
