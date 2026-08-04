"""Message analysis: counts per DM user, server, channel, and timeline."""

from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

from utils.parser import (
    load_index,
    load_server_index,
    load_messages,
    iter_message_channels,
    extract_dm_username,
    dirname_to_channel_id,
)


def count_messages_by_dm_user(export_dir: Path) -> List[Tuple[str, int]]:
    """Count total messages per DM user, sorted descending by count."""
    index = load_index(export_dir)
    messages_dir = export_dir / "Nachrichten"

    user_counts: Dict[str, int] = defaultdict(int)

    for channel_dir in iter_message_channels(messages_dir):
        channel_id = dirname_to_channel_id(channel_dir.name)
        channel_name = index.get(channel_id, "Unknown")
        username = extract_dm_username(channel_name)
        if username is None:
            continue

        messages = load_messages(channel_dir)
        user_counts[username] += len(messages)

    return sorted(user_counts.items(), key=lambda x: x[1], reverse=True)


def count_messages_by_server(export_dir: Path) -> List[Tuple[str, int]]:
    """Count total messages per server/guild, sorted descending by count."""
    index = load_index(export_dir)
    server_index = load_server_index(export_dir)
    messages_dir = export_dir / "Nachrichten"

    server_counts: Dict[str, int] = defaultdict(int)

    for channel_dir in iter_message_channels(messages_dir):
        channel_id = dirname_to_channel_id(channel_dir.name)
        channel_name = index.get(channel_id, "Unknown")

        if extract_dm_username(channel_name) is not None:
            continue  # Skip DMs

        if " in " in channel_name:
            guild_slug = channel_name.rsplit(" in ", 1)[1]
            server_counts[guild_slug] += len(load_messages(channel_dir))
        else:
            # Try to match via channel.json guild info
            from utils.parser import load_channel_info

            try:
                info = load_channel_info(channel_dir)
                guild = info.get("guild")
                if guild and isinstance(guild, dict):
                    guild_name = guild.get("name", "Unknown")
                    server_counts[guild_name] += len(load_messages(channel_dir))
                else:
                    server_counts["Unknown"] += len(load_messages(channel_dir))
            except Exception:
                server_counts["Unknown"] += len(load_messages(channel_dir))

    return sorted(server_counts.items(), key=lambda x: x[1], reverse=True)


def count_messages_by_channel(export_dir: Path) -> List[Tuple[str, str, int]]:
    """Count messages per channel, returns (channel_id, channel_name, count)."""
    index = load_index(export_dir)
    messages_dir = export_dir / "Nachrichten"

    results = []
    for channel_dir in iter_message_channels(messages_dir):
        channel_id = dirname_to_channel_id(channel_dir.name)
        channel_name = index.get(channel_id, "Unknown")
        messages = load_messages(channel_dir)
        results.append((channel_id, channel_name, len(messages)))

    return sorted(results, key=lambda x: x[2], reverse=True)


def _parse_timestamp(ts: str) -> datetime:
    """Parse 'YYYY-MM-DD HH:MM:SS' to datetime."""
    try:
        return datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None


def message_timeline(export_dir: Path, granularity: str = "month") -> Dict[str, int]:
    """
    Aggregate messages over time.
    granularity: 'day', 'month', 'year'
    Returns dict of period -> count sorted chronologically.
    """
    messages_dir = export_dir / "Nachrichten"
    counts: Dict[str, int] = defaultdict(int)

    fmt = {"day": "%Y-%m-%d", "month": "%Y-%m", "year": "%Y"}.get(granularity, "%Y-%m")

    for channel_dir in iter_message_channels(messages_dir):
        messages = load_messages(channel_dir)
        for msg in messages:
            ts = msg.get("Timestamp", "")
            if ts:
                dt = _parse_timestamp(ts)
                if dt:
                    key = dt.strftime(fmt)
                    counts[key] += 1

    return dict(sorted(counts.items()))


def message_summary(export_dir: Path) -> dict:
    """Return a complete message summary with all stats."""
    dm = count_messages_by_dm_user(export_dir)
    server = count_messages_by_server(export_dir)
    total = sum(c for _, c in dm) + sum(c for _, c in server)
    return {
        "total_messages": total,
        "dm_users": dm,
        "servers": server,
        "dm_total": sum(c for _, c in dm),
        "server_total": sum(c for _, c in server),
    }
