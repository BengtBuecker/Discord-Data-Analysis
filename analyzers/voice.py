"""Voice call analysis from Discord analytics events.

Uses grep pre-filtering for 4GB+ analytics files, then processes only
RTC-relevant events in Python. Detects voice call sessions from
`client_rtc_state: "RTC_CONNECTED"` sequences.
"""

import json
import re
import subprocess
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Iterator, List, Optional

from utils.formatting import format_hours_minutes
from utils.parser import (
    extract_dm_username,
    iter_analytics_files,
    load_index,
)


@dataclass
class VoiceSession:
    """A detected voice call session."""

    start: datetime
    end: Optional[datetime]
    duration_seconds: float


def _parse_timestamp(ts_str: object) -> Optional[datetime]:
    """Parse various timestamp formats from analytics events."""
    if not ts_str:
        return None
    ts_str = str(ts_str).strip().strip('"')
    ts_str = ts_str.replace(" UTC", "")
    formats = [
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%dT%H:%M:%SZ",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(ts_str, fmt)
        except ValueError:
            continue
    return None


def _iter_matching_lines(filepath: Path, pattern: str) -> Iterator[str]:
    """Python fallback: yield lines matching pattern, streamed line by line."""
    rx = re.compile(pattern)
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            if rx.search(line):
                yield line.strip()


def _grep_json_lines(
    files: List[Path], pattern: str, progress_callback=None
) -> Iterator[dict]:
    """
    Yield parsed JSON objects from lines matching pattern across files.
    Uses grep to pre-filter (much faster than Python for 4GB+ files on slow
    mounts); falls back to a Python scan when grep is missing or times out.
    """
    total_files = len(files)

    for fi, filepath in enumerate(files):
        if filepath.stat().st_size > 0:
            lines: Optional[Iterator[str]] = None
            try:
                proc = subprocess.run(
                    ["grep", "-E", pattern, str(filepath)],
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
                lines = iter(proc.stdout.splitlines())
            except (subprocess.TimeoutExpired, FileNotFoundError):
                lines = None

            if lines is None:
                lines = _iter_matching_lines(filepath, pattern)

            for line in lines:
                if not line:
                    continue
                try:
                    ev = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(ev, dict):
                    yield ev

        if progress_callback:
            progress_callback(fi + 1, total_files)


def _stream_rtc_events_via_grep(
    activity_dir: Path, progress_callback=None
) -> Iterator[tuple]:
    """
    Stream RTC heartbeat events from analytics files.
    Yields: (session_id, uptime_seconds, rtc_state, init_timestamp)
    """
    files = iter_analytics_files(activity_dir)
    for ev in _grep_json_lines(files, r"RTC_CONNECTED|RTC_DISCONNECTED", progress_callback):
        sid = ev.get("client_heartbeat_session_id")
        rtc = ev.get("client_rtc_state")
        if sid and rtc:
            yield (
                str(sid),
                int(ev.get("uptime_process_renderer", 0)),
                str(rtc),
                str(ev.get("client_heartbeat_initialization_timestamp", "")),
            )


def _stream_leave_voice_events(
    activity_dir: Path, progress_callback=None
) -> Iterator[tuple]:
    """
    Stream leave_voice_channel events with per-channel call durations.
    Only scans subdirectories known to contain these events — the large
    analytics/ folder holds client heartbeats and would take minutes to grep.
    Yields: (channel_id, guild_id, duration_ms, timestamp)
    """
    files: List[Path] = []
    for sub in ("tns", "reporting", "modeling"):
        sub_path = activity_dir / sub
        if sub_path.exists():
            files.extend(iter_analytics_files(sub_path))
    files = sorted(files)

    for ev in _grep_json_lines(files, "leave_voice_channel", progress_callback):
        cid = ev.get("channel_id")
        dur = ev.get("duration", 0)
        if cid and dur:
            yield (
                str(cid),
                str(ev.get("guild_id") or ""),
                int(dur),
                str(ev.get("timestamp", "")),
            )


def _append_session(sessions: List[VoiceSession], init_dt: datetime,
                    start_uptime: float, end_uptime: float,
                    min_duration_seconds: int) -> None:
    """Append a VoiceSession if its duration meets the minimum threshold."""
    duration = end_uptime - start_uptime
    if duration >= min_duration_seconds:
        sessions.append(
            VoiceSession(
                start=init_dt + timedelta(seconds=start_uptime),
                end=init_dt + timedelta(seconds=end_uptime),
                duration_seconds=duration,
            )
        )


def detect_voice_sessions(
    activity_dir: Path,
    min_duration_seconds: int = 30,
    progress_callback=None,
) -> List[VoiceSession]:
    """Stream analytics files (via grep pre-filter) and detect voice sessions."""
    sessions_events: Dict[str, List[tuple]] = defaultdict(list)
    sessions_init_ts: Dict[str, str] = {}

    total_rtc_events = 0
    for sid, uptime, rtc, init_ts in _stream_rtc_events_via_grep(activity_dir, progress_callback):
        sessions_events[sid].append((uptime, rtc))
        total_rtc_events += 1
        if init_ts and sid not in sessions_init_ts:
            sessions_init_ts[sid] = str(init_ts)

    print(f"\n  Found {total_rtc_events} RTC events across {len(sessions_events)} sessions.", file=sys.stderr)

    voice_sessions: List[VoiceSession] = []
    session_count = len(sessions_events)

    for idx, (sid, events) in enumerate(sessions_events.items()):
        if progress_callback and idx % 100 == 0:
            print(f"\r  Processing sessions... {idx}/{session_count}", end="", file=sys.stderr)

        init_ts_raw = sessions_init_ts.get(sid)
        if not init_ts_raw:
            continue
        init_dt = _parse_timestamp(init_ts_raw)
        if init_dt is None:
            continue

        events.sort(key=lambda x: x[0])

        start_uptime = None
        for uptime, rtc in events:
            if rtc == "RTC_CONNECTED" and start_uptime is None:
                start_uptime = uptime
            elif rtc != "RTC_CONNECTED" and start_uptime is not None:
                _append_session(voice_sessions, init_dt, start_uptime, uptime,
                                min_duration_seconds)
                start_uptime = None

        if start_uptime is not None and events:
            _append_session(voice_sessions, init_dt, start_uptime,
                            events[-1][0], min_duration_seconds)

    if progress_callback:
        print("", file=sys.stderr)

    voice_sessions.sort(key=lambda s: s.start)
    return voice_sessions


def aggregate_channel_durations(
    activity_dir: Path, export_dir: Path, progress_callback=None
) -> Dict[str, dict]:
    """
    Aggregate voice call duration per channel/user from leave_voice_channel events.
    Resolves channel IDs to human-readable names via Nachrichten/index.json.
    """
    channel_totals: Dict[str, dict] = {}

    for cid, gid, dur_ms, ts in _stream_leave_voice_events(activity_dir, progress_callback):
        if cid not in channel_totals:
            channel_totals[cid] = {
                "channel_id": cid,
                "guild_id": gid,
                "duration_ms": 0,
                "call_count": 0,
            }
        channel_totals[cid]["duration_ms"] += dur_ms
        channel_totals[cid]["call_count"] += 1

    if progress_callback:
        print("\n  Resolving channel names...", file=sys.stderr)

    try:
        index = load_index(export_dir)
    except FileNotFoundError:
        index = {}

    results: Dict[str, dict] = {}
    for cid, info in channel_totals.items():
        raw_name = index.get(cid, "")
        username = extract_dm_username(raw_name)
        if username:
            name, name_type = username, "dm"
        elif raw_name and raw_name not in ("Unknown channel", "None"):
            name, name_type = raw_name, "server"
        else:
            name, name_type = f"#{cid}", "unknown"

        results[name] = {
            "name": name,
            "channel_id": cid,
            "guild_id": info["guild_id"],
            "duration_seconds": round(info["duration_ms"] / 1000),
            "duration_minutes": round(info["duration_ms"] / 60000, 1),
            "duration_hours": round(info["duration_ms"] / 3600000, 2),
            "call_count": info["call_count"],
            "name_type": name_type,
        }

    return results


def voice_summary(export_dir: Path) -> dict:
    """Voice activity summary. Uses grep streaming for large files."""
    activity_dir = export_dir / "Aktivität"
    if not activity_dir.exists():
        return {"total_sessions": 0, "total_duration_seconds": 0, "error": "No Aktivität directory"}

    def progress(current: int, total: int):
        pct = current / total * 100 if total else 0
        print(f"\r  Scanning files... {current}/{total} ({pct:.0f}%)", end="", file=sys.stderr)

    print("  Scanning voice activity via grep...", file=sys.stderr)
    sessions = detect_voice_sessions(activity_dir, progress_callback=progress)
    print("", file=sys.stderr)

    # Aggregate per-channel durations from leave_voice_channel events
    channel_durations = aggregate_channel_durations(activity_dir, export_dir, progress_callback=progress)

    sorted_channels = sorted(
        channel_durations.values(), key=lambda x: x["duration_seconds"], reverse=True
    )

    if not sessions:
        return {
            "total_sessions": 0,
            "total_duration_seconds": 0,
            "total_duration_formatted": "0h 0m",
            "average_duration_seconds": 0,
            "longest_session_seconds": 0,
            "sessions_by_day": {},
            "sessions": [],
            "channel_durations": sorted_channels,
        }

    total_duration = sum(s.duration_seconds for s in sessions)
    avg_duration = total_duration / len(sessions) if sessions else 0
    longest = max(s.duration_seconds for s in sessions) if sessions else 0

    by_day = Counter(s.start.strftime("%Y-%m-%d") for s in sessions)

    return {
        "total_sessions": len(sessions),
        "total_duration_seconds": int(total_duration),
        "total_duration_formatted": format_hours_minutes(total_duration),
        "average_duration_seconds": int(avg_duration),
        "longest_session_seconds": int(longest),
        "sessions_by_day": dict(sorted(by_day.items())),
        "sessions": [
            {
                "start": s.start.strftime("%Y-%m-%d %H:%M:%S"),
                "end": s.end.strftime("%Y-%m-%d %H:%M:%S") if s.end else "ongoing",
                "duration_minutes": round(s.duration_seconds / 60, 1),
            }
            for s in sessions
        ],
        "channel_durations": sorted_channels,
    }
