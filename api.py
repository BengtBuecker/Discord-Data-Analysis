"""Python-JS bridge for pywebview Discord Analyzer."""

import json
import os
import sys
import tempfile
import zipfile
import shutil
from pathlib import Path

ANALYZER_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(ANALYZER_DIR))

from analyzers.messages import full_summary
from analyzers.voice import voice_summary


class AnalyzerApi:
    """Exposed to JavaScript via pywebview's js_api mechanism."""

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
        }

    def _find_export_root(self, extract_dir: Path) -> Path:
        if (extract_dir / "Account").exists():
            return extract_dir
        for child in extract_dir.iterdir():
            if child.is_dir() and (child / "Account").exists():
                return child
        return extract_dir

    def saveAnalysis(self, data: dict) -> bool:
        """Persist the last analysis result for auto-restore on next launch."""
        appdata = os.getenv("APPDATA")
        if not appdata:
            return False
        save_dir = Path(appdata) / "Discord-Personal-Data-Analyzer"
        try:
            save_dir.mkdir(parents=True, exist_ok=True)
            with open(save_dir / "last-analysis.json", "w", encoding="utf-8") as f:
                json.dump(data, f)
            return True
        except OSError:
            return False

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
