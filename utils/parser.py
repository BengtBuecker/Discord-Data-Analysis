"""Data access layer for Discord export files."""

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional


def load_json(path: Path) -> Any:
    """Load and parse a JSON file."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_index(export_dir: Path) -> Dict[str, str]:
    """Load Nachrichten/index.json mapping channel IDs to readable names."""
    return load_json(export_dir / "Nachrichten" / "index.json")


def load_channel_info(channel_dir: Path) -> dict:
    """Load channel.json from a channel directory."""
    return load_json(channel_dir / "channel.json")


def load_messages(channel_dir: Path) -> List[dict]:
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


def iter_analytics_files(activity_dir: Path) -> List[Path]:
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
