#!/usr/bin/env python3
"""Discord Data Analyzer — Desktop GUI

Zero-dependency desktop app. Select or drop your Discord GDPR ZIP,
get the full analysis report. Works offline.

Start:  python gui.py
Build:  pip install pyinstaller && pyinstaller --onefile --windowed gui.py
"""

import io
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import tkinter as tk
import zipfile
from pathlib import Path
from tkinter import filedialog, ttk

ANALYZER_DIR = Path(__file__).parent.resolve()

# ── Colors (Catppuccin Mocha) ──────────────────────────────────────────
C = {
    "bg":       "#1e1e2e",
    "surface":  "#313244",
    "overlay":  "#45475a",
    "text":     "#cdd6f4",
    "subtext":  "#6c7086",
    "blue":     "#89b4fa",
    "green":    "#a6e3a1",
    "red":      "#f38ba8",
    "yellow":   "#f9e2af",
    "base":     "#11111b",
}

# ── Drag-and-drop support (optional) ───────────────────────────────────
DND_AVAILABLE = False
try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    DND_AVAILABLE = True
except ImportError:
    pass


class AnalyzerApp:
    def __init__(self):
        if DND_AVAILABLE:
            self.root = TkinterDnD.Tk()
        else:
            self.root = tk.Tk()

        self.root.title("Discord Data Analyzer")
        self.root.geometry("900x700")
        self.root.minsize(600, 500)
        self.root.configure(bg=C["bg"])

        self._build_ui()
        self._center_window()

    def _center_window(self):
        self.root.update_idletasks()
        w, h = self.root.winfo_width(), self.root.winfo_height()
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        x, y = (sw - w) // 2, (sh - h) // 2
        self.root.geometry(f"{w}x{h}+{x}+{y}")

    def _build_ui(self):
        # ── Top bar
        top = tk.Frame(self.root, bg=C["bg"])
        top.pack(fill=tk.X, padx=24, pady=(24, 0))

        tk.Label(
            top, text="Discord Data Analyzer", font=("Segoe UI", 18, "bold"),
            fg=C["text"], bg=C["bg"],
        ).pack(anchor="w")

        tk.Label(
            top, text="Drop your Discord GDPR ZIP or select it below. 100% offline.",
            font=("Segoe UI", 10), fg=C["subtext"], bg=C["bg"],
        ).pack(anchor="w", pady=(4, 0))

        # ── Drop zone
        self.drop_frame = tk.Frame(
            self.root, bg=C["surface"], highlightthickness=2,
            highlightbackground=C["overlay"], relief=tk.FLAT,
        )
        self.drop_frame.pack(fill=tk.BOTH, expand=False, padx=24, pady=16)

        self.drop_label = tk.Label(
            self.drop_frame,
            text="Drop your Discord ZIP here\nor click to select",
            font=("Segoe UI", 13), fg=C["subtext"], bg=C["surface"],
            justify=tk.CENTER, pady=40,
        )
        self.drop_label.pack(fill=tk.BOTH, expand=True)

        self._bind_drop()

        # File picker button
        self.btn_frame = tk.Frame(self.root, bg=C["bg"])
        self.btn_frame.pack(fill=tk.X, padx=24)

        self.select_btn = tk.Button(
            self.btn_frame, text="Select ZIP File", font=("Segoe UI", 11, "bold"),
            bg=C["blue"], fg=C["base"], activebackground=C["green"],
            activeforeground=C["base"], relief=tk.FLAT, bd=0,
            padx=24, pady=8, cursor="hand2",
            command=self._select_file,
        )
        self.select_btn.pack(side=tk.LEFT)

        self.status_label = tk.Label(
            self.btn_frame, text="", font=("Segoe UI", 10),
            fg=C["subtext"], bg=C["bg"],
        )
        self.status_label.pack(side=tk.LEFT, padx=16)

        # ── Progress bar
        self.progress = ttk.Progressbar(
            self.root, mode="indeterminate", length=300,
        )
        self.progress.pack(fill=tk.X, padx=24, pady=(12, 0))
        self.progress.pack_forget()

        # ── Results area
        self.result_frame = tk.Frame(self.root, bg=C["bg"])
        self.result_frame.pack(fill=tk.BOTH, expand=True, padx=24, pady=(12, 8))

        self.result_text = tk.Text(
            self.result_frame, wrap=tk.WORD, font=("Consolas", 10),
            bg=C["base"], fg=C["text"], insertbackground=C["text"],
            relief=tk.FLAT, bd=0, padx=16, pady=12,
            state=tk.DISABLED,
        )
        self.result_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = tk.Scrollbar(
            self.result_frame, command=self.result_text.yview,
            bg=C["surface"], troughcolor=C["bg"], activebackground=C["overlay"],
        )
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.result_text.configure(yscrollcommand=scrollbar.set)

        self._setup_text_tags()

        # ── Bottom buttons
        self.bottom_frame = tk.Frame(self.root, bg=C["bg"])
        self.bottom_frame.pack(fill=tk.X, padx=24, pady=(0, 16))

        self.save_btn = tk.Button(
            self.bottom_frame, text="Save Results", font=("Segoe UI", 10),
            bg=C["surface"], fg=C["text"], activebackground=C["overlay"],
            activeforeground=C["text"], relief=tk.FLAT, bd=0,
            padx=16, pady=6, cursor="hand2",
            command=self._save_results,
            state=tk.DISABLED,
        )
        self.save_btn.pack(side=tk.LEFT)

        self.new_btn = tk.Button(
            self.bottom_frame, text="New Analysis", font=("Segoe UI", 10),
            bg=C["surface"], fg=C["text"], activebackground=C["overlay"],
            activeforeground=C["text"], relief=tk.FLAT, bd=0,
            padx=16, pady=6, cursor="hand2",
            command=self._reset,
            state=tk.DISABLED,
        )
        self.new_btn.pack(side=tk.LEFT, padx=8)

        # ── Status bar
        self.status_bar = tk.Label(
            self.root, text="Ready", font=("Segoe UI", 9),
            fg=C["subtext"], bg=C["bg"], anchor=tk.W,
        )
        self.status_bar.pack(fill=tk.X, padx=24, pady=(0, 8))

    def _setup_text_tags(self):
        self.result_text.tag_configure("h1", font=("Consolas", 12, "bold"), foreground=C["blue"])
        self.result_text.tag_configure("h2", font=("Consolas", 10, "bold"), foreground=C["green"])
        self.result_text.tag_configure("dim", foreground=C["overlay"])
        self.result_text.tag_configure("err", foreground=C["red"])

    def _bind_drop(self):
        # Click on drop zone → file dialog
        self.drop_label.bind("<Button-1>", lambda e: self._select_file())
        self.drop_frame.bind("<Button-1>", lambda e: self._select_file())
        self.drop_label.configure(cursor="hand2")

        if DND_AVAILABLE:
            self.drop_label.drop_target_register(DND_FILES)
            self.drop_frame.drop_target_register(DND_FILES)

            def on_drop(event):
                path = event.data.strip("{}")
                if os.path.isfile(path):
                    self._process_file(path)

            self.drop_label.dnd_bind("<<Drop>>", on_drop)
            self.drop_frame.dnd_bind("<<Drop>>", on_drop)

    # ── Actions ────────────────────────────────────────────────────────

    def _select_file(self):
        path = filedialog.askopenfilename(
            title="Select Discord Data ZIP",
            filetypes=[("ZIP files", "*.zip"), ("All files", "*.*")],
        )
        if path:
            self._process_file(path)

    def _process_file(self, path: str):
        path = Path(path)
        if not path.suffix.lower() == ".zip":
            self._set_status("Please select a .zip file.", C["red"])
            return
        if not path.exists():
            self._set_status("File not found.", C["red"])
            return

        self._set_status(f"Processing {path.name}...", C["yellow"])
        self.progress.pack(fill=tk.X, padx=24, pady=(12, 0))
        self.progress.start()
        self.select_btn.configure(state=tk.DISABLED)
        self.new_btn.configure(state=tk.DISABLED)
        self.save_btn.configure(state=tk.DISABLED)
        self.drop_label.configure(text=f"Analyzing {path.name}...", fg=C["yellow"])

        threading.Thread(target=self._run_analysis, args=(path,), daemon=True).start()

    def _run_analysis(self, zip_path: Path):
        extract_dir = Path(tempfile.mkdtemp(prefix="discord_export_"))
        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(extract_dir)
        except (zipfile.BadZipFile, OSError) as e:
            self.root.after(0, lambda: self._show_error(f"Invalid ZIP: {e}"))
            shutil.rmtree(extract_dir, ignore_errors=True)
            return

        proc = subprocess.run(
            [sys.executable, str(ANALYZER_DIR / "analyzer.py"), "--dir", str(extract_dir), "all"],
            capture_output=True, text=True, timeout=300, cwd=str(ANALYZER_DIR),
        )

        shutil.rmtree(extract_dir, ignore_errors=True)

        output = proc.stdout if proc.returncode == 0 or proc.stdout else f"Error:\n{proc.stderr}"

        self.root.after(0, lambda: self._show_results(output))

    def _show_results(self, text: str):
        self.progress.stop()
        self.progress.pack_forget()
        self.select_btn.configure(state=tk.NORMAL)
        self.new_btn.configure(state=tk.NORMAL)
        self.save_btn.configure(state=tk.NORMAL)
        self.drop_label.configure(
            text="Drop your Discord ZIP here\nor click to select", fg=C["subtext"],
        )

        self.result_text.configure(state=tk.NORMAL)
        self.result_text.delete("1.0", tk.END)

        for line in text.split("\n"):
            stripped = line.strip()
            if stripped.startswith("===="):
                self.result_text.insert(tk.END, line + "\n", "h1")
            elif line.startswith("  ") and stripped and not stripped.startswith("─") and not stripped.startswith("="):
                self.result_text.insert(tk.END, line + "\n", "h2")
            elif line.startswith("───") or line.startswith("==="):
                self.result_text.insert(tk.END, line + "\n", "dim")
            elif "Error" in stripped or "error" in stripped.lower():
                self.result_text.insert(tk.END, line + "\n", "err")
            else:
                self.result_text.insert(tk.END, line + "\n")

        self.result_text.configure(state=tk.DISABLED)
        self.result_text.see("1.0")
        self._set_status("Analysis complete.", C["green"])

    def _show_error(self, msg: str):
        self.progress.stop()
        self.progress.pack_forget()
        self.select_btn.configure(state=tk.NORMAL)
        self.drop_label.configure(
            text="Drop your Discord ZIP here\nor click to select", fg=C["subtext"],
        )
        self._set_status(msg, C["red"])

    def _save_results(self):
        path = filedialog.asksaveasfilename(
            title="Save Results",
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
        )
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.result_text.get("1.0", tk.END))
            self._set_status(f"Saved to {Path(path).name}", C["green"])

    def _reset(self):
        self.result_text.configure(state=tk.NORMAL)
        self.result_text.delete("1.0", tk.END)
        self.result_text.configure(state=tk.DISABLED)
        self.new_btn.configure(state=tk.DISABLED)
        self.save_btn.configure(state=tk.DISABLED)
        self.drop_label.configure(
            text="Drop your Discord ZIP here\nor click to select", fg=C["subtext"],
        )
        self._set_status("Ready", C["subtext"])

    def _set_status(self, msg: str, color: str = None):
        self.status_bar.configure(text=msg, fg=color or C["subtext"])

    def run(self):
        self.root.mainloop()


def main():
    app = AnalyzerApp()
    app.run()


if __name__ == "__main__":
    main()
