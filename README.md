# Discord Data Analyzer

CLI tool to analyze Discord GDPR data exports. Parse your exported JSON files to get insights about messages, voice calls, and server activity — all locally, no data leaves your machine.

## Features

- **Messages by DM user** — who you chat with most
- **Messages by server** — which communities you're active in
- **Messages by channel** — per-channel breakdown
- **Message timeline** — activity over days, months, or years
- **Voice call analysis** — session count, total duration, per-day breakdown
- **Full report** — all of the above in one command

## Requirements

- Python 3.9+
- No external dependencies (stdlib only)

## Usage

```bash
# Clone and enter the repo
cd discord-analyzer

# Point at your Discord data export directory
python analyzer.py --dir "path/to/your/discord/export" <command>
```

### Commands

| Command | Description |
|---|---|
| `messages-dm` | Message count per DM user, sorted by volume |
| `messages-server` | Message count per server/guild |
| `messages-channel` | Message count per channel |
| `messages-timeline` | Message count over time (`--granularity day|month|year`) |
| `voice` | Voice call sessions, total duration, daily breakdown |
| `all` | Full report (messages + voice) |

### Examples

```bash
# Who do I message most?
python analyzer.py --dir "DC Daten" messages-dm

# How much did I talk in voice calls?
python analyzer.py --dir "DC Daten" voice

# Full analysis
python analyzer.py --dir "DC Daten" all

# Message timeline by day
python analyzer.py --dir "DC Daten" messages-timeline --granularity day
```

## How It Works

### Messages
Reads `Nachrichten/index.json` to map channel IDs to names, then loads each channel's `messages.json` to count messages. DM channels are identified by the `"Direct Message with username#0"` naming pattern.

### Voice Calls
Parses the `Aktivität/analytics/` directory for Discord client heartbeat events. Voice sessions are detected from `client_rtc_state: "RTC_CONNECTED"` transitions. Uses `grep` pre-filtering for large (4GB+) analytics files to avoid loading everything into memory.

## Privacy

All analysis runs locally. No data is uploaded anywhere. The Git repo contains only the analyzer code — not your Discord data.

## Data Format

This tool expects a standard [Discord data package](https://support.discord.com/hc/articles/360004957991) structure:

```
your-export/
├── Account/
│   └── user.json
├── Aktivität/
│   └── analytics/
│       └── events-*.json
├── Nachrichten/
│   ├── index.json
│   └── c<channel_id>/
│       ├── channel.json
│       └── messages.json
└── Server/
    └── index.json
```
