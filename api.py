"""Python-JS bridge for pywebview Discord Analyzer."""

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

    def analyzeZip(self, zip_path: str) -> dict:
        path = Path(zip_path)
        if path.suffix.lower() != ".zip" or not path.exists():
            return {"error": "Invalid ZIP file"}

        extract_dir = Path(tempfile.mkdtemp(prefix="discord_export_"))
        try:
            with zipfile.ZipFile(path, "r") as zf:
                zf.extractall(extract_dir)
        except (zipfile.BadZipFile, OSError) as e:
            shutil.rmtree(extract_dir, ignore_errors=True)
            return {"error": f"Invalid ZIP: {e}"}

        export_dir = self._find_export_root(extract_dir)
        try:
            msg = full_summary(export_dir)
            voice = voice_summary(export_dir)
        except Exception as e:
            shutil.rmtree(extract_dir, ignore_errors=True)
            return {"error": f"Analysis failed: {e}"}

        shutil.rmtree(extract_dir, ignore_errors=True)

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
