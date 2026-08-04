"""Shared test fixtures — mock Discord GDPR export data."""

import json
import shutil
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def mock_export_dir():
    tmp = Path(tempfile.mkdtemp(prefix="test_discord_export_"))

    (tmp / "Account").mkdir(parents=True)
    (tmp / "Account" / "user.json").write_text(json.dumps({
        "id": "123456789012345678", "username": "testuser",
    }))

    (tmp / "Nachrichten").mkdir(parents=True)

    # index.json: channel ID -> human-readable name
    index = {
        "12345": "Direct Message with Alice#1234",
        "67890": "Direct Message with Bob#5678",
        "99999": "general in MyServer",
        "88888": "memes in MyServer",
        "77777": "Unknown channel",
    }
    (tmp / "Nachrichten" / "index.json").write_text(json.dumps(index))

    def _mk_channel(cid, messages):
        d = tmp / "Nachrichten" / f"c{cid}"
        d.mkdir(parents=True)
        (d / "channel.json").write_text(json.dumps({
            "id": cid, "type": 0,
            "guild": {"id": "111", "name": "MyServer"} if int(cid) > 70000 else None,
        }))
        (d / "messages.json").write_text(json.dumps(messages))

    _mk_channel("12345", [
        {"ID": "1", "Timestamp": "2024-01-15 10:00:00",
         "Contents": "Hello Alice", "Attachments": ""},
        {"ID": "2", "Timestamp": "2024-01-15 10:05:00",
         "Contents": "Hi back", "Attachments": ""},
        {"ID": "3", "Timestamp": "2024-02-01 12:00:00",
         "Contents": "How are you?", "Attachments": ""},
        {"ID": "4", "Timestamp": "2024-12-25 20:00:00",
         "Contents": "Merry Christmas!", "Attachments": ""},
        {"ID": "5", "Timestamp": "2025-06-15 15:30:00",
         "Contents": "Summer plans?", "Attachments": ""},
    ])

    _mk_channel("67890", [
        {"ID": "6", "Timestamp": "2024-03-10 09:00:00",
         "Contents": "Hey Bob", "Attachments": "image.png"},
        {"ID": "7", "Timestamp": "2024-03-10 09:01:00",
         "Contents": "Yo", "Attachments": ""},
        {"ID": "8", "Timestamp": "2025-01-01 00:00:00",
         "Contents": "Happy New Year!", "Attachments": ""},
    ])

    _mk_channel("99999", [])
    _mk_channel("77777", [
        {"ID": "10", "Timestamp": "2024-05-05 14:00:00",
         "Contents": "Unknown destination", "Attachments": ""},
    ])
    (tmp / "Nachrichten" / "c77777" / "channel.json").write_text(json.dumps({"id": "77777", "type": 0}))

    # Count: Alice=5, Bob=3, Unknown channel (77777)=1, general in MyServer=0, total=9
    # DM total=6, Server total=1 (Unknown maps by _server_name), total=7... wait
    # Actually "Unknown channel" has channel.json with guild=None
    # _server_name for "Unknown channel" → "Unknown" (no " in ")
    # So 77777 counts as server with name "Unknown"
    # Actually let me trace: 12345 → DM (Alice#1234 → Alice), 67890 → DM (Bob#5678 → Bob)
    # 99999 → Server (general in MyServer → MyServer), 0 messages
    # 77777 → "Unknown channel" → no " in " → channel.json has no guild → "Unknown"

    (tmp / "Aktivität").mkdir(parents=True)
    (tmp / "Aktivität" / "analytics").mkdir(parents=True)
    (tmp / "Aktivität" / "tns").mkdir(parents=True)
    (tmp / "Aktivität" / "reporting").mkdir(parents=True)
    (tmp / "Aktivität" / "modeling").mkdir(parents=True)

    rtc_events = [
        {"client_heartbeat_session_id": "ses_001",
         "uptime_process_renderer": 0,
         "client_rtc_state": "RTC_CONNECTED",
         "client_heartbeat_initialization_timestamp": "2024-06-01 12:00:00"},
        {"client_heartbeat_session_id": "ses_001",
         "uptime_process_renderer": 3600,
         "client_rtc_state": "RTC_CONNECTED",
         "client_heartbeat_initialization_timestamp": "2024-06-01 12:00:00"},
        {"client_heartbeat_session_id": "ses_001",
         "uptime_process_renderer": 7200,
         "client_rtc_state": "RTC_DISCONNECTED",
         "client_heartbeat_initialization_timestamp": "2024-06-01 12:00:00"},
        {"client_heartbeat_session_id": "ses_002",
         "uptime_process_renderer": 100,
         "client_rtc_state": "RTC_CONNECTED",
         "client_heartbeat_initialization_timestamp": "2024-06-02 08:00:00"},
        {"client_heartbeat_session_id": "ses_002",
         "uptime_process_renderer": 200,
         "client_rtc_state": "RTC_DISCONNECTED",
         "client_heartbeat_initialization_timestamp": "2024-06-02 08:00:00"},
        {"client_heartbeat_session_id": "ses_003",
         "uptime_process_renderer": 50,
         "client_rtc_state": "RTC_NO_CONNECTION",
         "client_heartbeat_initialization_timestamp": "2024-06-03 10:00:00"},
    ]
    with open(tmp / "Aktivität" / "analytics" / "events-0.json", "w") as f:
        for ev in rtc_events:
            f.write(json.dumps(ev) + "\n")

    leave_events = [
        {"channel_id": "12345", "guild_id": "", "duration": 1800000, "timestamp": "2024-06-01 12:30:00", "action": "leave_voice_channel"},
        {"channel_id": "12345", "guild_id": "", "duration": 900000, "timestamp": "2024-06-01 13:00:00", "action": "leave_voice_channel"},
        {"channel_id": "99999", "guild_id": "111", "duration": 3600000, "timestamp": "2024-06-01 14:00:00", "action": "leave_voice_channel"},
    ]
    with open(tmp / "Aktivität" / "tns" / "events-0.json", "w") as f:
        for ev in leave_events:
            f.write(json.dumps(ev) + "\n")

    return tmp


@pytest.fixture(autouse=True)
def cleanup_export_dir(mock_export_dir):
    yield
    shutil.rmtree(mock_export_dir, ignore_errors=True)


@pytest.fixture
def mock_zip_path(mock_export_dir):
    """Create a temporary ZIP from the mock export data."""
    zip_path = mock_export_dir.parent / "test_export.zip"
    # Don't actually create ZIP here — tests that need it will create it
    return zip_path
