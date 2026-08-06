"""Python-JS bridge for pywebview Discord Analyzer."""

import json
import os
import re
import sys
import tempfile
import urllib.request
import zipfile
import shutil
from datetime import datetime
from pathlib import Path

ANALYZER_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(ANALYZER_DIR))

from analyzers.messages import full_summary
from analyzers.voice import voice_summary
from utils.formatting import format_hours_minutes

VERSION = "2.1.0"

_RELEASES_URL = "https://api.github.com/repos/BengtBuecker/Discord-Personal-Data-Analysis/releases/latest"


class AnalyzerApi:
    """Exposed to JavaScript via pywebview's js_api mechanism."""

    _ACCOUNT_USERNAME_CACHE = None

    def __init__(self):
        self._export_dir = None

    def selectFile(self) -> str:
        """Open native file dialog. Uses tkinter directly — no subprocess."""
        import tkinter as tk
        from tkinter import filedialog

        try:
            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            path = filedialog.askopenfilename(
                title="Select Discord Data ZIP",
                filetypes=[("ZIP files", "*.zip"), ("All files", "*.*")],
            )
            root.destroy()
            return path or ""
        except Exception:
            return ""

    def _push_progress(self, phase: str) -> None:
        """Push a progress update to the JS frontend. No-op if webview
        is unavailable or no window is open (e.g. under pytest)."""
        try:
            import webview
            _has_webview = True
        except ImportError:
            _has_webview = False

        if not _has_webview:
            return
        if not webview.windows:
            return
        webview.windows[0].evaluate_js(f"updateProgress('{phase}')")

    def analyzeZip(self, zip_path: str) -> dict:
        path = Path(zip_path)
        if path.suffix.lower() != ".zip" or not path.exists():
            return {"error": "Invalid ZIP file"}

        extract_dir = Path(tempfile.mkdtemp(prefix="discord_export_"))
        try:
            self._push_progress("Extracting ZIP...")
            with zipfile.ZipFile(path, "r") as zf:
                zf.extractall(extract_dir)
        except (zipfile.BadZipFile, OSError) as e:
            shutil.rmtree(extract_dir, ignore_errors=True)
            return {"error": f"Invalid ZIP: {e}"}

        export_dir = self._find_export_root(extract_dir)
        try:
            self._push_progress("Analyzing messages...")
            msg = full_summary(export_dir)
            self._push_progress("Analyzing voice...")
            voice = voice_summary(export_dir)
        except Exception as e:
            shutil.rmtree(extract_dir, ignore_errors=True)
            return {"error": f"Analysis failed: {e}"}

        shutil.rmtree(extract_dir, ignore_errors=True)

        username = self._extract_username(export_dir)
        self._ACCOUNT_USERNAME_CACHE = username

        self._push_progress("Building dashboard...")
        return {
            "msg": {
                "total_messages": msg["total_messages"],
                "dm_total": msg["dm_total"],
                "server_total": msg["server_total"],
            },
            "dm_users": msg["dm_users"],
            "servers": msg["servers"],
            "timeline": msg["timeline"],
            "per_month": msg.get("per_month", {}),
            "voice": {
                "total_sessions": voice.get("total_sessions", 0),
                "total_duration_formatted": voice.get("total_duration_formatted", "0h 0m"),
                "total_duration_seconds": voice.get("total_duration_seconds", 0),
                "channel_durations": voice.get("channel_durations", []),
            },
            "account": {"username": username},
        }

    def _extract_username(self, export_dir: Path) -> str | None:
        """Read the account username from `Account/user.json`, if present."""
        user_json_path = export_dir / "Account" / "user.json"
        if not user_json_path.exists():
            return None
        try:
            with open(user_json_path, "r", encoding="utf-8") as f:
                account_data = json.load(f)
            return account_data.get("username")
        except (json.JSONDecodeError, OSError):
            return None

    def _find_export_root(self, extract_dir: Path) -> Path:
        if (extract_dir / "Account").exists():
            return extract_dir
        for child in extract_dir.iterdir():
            if child.is_dir() and (child / "Account").exists():
                return child
        return extract_dir

    def saveAnalysis(self, data: dict) -> bool:
        """Persist the last analysis result for auto-restore on next launch,
        and additionally keep a dated copy in the per-user analyses history."""
        appdata = os.getenv("APPDATA")
        if not appdata:
            return False
        save_dir = Path(appdata) / "Discord-Personal-Data-Analyzer"
        try:
            save_dir.mkdir(parents=True, exist_ok=True)
            with open(save_dir / "last-analysis.json", "w", encoding="utf-8") as f:
                json.dump(data, f)
        except OSError:
            return False

        try:
            self._save_to_history(save_dir, data)
        except OSError:
            pass  # history is best-effort; last-analysis.json already saved

        return True

    def _save_to_history(self, save_dir: Path, data: dict) -> None:
        analyses_dir = save_dir / "analyses"
        analyses_dir.mkdir(parents=True, exist_ok=True)

        username = (
            (data.get("account") or {}).get("username")
            or self._ACCOUNT_USERNAME_CACHE
            or "user"
        )
        safe_username = re.sub(r"[^A-Za-z0-9_-]", "_", username) or "user"
        date_str = datetime.now().strftime("%Y-%m-%d")
        filename = f"{safe_username}_{date_str}.json"

        with open(analyses_dir / filename, "w", encoding="utf-8") as f:
            json.dump(data, f)

    def getSavedAnalysis(self) -> dict | None:
        """Load the last persisted analysis, if any."""
        appdata = os.getenv("APPDATA")
        if not appdata:
            return None
        save_path = Path(appdata) / "Discord-Personal-Data-Analyzer" / "last-analysis.json"
        if not save_path.exists():
            return None
        try:
            with open(save_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            print(f"[WARN] Corrupted saved analysis: {e}", file=sys.stderr)
            return None

    def listSavedAnalyses(self) -> list:
        """List past analyses from the analyses/ history directory, each
        named by Discord username + save date, newest first."""
        appdata = os.getenv("APPDATA")
        if not appdata:
            return []
        analyses_dir = Path(appdata) / "Discord-Personal-Data-Analyzer" / "analyses"
        if not analyses_dir.exists():
            return []

        results = []
        for path in analyses_dir.glob("*.json"):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except (json.JSONDecodeError, OSError):
                continue

            username = (data.get("account") or {}).get("username") or "user"
            msg = data.get("msg") or {}
            voice = data.get("voice") or {}
            results.append({
                "username": username,
                "date": self._date_from_filename(path.name) or "",
                "filename": path.name,
                "preview": {
                    "total_messages": msg.get("total_messages", 0),
                    "total_voice_time": format_hours_minutes(voice.get("total_duration_seconds", 0)),
                },
            })

        results.sort(key=lambda r: r["date"], reverse=True)
        return results

    def loadAnalysis(self, filename: str) -> dict | None:
        """Load one specific analysis file from the analyses/ history dir."""
        appdata = os.getenv("APPDATA")
        if not appdata:
            return None
        safe_name = Path(filename).name  # reject any path traversal
        path = Path(appdata) / "Discord-Personal-Data-Analyzer" / "analyses" / safe_name
        if not path.exists():
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            print(f"[WARN] Corrupted saved analysis: {e}", file=sys.stderr)
            return None

    @staticmethod
    def _date_from_filename(filename: str) -> str | None:
        match = re.search(r"_(\d{4}-\d{2}-\d{2})\.json$", filename)
        return match.group(1) if match else None

    def exportAnalysis(self, data: dict) -> str:
        """Save the analysis result to a user-chosen JSON file."""
        import tkinter as tk
        from tkinter import filedialog

        try:
            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            path = filedialog.asksaveasfilename(
                title="Export Analysis",
                defaultextension=".json",
                filetypes=[("JSON files", "*.json")],
                initialfile="discord-analysis.json",
            )
            root.destroy()
            if not path:
                return ""
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            return path
        except Exception:
            return ""

    def importAnalysis(self) -> dict | None:
        """Load a previously exported analysis JSON file, validating its shape."""
        import tkinter as tk
        from tkinter import filedialog

        try:
            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            path = filedialog.askopenfilename(
                title="Import Analysis",
                filetypes=[("JSON files", "*.json")],
            )
            root.destroy()
            if not path:
                return None
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if (
                not isinstance(data.get("msg"), dict)
                or not isinstance(data.get("voice"), dict)
                or not isinstance(data.get("timeline"), dict)
            ):
                print(
                    "[WARN] Imported file is not a valid analysis: missing msg/voice/timeline",
                    file=sys.stderr,
                )
                return None
            return data
        except (json.JSONDecodeError, OSError) as e:
            print(f"[WARN] Failed to import analysis: {e}", file=sys.stderr)
            return None
        except Exception:
            return None

    def checkForUpdate(self) -> None:
        """Check GitHub Releases for a newer version and notify the UI.

        Runs on a background thread (see main.py). Any failure — network,
        rate limiting, malformed response — is swallowed silently.
        """
        import ssl

        try:
            ctx = ssl.create_default_context()
            req = urllib.request.Request(
                _RELEASES_URL,
                headers={
                    "Accept": "application/vnd.github+json",
                    "User-Agent": "Discord-Personal-Data-Analyzer",
                },
            )
            with urllib.request.urlopen(req, context=ctx, timeout=10) as resp:
                release = json.loads(resp.read().decode())

            tag = release.get("tag_name", "")
            match = re.match(r"^v?(\d+)\.(\d+)\.(\d+)", tag)
            if not match:
                return  # non-semver tag, skip silently

            remote_version = tuple(int(g) for g in match.groups())
            local_version = tuple(int(x) for x in VERSION.split("."))

            if remote_version > local_version:
                html_url = release.get("html_url", "")
                self._push_progress("")  # verify webview is available
                try:
                    import webview

                    if webview.windows:
                        webview.windows[0].evaluate_js(
                            f"showUpdateBanner('{tag}', '{html_url}')"
                        )
                except (ImportError, IndexError, AttributeError):
                    pass
        except Exception:
            pass  # network errors, rate limiting, etc. -- all silent
