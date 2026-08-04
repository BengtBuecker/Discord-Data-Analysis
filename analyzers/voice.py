"""Voice call analysis from Discord analytics events.

Uses grep pre-filtering for 4GB+ analytics files, then processes only
RTC-relevant events in Python. Detects voice call sessions from
`client_rtc_state: "RTC_CONNECTED"` sequences.
"""

import json
import subprocess
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Iterator, List, Optional

from utils.parser import iter_analytics_files


@dataclass
class VoiceSession:
    """A detected voice call session."""

    start: datetime
    end: Optional[datetime]
    duration_seconds: float


def _parse_ts(ts_str) -> Optional[datetime]:
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


def _stream_rtc_events_via_grep(
    activity_dir: Path, progress_callback=None
) -> Iterator[tuple]:
    """
    Use grep to pre-filter analytics files for RTC events, then parse.
    Much faster than Python line-by-line for 4GB+ files on slow mounts.
    """
    files = iter_analytics_files(activity_dir)
    total_files = len(files)

    for fi, filepath in enumerate(files):
        fsize = filepath.stat().st_size
        if fsize == 0:
            if progress_callback:
                progress_callback(fi + 1, total_files)
            continue

        try:
            proc = subprocess.Popen(
                ["grep", "-E", "RTC_CONNECTED|RTC_DISCONNECTED", str(filepath)],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
            )
            for line in proc.stdout:
                line = line.strip()
                if not line:
                    continue
                try:
                    ev = json.loads(line)
                except Exception:
                    continue

                rtc = ev.get("client_rtc_state")
                sid = ev.get("client_heartbeat_session_id")
                uptime = int(ev.get("uptime_process_renderer", 0))
                init_ts_raw = ev.get("client_heartbeat_initialization_timestamp", "")

                if sid and rtc:
                    yield (str(sid), uptime, str(rtc), str(init_ts_raw))

            proc.wait(timeout=30)
        except (subprocess.TimeoutExpired, FileNotFoundError):
            # grep not available or timed out — fallback to Python
            with open(filepath, "r", encoding="utf-8") as f:
                for line in f:
                    if "RTC_CONNECTED" not in line and "RTC_DISCONNECTED" not in line:
                        continue
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        ev = json.loads(line)
                    except Exception:
                        continue
                    rtc = ev.get("client_rtc_state")
                    sid = ev.get("client_heartbeat_session_id")
                    uptime = int(ev.get("uptime_process_renderer", 0))
                    init_ts_raw = ev.get("client_heartbeat_initialization_timestamp", "")
                    if sid and rtc:
                        yield (str(sid), uptime, str(rtc), str(init_ts_raw))

        if progress_callback:
            progress_callback(fi + 1, total_files)


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

    import sys
    print(f"\n  Found {total_rtc_events} RTC events across {len(sessions_events)} sessions.", file=sys.stderr)

    voice_sessions: List[VoiceSession] = []
    session_count = len(sessions_events)

    for idx, (sid, events) in enumerate(sessions_events.items()):
        if progress_callback and idx % 100 == 0:
            print(f"\r  Processing sessions... {idx}/{session_count}", end="", file=sys.stderr)

        init_ts_raw = sessions_init_ts.get(sid)
        if not init_ts_raw:
            continue
        init_dt = _parse_ts(init_ts_raw)
        if init_dt is None:
            continue

        events.sort(key=lambda x: x[0])

        start_uptime = None
        for uptime, rtc in events:
            if rtc == "RTC_CONNECTED" and start_uptime is None:
                start_uptime = uptime
            elif rtc != "RTC_CONNECTED" and start_uptime is not None:
                duration = uptime - start_uptime
                if duration >= min_duration_seconds:
                    voice_sessions.append(
                        VoiceSession(
                            start=init_dt + timedelta(seconds=start_uptime),
                            end=init_dt + timedelta(seconds=uptime),
                            duration_seconds=duration,
                        )
                    )
                start_uptime = None

        if start_uptime is not None and events:
            last_uptime = events[-1][0]
            duration = last_uptime - start_uptime
            if duration >= min_duration_seconds:
                voice_sessions.append(
                    VoiceSession(
                        start=init_dt + timedelta(seconds=start_uptime),
                        end=init_dt + timedelta(seconds=last_uptime),
                        duration_seconds=duration,
                    )
                )

    if progress_callback:
        print("", file=sys.stderr)

    voice_sessions.sort(key=lambda s: s.start)
    return voice_sessions


def voice_summary(export_dir: Path) -> dict:
    """Voice activity summary. Uses grep streaming for large files."""
    import sys

    activity_dir = export_dir / "Aktivität"
    if not activity_dir.exists():
        return {"total_sessions": 0, "total_duration_seconds": 0, "error": "No Aktivität directory"}

    def progress(current: int, total: int):
        pct = current / total * 100 if total else 0
        print(f"\r  Scanning files... {current}/{total} ({pct:.0f}%)", end="", file=sys.stderr)

    print("  Scanning voice activity via grep...", file=sys.stderr)
    sessions = detect_voice_sessions(activity_dir, progress_callback=progress)
    print("", file=sys.stderr)

    if not sessions:
        return {
            "total_sessions": 0,
            "total_duration_seconds": 0,
            "total_duration_formatted": "0h 0m",
            "average_duration_seconds": 0,
            "longest_session_seconds": 0,
            "sessions_by_day": {},
            "sessions": [],
        }

    total_duration = sum(s.duration_seconds for s in sessions)
    avg_duration = total_duration / len(sessions) if sessions else 0
    longest = max(s.duration_seconds for s in sessions) if sessions else 0

    from collections import Counter
    by_day = Counter(s.start.strftime("%Y-%m-%d") for s in sessions)

    hours = int(total_duration // 3600)
    minutes = int((total_duration % 3600) // 60)

    return {
        "total_sessions": len(sessions),
        "total_duration_seconds": int(total_duration),
        "total_duration_formatted": f"{hours}h {minutes}m",
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
    }
