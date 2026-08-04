<p align="center">
  <img src="https://img.shields.io/badge/python-3.9+-blue.svg" alt="Python 3.9+">
  <img src="https://img.shields.io/badge/dependencies-pywebview-blue.svg" alt="PyWebView">
  <img src="https://img.shields.io/badge/privacy-local-9cf.svg" alt="100% Local">
  <img src="https://img.shields.io/badge/desktop-GUI-89b4fa.svg" alt="Desktop GUI">
</p>

<h1 align="center">🔍 Discord Data Analyzer</h1>
<p align="center"><em>Turn your Discord GDPR export into readable insights — messages, voice calls, servers.</em></p>
<p align="center"><strong>Zero dependencies. 100% local. Your data never leaves your machine.</strong></p>

---

## ✨ Features

| Category | What You Get |
|---|---|
| 🖥️ **Desktop App** | Native window — drop your ZIP, get the full report. No terminal needed. |
| 💬 **Messages** | DM users, servers, channels, timeline (day/month/year) |
| 📞 **Voice Calls** | Total duration, per-user breakdown, per-channel sessions, daily stats |
| 📊 **Full Report** | Everything above in a single command |

### Voice Call Breakdown

The `voice` command now shows **who you actually talked to**, not just total airtime:

- **DM Call Duration by User** — ranked list of every person you called, with total hours and call count
- **Server Voice Channel Duration** — per-channel time across every server
- **Other Voice Channels** — channels from servers you've since left

```
DM Call Duration by User:
  thvndabolt           378h 35m  (356 calls)
  ollicorn             210h 51m  (328 calls)
  herrgrimel           100h 43m  (69 calls)
  ...
```

---

## 🚀 Quick Start

### Desktop App (Windows)

[Download the latest `Discord-Data-Analyzer.exe`](https://github.com/BengtBuecker/Discord-Data-Analysis/releases) from Releases, double-click, drop your ZIP. That's it.

Or run from source:

```bash
pip install pywebview
python main.py
```

### Command Line

```bash
git clone https://github.com/BengtBuecker/Discord-Data-Analysis
cd Discord-Data-Analysis
python analyzer.py --dir "path/to/discord/export" all
```

> **Prerequisites**: Python 3.9+, `pip install pywebview` for the desktop GUI. The CLI analyzer (`python analyzer.py`) uses stdlib only — zero dependencies.

### Build Your Own .exe

```bash
pip install pyinstaller pywebview
pyinstaller --onefile --windowed --name "Discord-Data-Analyzer" main.py
# → dist/Discord-Data-Analyzer.exe
```

The [GitHub Actions workflow](.github/workflows/build-exe.yml) also auto-builds a Windows `.exe` on every tagged release.

---

## 📋 Commands

| Command | What It Shows |
|---|---|
| `messages-dm` | Most-messaged DM contacts, ranked |
| `messages-server` | Message volume per server |
| `messages-channel` | Detailed per-channel counts |
| `messages-timeline` | Activity over time |
| `voice` | Call duration by user, channel & day |
| `all` | Everything at once |

### `messages-timeline` Options

```bash
python analyzer.py --dir "DC Daten" messages-timeline --granularity month  # default
python analyzer.py --dir "DC Daten" messages-timeline --granularity day
python analyzer.py --dir "DC Daten" messages-timeline --granularity year
```

### Example Output (`voice`)

```
============================================================
  Voice Call Analysis
============================================================
  Total sessions:       570
  Total voice time:     1231h 52m (4434771s)
  Average session:      129m 40s
  Longest session:      941m 18s

  Sessions per day:
    2026-07-22   1  █
    2026-07-21   2  ██
    2026-07-20   2  ██
    ...

  DM Call Duration by User:
    thvndabolt           378h 35m  (356 calls)
    ollicorn             210h 51m  (328 calls)
    ...

  Server Voice Channel Duration:
    Gaming in delete riot pls       866h 6m  (908 sessions)
    goon corner in Precise Gunplay  619h 9m  (472 sessions)
    ...

  Recent sessions:
    2026-07-22 17:43:15 — 247.8min
    2026-07-21 20:47:33 — 149.7min
```

---

## 🧠 How It Works

### Messages

Reads `Nachrichten/index.json` to map channel IDs to readable names, then loads each channel's `messages.json` to count messages. DM channels are detected by the `"Direct Message with username#0"` naming pattern.

### Voice Calls

Two data sources are combined for comprehensive analysis:

| Source | What It Provides |
|---|---|
| `Aktivität/analytics/` | RTC heartbeat events → total session count & duration |
| `Aktivität/tns/` | `leave_voice_channel` events → per-channel/user breakdown |

Voice sessions are detected from `client_rtc_state: "RTC_CONNECTED"` heartbeat transitions in analytics events. Per-user call durations come from `leave_voice_channel` events which record the channel ID and duration (in milliseconds) each time a voice channel is left.

Channel IDs are resolved to human-readable names via `Nachrichten/index.json`:
- **DM channels** → username (stripped from `"Direct Message with username#0"`)
- **Server channels** → `"ChannelName in ServerName"`
- **Unknown** → `#channel_id` (e.g., channels from servers you've left)

Large analytics files (4GB+) are handled via `grep` pre-filtering to keep memory usage low.

---

## 🔒 Privacy

- **No data leaves your machine** — all analysis runs locally
- **No external dependencies** — stdlib-only, nothing to install
- **No telemetry, no tracking** — the repo contains only analyzer code

---

## 📁 Expected Data Format

This tool works with a standard [Discord Data Package](https://support.discord.com/hc/articles/360004957991).

```
your-export/
├── Account/
│   └── user.json
├── Aktivität/
│   ├── analytics/          ← RTC heartbeats (total session detection)
│   │   └── events-*.json
│   ├── tns/                ← leave_voice_channel events (per-user duration)
│   │   └── events-*.json
│   ├── reporting/
│   │   └── events-*.json
│   └── modeling/
│       └── events-*.json
├── Nachrichten/
│   ├── index.json          ← channel ID → name mapping
│   └── c<channel_id>/
│       ├── channel.json
│       └── messages.json
└── Server/
    └── index.json          ← guild ID → server name mapping
```
