#!/usr/bin/env python3
"""Discord Data Export Analyzer.

Usage:
    python analyzer.py --dir "DC Daten" messages-dm
    python analyzer.py --dir "DC Daten" messages-server
    python analyzer.py --dir "DC Daten" messages-channel
    python analyzer.py --dir "DC Daten" voice
    python analyzer.py --dir "DC Daten" all
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from analyzers.messages import (
    count_messages_by_dm_user,
    count_messages_by_server,
    count_messages_by_channel,
    message_timeline,
    message_summary,
)
from analyzers.voice import voice_summary


def print_dm_users(export_dir: Path, top: int = 50):
    results = count_messages_by_dm_user(export_dir)
    total = sum(c for _, c in results)
    print(f"\n{'='*60}")
    print(f"  DM Messages by User  (total: {total} messages)")
    print(f"{'='*60}")
    print(f"  {'User':<30} {'Messages':>8}  {'%':>6}")
    print(f"  {'-'*30} {'-'*8}  {'-'*6}")
    for username, count in results[:top]:
        pct = (count / total * 100) if total else 0
        print(f"  {username:<30} {count:>8}  {pct:>5.1f}%")
    if len(results) > top:
        print(f"  ... and {len(results) - top} more users")
    print()


def print_server(export_dir: Path):
    results = count_messages_by_server(export_dir)
    total = sum(c for _, c in results)
    print(f"\n{'='*60}")
    print(f"  Messages by Server  (total: {total} messages)")
    print(f"{'='*60}")
    print(f"  {'Server':<40} {'Messages':>8}  {'%':>6}")
    print(f"  {'-'*40} {'-'*8}  {'-'*6}")
    for name, count in results:
        pct = (count / total * 100) if total else 0
        print(f"  {name:<40} {count:>8}  {pct:>5.1f}%")
    print()


def print_channels(export_dir: Path, top: int = 30):
    results = count_messages_by_channel(export_dir)
    total = sum(c for _, _, c in results)
    print(f"\n{'='*80}")
    print(f"  Messages by Channel  (total: {total} messages)")
    print(f"{'='*80}")
    print(f"  {'Channel':<45} {'Messages':>8}  {'%':>6}")
    print(f"  {'-'*45} {'-'*8}  {'-'*6}")
    for ch_id, ch_name, count in results[:top]:
        display = ch_name if len(ch_name) < 45 else ch_name[:42] + "..."
        pct = (count / total * 100) if total else 0
        print(f"  {display:<45} {count:>8}  {pct:>5.1f}%")
    if len(results) > top:
        print(f"  ... and {len(results) - top} more channels")
    print()


def print_timeline(export_dir: Path, granularity: str = "month"):
    timeline = message_timeline(export_dir, granularity)
    print(f"\n{'='*50}")
    print(f"  Message Timeline (by {granularity})")
    print(f"{'='*50}")
    max_count = max(timeline.values()) if timeline else 1
    for period, count in timeline.items():
        bar = "#" * min(int(count / max_count * 30), 30)
        print(f"  {period}  {count:>6}  {bar}")
    print()


def print_voice(export_dir: Path):
    summary = voice_summary(export_dir)
    print(f"\n{'='*60}")
    print(f"  Voice Call Analysis")
    print(f"{'='*60}")
    print(f"  Total sessions:       {summary['total_sessions']}")
    print(f"  Total voice time:     {summary['total_duration_formatted']} ({summary['total_duration_seconds']}s)")
    print(f"  Average session:      {summary['average_duration_seconds'] // 60}m {summary['average_duration_seconds'] % 60}s")
    print(f"  Longest session:      {summary['longest_session_seconds'] // 60}m {summary['longest_session_seconds'] % 60}s")

    if summary["sessions_by_day"]:
        print(f"\n  Sessions per day:")
        for day, count in summary["sessions_by_day"].items():
            bar = "#" * count
            print(f"    {day}  {count:>2}  {bar}")

    if summary.get("channel_durations"):
        dm_entries = [c for c in summary["channel_durations"] if c["name_type"] == "dm"]
        server_entries = [c for c in summary["channel_durations"] if c["name_type"] == "server"]
        unknown_entries = [c for c in summary["channel_durations"] if c["name_type"] == "unknown"]

        if dm_entries:
            print(f"\n  DM Call Duration by User:")
            for c in dm_entries:
                h = c["duration_seconds"] // 3600
                m = (c["duration_seconds"] % 3600) // 60
                print(f"    {c['name']:<30} {h}h {m}m  ({c['call_count']} calls)")

        if server_entries:
            print(f"\n  Server Voice Channel Duration:")
            for c in server_entries:
                h = c["duration_seconds"] // 3600
                m = (c["duration_seconds"] % 3600) // 60
                print(f"    {c['name']:<50} {h}h {m}m  ({c['call_count']} sessions)")

        if unknown_entries:
            print(f"\n  Other Voice Channels:")
            for c in unknown_entries:
                h = c["duration_seconds"] // 3600
                m = (c["duration_seconds"] % 3600) // 60
                print(f"    {c['name']:<50} {h}h {m}m  ({c['call_count']} sessions)")

    if summary.get("sessions"):
        print(f"\n  Recent sessions:")
        for s in summary["sessions"][-10:]:
            print(f"    {s['start']} -- {s['duration_minutes']}min")

    print()


def print_all(export_dir: Path):
    summary = message_summary(export_dir)
    print(f"\n{'='*60}")
    print(f"  FULL DISCORD DATA ANALYSIS")
    print(f"{'='*60}")
    print(f"  Total messages sent:  {summary['total_messages']}")
    print(f"    - DM messages:       {summary['dm_total']}")
    print(f"    - Server messages:   {summary['server_total']}")

    print_dm_users(export_dir)
    print_server(export_dir)
    print_channels(export_dir)
    print_timeline(export_dir)
    print_voice(export_dir)


def main():
    parser = argparse.ArgumentParser(
        description="Discord Data Export Analyzer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python analyzer.py --dir "DC Daten" messages-dm
  python analyzer.py --dir "DC Daten" messages-server
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
    _timeline = sub.add_parser("messages-timeline", help="Message count over time")
    _timeline.add_argument(
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
        "messages-timeline": lambda: print_timeline(args.dir, getattr(args, "granularity", "month")),
        "voice": lambda: print_voice(args.dir),
        "all": lambda: print_all(args.dir),
    }

    commands[args.command]()


if __name__ == "__main__":
    main()
