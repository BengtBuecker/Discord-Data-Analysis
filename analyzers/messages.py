"""Message analysis: counts per DM user, server, channel, and timeline."""

from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Tuple

from utils.parser import (
    load_index,
    load_channel_info,
    load_messages,
    iter_message_channels,
    extract_dm_username,
    dirname_to_channel_id,
)


def _channel_entries(export_dir: Path) -> Iterator[Tuple[Path, str, str, list]]:
    """Yield (channel_dir, channel_id, channel_name, messages) once per channel.

    Skips channels whose messages.json or channel.json cannot be parsed.
    """
    try:
        index = load_index(export_dir)
    except (OSError, ValueError):
        index = {}
    for channel_dir in iter_message_channels(export_dir / "Nachrichten"):
        channel_id = dirname_to_channel_id(channel_dir.name)
        channel_name = index.get(channel_id, "Unknown")
        try:
            messages = load_messages(channel_dir)
        except (OSError, ValueError):
            continue
        yield channel_dir, channel_id, channel_name, messages


def _server_name(channel_dir: Path, channel_name: str) -> str:
    """Resolve server name from the index name, falling back to channel.json."""
    if " in " in channel_name:
        return channel_name.rsplit(" in ", 1)[1]
    try:
        info = load_channel_info(channel_dir)
    except (OSError, ValueError):
        return "Unknown"  # channel.json missing or contains invalid JSON
    guild = info.get("guild") if isinstance(info, dict) else None
    if isinstance(guild, dict):
        return guild.get("name", "Unknown")
    return "Unknown"


def count_messages_by_dm_user(export_dir: Path) -> List[Tuple[str, int]]:
    """Count total messages per DM user, sorted descending by count."""
    user_counts: Dict[str, int] = defaultdict(int)
    for _dir, _id, name, messages in _channel_entries(export_dir):
        username = extract_dm_username(name)
        if username is not None:
            user_counts[username] += len(messages)
    return sorted(user_counts.items(), key=lambda x: x[1], reverse=True)


def count_messages_by_server(export_dir: Path) -> List[Tuple[str, int]]:
    """Count total messages per server/guild, sorted descending by count."""
    server_counts: Dict[str, int] = defaultdict(int)
    for channel_dir, _id, name, messages in _channel_entries(export_dir):
        if extract_dm_username(name) is not None:
            continue  # Skip DMs
        server_counts[_server_name(channel_dir, name)] += len(messages)
    return sorted(server_counts.items(), key=lambda x: x[1], reverse=True)


def count_messages_by_channel(export_dir: Path) -> List[Tuple[str, str, int]]:
    """Count messages per channel, returns (channel_id, channel_name, count)."""
    results = [
        (channel_id, name, len(messages))
        for _dir, channel_id, name, messages in _channel_entries(export_dir)
    ]
    return sorted(results, key=lambda x: x[2], reverse=True)


def _parse_timestamp(ts: str) -> Optional[datetime]:
    """Parse 'YYYY-MM-DD HH:MM:SS' to datetime."""
    try:
        return datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None


_GRANULARITY_FORMATS = {"day": "%Y-%m-%d", "month": "%Y-%m", "year": "%Y"}


def _granularity_format(granularity: str) -> str:
    """Map a granularity name to its strftime format, defaulting to month."""
    return _GRANULARITY_FORMATS.get(granularity, "%Y-%m")


def _timeline_key(ts: str, fmt: str) -> Optional[str]:
    dt = _parse_timestamp(ts)
    return dt.strftime(fmt) if dt else None


def message_timeline(export_dir: Path, granularity: str = "month") -> Dict[str, int]:
    """
    Aggregate messages over time.
    granularity: 'day', 'month', 'year'
    Returns dict of period -> count sorted chronologically.
    """
    fmt = _granularity_format(granularity)
    counts: Dict[str, int] = defaultdict(int)
    for _dir, _id, _name, messages in _channel_entries(export_dir):
        for msg in messages:
            key = _timeline_key(msg.get("Timestamp", ""), fmt)
            if key:
                counts[key] += 1
    return dict(sorted(counts.items()))


def full_summary(export_dir: Path, granularity: str = "month") -> dict:
    """All message stats in a single pass over the export.

    Also returns a ``per_month`` breakdown so the frontend can drill down
    into a single month and show per-contact / per-server stats for it.
    """
    fmt = _granularity_format(granularity)

    user_counts: Dict[str, int] = defaultdict(int)
    server_counts: Dict[str, int] = defaultdict(int)
    channels: List[Tuple[str, str, int]] = []
    timeline: Dict[str, int] = defaultdict(int)

    # ── per-month breakdown: { month: { "dm_users": {user: count}, "servers": {server: count} } }
    per_month_dm: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    per_month_server: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    per_month_days: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    day_fmt = "%Y-%m-%d"

    for channel_dir, channel_id, name, messages in _channel_entries(export_dir):
        count = len(messages)
        channels.append((channel_id, name, count))

        username = extract_dm_username(name)
        is_dm = username is not None
        if is_dm:
            user_counts[username] += count
        else:
            server_name = _server_name(channel_dir, name)
            server_counts[server_name] += count

        for msg in messages:
            key = _timeline_key(msg.get("Timestamp", ""), fmt)
            if key:
                timeline[key] += 1
                if is_dm:
                    per_month_dm[key][username] += 1
                else:
                    per_month_server[key][server_name] += 1
                day_key = _timeline_key(msg.get("Timestamp", ""), day_fmt)
                if day_key:
                    per_month_days[key][day_key] += 1

    dm_users = sorted(user_counts.items(), key=lambda x: x[1], reverse=True)
    servers = sorted(server_counts.items(), key=lambda x: x[1], reverse=True)
    dm_total = sum(user_counts.values())
    server_total = sum(server_counts.values())

    # Post-process per_month: convert inner dicts to sorted lists
    per_month: Dict[str, dict] = {}
    all_months = set(per_month_dm.keys()) | set(per_month_server.keys())
    for month in sorted(all_months):
        dm_sorted = sorted(per_month_dm[month].items(), key=lambda x: x[1], reverse=True)
        sv_sorted = sorted(per_month_server[month].items(), key=lambda x: x[1], reverse=True)
        per_month[month] = {
            "dm_users": dm_sorted,
            "servers": sv_sorted,
            "total": sum(v for _, v in dm_sorted) + sum(v for _, v in sv_sorted),
            "days": dict(sorted(per_month_days.get(month, {}).items())),
        }

    return {
        "total_messages": dm_total + server_total,
        "dm_total": dm_total,
        "server_total": server_total,
        "dm_users": dm_users,
        "servers": servers,
        "channels": sorted(channels, key=lambda x: x[2], reverse=True),
        "timeline": dict(sorted(timeline.items())),
        "per_month": per_month,
    }


def message_summary(export_dir: Path) -> dict:
    """Message totals with per-user and per-server breakdowns."""
    s = full_summary(export_dir)
    return {k: s[k] for k in
            ("total_messages", "dm_total", "server_total", "dm_users", "servers")}
