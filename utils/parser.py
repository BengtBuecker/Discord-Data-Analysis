"""Data access layer for Discord export files."""

import json
import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Iterator, Any


def load_json(path: Path) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_json_lines(path: Path) -> Iterator[dict]:
    """Parse newline-delimited JSON file. Each line is a complete JSON object."""
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def load_user(export_dir: Path) -> dict:
    """Load the account user.json to get the data owner's ID."""
    return load_json(export_dir / "Account" / "user.json")


def load_index(export_dir: Path) -> Dict[str, str]:
    """Load Nachrichten/index.json mapping channel IDs to readable names."""
    return load_json(export_dir / "Nachrichten" / "index.json")


def load_server_index(export_dir: Path) -> Dict[str, str]:
    """Load Server/index.json mapping guild IDs to server names."""
    return load_json(export_dir / "Server" / "index.json")


def load_channel_info(channel_dir: Path) -> dict:
    """Load channel.json from a channel directory."""
    return load_json(channel_dir / "channel.json")


def load_messages(channel_dir: Path) -> list[dict]:
    """Load messages.json (JSON array) from a channel directory."""
    return load_json(channel_dir / "messages.json")


def iter_message_channels(messages_dir: Path) -> Iterator[Path]:
    """Yield all channel directories in the messages folder."""
    for entry in sorted(messages_dir.iterdir()):
        if entry.is_dir() and (entry / "messages.json").exists():
            yield entry


def dirname_to_channel_id(dirname: str) -> str:
    """Strip 'c' prefix from directory name to get channel ID."""
    if dirname.startswith("c"):
        return dirname[1:]
    return dirname


def iter_analytics_files(activity_dir: Path) -> list[Path]:
    """Find all analytics JSONL files in the Aktivität folder structure."""
    files = []
    if not activity_dir.exists():
        return files
    for root, _dirs, filenames in os.walk(activity_dir):
        for fname in filenames:
            if fname.endswith(".json"):
                files.append(Path(root) / fname)
    return sorted(files)


DM_CHANNEL_RE = re.compile(r"^Direct Message with (.+?)(?:#\d+)?$")


def extract_dm_username(channel_name: str) -> Optional[str]:
    """Extract username from a DM channel name like 'Direct Message with username#0'."""
    m = DM_CHANNEL_RE.match(channel_name)
    if m:
        return m.group(1)
    return None


def categorize_channels(index: dict, server_index: dict) -> Dict[str, list]:
    """
    Categorize channels by type:
    - dm_users: map username -> [channel_ids]
    - guild_channels: map guild_name -> [channel_ids]
    - unknown: [channel_ids that don't match any pattern]
    """
    dm_users: Dict[str, list] = {}
    guild_channels: Dict[str, list] = {}
    unknown: list = []

    for channel_id, channel_name in index.items():
        username = extract_dm_username(channel_name)
        if username:
            dm_users.setdefault(username, []).append(channel_id)
        else:
            # Try to parse "ChannelName in ServerName" or "ChannelName"
            if " in " in channel_name:
                parts = channel_name.rsplit(" in ", 1)
                server_name = parts[1]
                guild_channels.setdefault(server_name, []).append(channel_id)
            else:
                unknown.append(channel_id)

    return {"dm_users": dm_users, "guild_channels": guild_channels, "unknown": unknown}
