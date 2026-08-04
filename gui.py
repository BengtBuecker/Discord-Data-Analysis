#!/usr/bin/env python3
"""Discord Data Analyzer -- Desktop GUI (Dashboard Edition)

Zero-dependency modern dashboard. Select your Discord GDPR ZIP,
get a visual breakdown of messages, voice calls, and servers.
"""

import os
import shutil
import sys
import tempfile
import threading
import tkinter as tk
import zipfile
from pathlib import Path
from tkinter import filedialog, ttk

ANALYZER_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(ANALYZER_DIR))

from analyzers.messages import (
    count_messages_by_dm_user,
    count_messages_by_server,
    count_messages_by_channel,
    message_timeline,
    message_summary,
)
from analyzers.voice import voice_summary

# -- Colors (Catppuccin Mocha) -------------------------------------------
C = {
    "bg":       "#1e1e2e",
    "surface":  "#313244",
    "surface0": "#45475a",
    "overlay":  "#585b70",
    "text":     "#cdd6f4",
    "subtext":  "#a6adc8",
    "dim":      "#6c7086",
    "blue":     "#89b4fa",
    "green":    "#a6e3a1",
    "red":      "#f38ba8",
    "yellow":   "#f9e2af",
    "mauve":    "#cba6f7",
    "peach":    "#fab387",
    "teal":     "#94e2d5",
    "base":     "#11111b",
    "crust":    "#11111b",
}
BAR_COLORS = [C["blue"], C["green"], C["mauve"], C["peach"], C["teal"],
              C["yellow"], C["red"], C["overlay"], C["blue"], C["green"]]


class ToolTip:
    """Hover tooltip — shows exact values on mouse enter."""
    def __init__(self, widget, text: str):
        self.widget = widget
        self.text = text
        self.tip = None
        widget.bind("<Enter>", self._show)
        widget.bind("<Leave>", self._hide)
        widget.bind("<Motion>", self._move)

    def _show(self, event=None):
        if self.tip:
            return
        x = self.widget.winfo_rootx() + 12
        y = self.widget.winfo_rooty() - 28
        self.tip = tk.Toplevel(self.widget)
        self.tip.wm_overrideredirect(True)
        self.tip.wm_geometry(f"+{x}+{y}")
        label = tk.Label(self.tip, text=self.text, font=("Segoe UI", 9),
                         bg=C["surface0"], fg=C["text"], padx=8, pady=3,
                         relief=tk.FLAT, bd=0)
        label.pack()

    def _move(self, event):
        if self.tip:
            x = self.widget.winfo_rootx() + event.x + 14
            y = self.widget.winfo_rooty() + event.y - 34
            self.tip.wm_geometry(f"+{x}+{y}")

    def _hide(self, event=None):
        if self.tip:
            self.tip.destroy()
            self.tip = None

# -- Optional drag-and-drop ----------------------------------------------
DND = False
try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    DND = True
except ImportError:
    pass


class DashboardApp:
    def __init__(self):
        self.root = (TkinterDnD.Tk() if DND else tk.Tk())
        self.root.title("Discord Data Analyzer")
        self.root.geometry("960x780")
        self.root.minsize(800, 600)
        self.root.configure(bg=C["bg"])
        self._data = None
        self._build_landing()
        self._center()

    def _center(self):
        self.root.update_idletasks()
        w, h = self.root.winfo_width(), self.root.winfo_height()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        self.root.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")

    # -- Landing --------------------------------------------------------

    def _build_landing(self):
        for w in self.root.winfo_children():
            w.destroy()

        self.landing = tk.Frame(self.root, bg=C["bg"])
        self.landing.pack(fill=tk.BOTH, expand=True)

        spacer = tk.Frame(self.landing, bg=C["bg"], height=120)
        spacer.pack()

        tk.Label(self.landing, text="Discord Data Analyzer",
                 font=("Segoe UI", 28, "bold"), fg=C["text"], bg=C["bg"]).pack()
        tk.Label(self.landing, text="Drop your Discord GDPR ZIP to get started",
                 font=("Segoe UI", 12), fg=C["subtext"], bg=C["bg"]).pack(pady=(4, 32))

        self.drop_frame = tk.Frame(self.landing, bg=C["surface"],
                                    highlightthickness=2,
                                    highlightbackground=C["surface0"])
        self.drop_frame.pack(ipadx=100, ipady=50)

        self.drop_label = tk.Label(self.drop_frame,
                                    text="Drop ZIP here\nor click to select",
                                    font=("Segoe UI", 14), fg=C["dim"],
                                    bg=C["surface"], justify=tk.CENTER, cursor="hand2")
        self.drop_label.pack(padx=60, pady=40)

        self.drop_label.bind("<Button-1>", lambda e: self._select_file())
        self.drop_frame.bind("<Button-1>", lambda e: self._select_file())

        self.select_btn = tk.Button(self.landing, text="Select ZIP File",
                                     font=("Segoe UI", 12, "bold"),
                                     bg=C["blue"], fg=C["base"],
                                     activebackground=C["green"],
                                     activeforeground=C["base"],
                                     relief=tk.FLAT, bd=0, padx=32, pady=10,
                                     cursor="hand2", command=self._select_file)
        self.select_btn.pack(pady=20)

        self.progress = ttk.Progressbar(self.landing, mode="indeterminate", length=300)
        self.status = tk.Label(self.landing, text="",
                               font=("Segoe UI", 10), fg=C["dim"], bg=C["bg"])

        self._bind_drop()

    def _bind_drop(self):
        if not DND:
            return
        self.drop_label.drop_target_register(DND_FILES)
        self.drop_frame.drop_target_register(DND_FILES)

        def on_drop(event):
            path = event.data.strip("{}")
            if os.path.isfile(path):
                self._process_file(path)

        self.drop_label.dnd_bind("<<Drop>>", on_drop)
        self.drop_frame.dnd_bind("<<Drop>>", on_drop)

    # -- File handling --------------------------------------------------

    def _select_file(self):
        path = filedialog.askopenfilename(
            title="Select Discord Data ZIP",
            filetypes=[("ZIP files", "*.zip"), ("All files", "*.*")],
        )
        if path:
            self._process_file(path)

    def _process_file(self, path: str):
        path = Path(path)
        if not path.suffix.lower() == ".zip" or not path.exists():
            return

        self.select_btn.configure(state=tk.DISABLED)
        self.drop_label.configure(text=f"Analyzing {path.name}...", fg=C["yellow"])
        self.progress.pack(pady=(12, 0))
        self.progress.start()
        self.status.pack()
        self.status.configure(text="Extracting ZIP...", fg=C["dim"])

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

        export_dir = self._find_export_root(extract_dir)

        def tick(msg):
            self.root.after(0, lambda: self.status.configure(text=msg, fg=C["dim"]))

        tick("Counting messages...")
        msg = message_summary(export_dir)
        dm_users = count_messages_by_dm_user(export_dir)
        servers = count_messages_by_server(export_dir)
        channels = count_messages_by_channel(export_dir)
        timeline = message_timeline(export_dir, "month")

        tick("Analyzing voice activity...")
        voice = voice_summary(export_dir)

        tick("Building dashboard...")
        data = {
            "msg": msg,
            "dm_users": dm_users,
            "servers": servers,
            "channels": channels,
            "timeline": timeline,
            "voice": voice,
        }

        shutil.rmtree(extract_dir, ignore_errors=True)
        self.root.after(0, lambda: self._build_dashboard(data))

    def _find_export_root(self, extract_dir: Path) -> Path:
        """Discord ZIPs sometimes wrap everything in a subfolder."""
        if (extract_dir / "Account").exists():
            return extract_dir
        for child in extract_dir.iterdir():
            if child.is_dir() and (child / "Account").exists():
                return child
        return extract_dir

    def _show_error(self, msg: str):
        self.progress.stop()
        self.progress.pack_forget()
        self.status.pack_forget()
        self.select_btn.configure(state=tk.NORMAL)
        self.drop_label.configure(
            text="Drop ZIP here\nor click to select", fg=C["dim"])
        self.status.configure(text=msg, fg=C["red"])
        self.status.pack()

    # -- Dashboard ------------------------------------------------------

    def _build_dashboard(self, data: dict):
        self._data = data
        for w in self.root.winfo_children():
            w.destroy()

        # Scrollable canvas
        self.canvas = tk.Canvas(self.root, bg=C["bg"], highlightthickness=0,
                                 bd=0, relief=tk.FLAT)
        scrollbar = tk.Scrollbar(self.root, orient=tk.VERTICAL,
                                  command=self.canvas.yview)
        self.content = tk.Frame(self.canvas, bg=C["bg"])

        self.content.bind("<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.create_window((0, 0), window=self.content, anchor="nw",
                                   width=self.root.winfo_width())
        self.canvas.configure(yscrollcommand=scrollbar.set)

        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Mouse wheel scrolling
        def _on_mousewheel(event):
            self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        self.canvas.bind_all("<MouseWheel>", _on_mousewheel)
        self.canvas.bind("<Enter>",
            lambda e: self.canvas.bind_all("<MouseWheel>", _on_mousewheel))
        self.canvas.bind("<Leave>",
            lambda e: self.canvas.unbind_all("<MouseWheel>"))

        # Header
        hdr = tk.Frame(self.content, bg=C["bg"])
        hdr.pack(fill=tk.X, padx=32, pady=(28, 8))

        tk.Label(hdr, text="Dashboard", font=("Segoe UI", 22, "bold"),
                 fg=C["text"], bg=C["bg"]).pack(side=tk.LEFT)

        new_btn = tk.Button(hdr, text="New Analysis", font=("Segoe UI", 10),
                             bg=C["surface"], fg=C["text"],
                             activebackground=C["overlay"], activeforeground=C["text"],
                             relief=tk.FLAT, bd=0, padx=16, pady=6,
                             cursor="hand2", command=self._build_landing)
        new_btn.pack(side=tk.RIGHT)

        # Summary cards
        self._section_summary(data)

        # DM leaderboard
        self._section_dm_leaderboard(data)

        # Servers
        self._section_servers(data)

        # Voice
        self._section_voice(data)

        # Timeline
        self._section_timeline(data)

    # -- Sections -------------------------------------------------------

    def _section_summary(self, data):
        m = data["msg"]
        v = data["voice"]

        cards = tk.Frame(self.content, bg=C["bg"])
        cards.pack(fill=tk.X, padx=32, pady=(0, 12))

        items = [
            ("Total Messages", f"{m['total_messages']:,}", C["blue"]),
            ("DM Messages", f"{m['dm_total']:,}", C["green"]),
            ("Server Messages", f"{m['server_total']:,}", C["mauve"]),
            ("Voice Time", v.get("total_duration_formatted", "0h 0m"), C["peach"]),
            ("Voice Sessions", str(v.get("total_sessions", 0)), C["teal"]),
        ]

        for i, (label, value, color) in enumerate(items):
            card = tk.Frame(cards, bg=C["surface"], padx=20, pady=14)
            card.pack(side=tk.LEFT, padx=(0 if i == 0 else 8), expand=True,
                       fill=tk.BOTH)

            tk.Label(card, text=label, font=("Segoe UI", 9),
                     fg=C["dim"], bg=C["surface"], anchor="w").pack(fill=tk.X)
            tk.Label(card, text=value, font=("Segoe UI", 22, "bold"),
                     fg=color, bg=C["surface"], anchor="w").pack(fill=tk.X)

    def _section_dm_leaderboard(self, data):
        dm_users = data["dm_users"]
        total = sum(c for _, c in dm_users)
        self._section_header("Top DM Contacts", f"{len(dm_users)} users, {total:,} msgs")
        body = self._section_body()

        top = dm_users[:12]
        max_count = top[0][1] if top else 1

        for i, (name, count) in enumerate(top):
            row = tk.Frame(body, bg=C["base"])
            row.pack(fill=tk.X, pady=1, padx=2)

            rank = tk.Label(row, text=f"{i+1:>2}", font=("Consolas", 10),
                            fg=C["dim"], bg=C["base"], width=3, anchor="e")
            rank.pack(side=tk.LEFT)

            uname = tk.Label(row, text=name[:24], font=("Segoe UI", 10),
                             fg=C["text"], bg=C["base"], anchor="w", width=26)
            uname.pack(side=tk.LEFT, padx=(8, 4))

            bar_w = int(count / max_count * 320)
            bar = tk.Canvas(row, bg=C["base"], height=16, width=320,
                             highlightthickness=0, bd=0)
            bar.pack(side=tk.LEFT)
            color = BAR_COLORS[i % len(BAR_COLORS)]
            if bar_w > 0:
                bar.create_rectangle(0, 2, bar_w, 14, fill=color, outline="",
                                     width=0)
            ToolTip(bar, f"{name}: {count:,} messages")

    def _section_servers(self, data):
        servers = [(n, c) for n, c in data["servers"] if n not in ("Direct Messages", "Unknown")]
        total_srv = sum(c for _, c in servers)
        self._section_header("Servers", f"{len(servers)} servers, {total_srv:,} msgs")
        body = self._section_body()

        top = servers[:10]
        max_count = top[0][1] if top else 1

        for i, (name, count) in enumerate(top):
            row = tk.Frame(body, bg=C["base"])
            row.pack(fill=tk.X, pady=1, padx=2)

            uname = tk.Label(row, text=name[:30], font=("Segoe UI", 10),
                             fg=C["text"], bg=C["base"], anchor="w", width=32)
            uname.pack(side=tk.LEFT, padx=(8, 4))

            bar_w = int(count / max_count * 320)
            bar = tk.Canvas(row, bg=C["base"], height=16, width=320,
                             highlightthreshold=0, bd=0)
            bar.pack(side=tk.LEFT)
            color = BAR_COLORS[i % len(BAR_COLORS)]
            if bar_w > 0:
                bar.create_rectangle(0, 2, bar_w, 14, fill=color, outline="",
                                     width=0)
            ToolTip(bar, f"{name}: {count:,} messages")

    def _section_voice(self, data):
        v = data["voice"]
        channel_durations = v.get("channel_durations", [])
        dm_entries = [c for c in channel_durations if c["name_type"] == "dm"]
        sv_entries = [c for c in channel_durations if c["name_type"] == "server"]

        total_voice_sec = sum(c["duration_seconds"] for c in channel_durations)
        total_h = total_voice_sec // 3600
        total_m = (total_voice_sec % 3600) // 60
        self._section_header("Voice Calls", f"{total_h}h {total_m}m total")
        body = self._section_body()

        if dm_entries:
            tk.Label(body, text="DM Calls", font=("Segoe UI", 9, "bold"),
                     fg=C["green"], bg=C["base"]).pack(anchor="w", padx=10,
                     pady=(8, 4))

            top = dm_entries[:10]
            max_sec = top[0]["duration_seconds"] if top else 1

            for i, c in enumerate(top):
                row = tk.Frame(body, bg=C["base"])
                row.pack(fill=tk.X, pady=1, padx=2)

                uname = tk.Label(row, text=c["name"][:24],
                                 font=("Segoe UI", 10), fg=C["text"],
                                 bg=C["base"], anchor="w", width=26)
                uname.pack(side=tk.LEFT, padx=(8, 4))

                bar_w = int(c["duration_seconds"] / max_sec * 300)
                bar = tk.Canvas(row, bg=C["base"], height=16, width=300,
                                 highlightthickness=0, bd=0)
                bar.pack(side=tk.LEFT)
                color = BAR_COLORS[i % len(BAR_COLORS)]
                if bar_w > 0:
                    bar.create_rectangle(0, 2, bar_w, 14, fill=color,
                                         outline="", width=0)

                h = c["duration_seconds"] // 3600
                m = (c["duration_seconds"] % 3600) // 60
                ToolTip(bar, f"{c['name']}: {h}h {m}m ({c['call_count']} calls)")

        if sv_entries:
            tk.Label(body, text="Server Channels", font=("Segoe UI", 9, "bold"),
                     fg=C["mauve"], bg=C["base"]).pack(anchor="w", padx=10,
                     pady=(12, 4))

            for c in sv_entries[:8]:
                row = tk.Frame(body, bg=C["base"])
                row.pack(fill=tk.X, pady=1, padx=2)

                name = c["name"][:36]
                uname = tk.Label(row, text=name, font=("Segoe UI", 10),
                                 fg=C["text"], bg=C["base"], anchor="w",
                                 width=38)
                uname.pack(side=tk.LEFT, padx=(8, 4))

                h = c["duration_seconds"] // 3600
                m = (c["duration_seconds"] % 3600) // 60
                ToolTip(row, f"{c['name']}: {h}h {m}m ({c['call_count']} sessions)")

    def _section_timeline(self, data):
        timeline = data["timeline"]
        self._section_header("Message Timeline", f"{len(timeline)} months")
        body = self._section_body()

        items = list(timeline.items())
        items.sort()
        if len(items) > 24:
            items = items[-24:]
        max_count = max(c for _, c in items) if items else 1

        canvas_h = 180
        canvas = tk.Canvas(body, bg=C["base"], height=canvas_h,
                            highlightthickness=0, bd=0, width=780)
        canvas.pack(fill=tk.X, padx=8, pady=(8, 8))

        bar_area_left = 40
        bar_area_right = 760
        bar_area_top = 10
        bar_area_bottom = canvas_h - 24
        bar_area_w = bar_area_right - bar_area_left
        bar_area_h = bar_area_bottom - bar_area_top

        # Grid lines
        for pct in (0.25, 0.5, 0.75):
            y = bar_area_bottom - int(bar_area_h * pct)
            canvas.create_line(bar_area_left, y, bar_area_right, y,
                                fill=C["surface0"], width=1)

        # Bars
        n = len(items)
        bar_gap = 3
        total_gap = bar_gap * (n + 1)
        bar_width = (bar_area_w - total_gap) / n if n > 0 else 1

        self._timeline_data = {}
        for i, (period, count) in enumerate(items):
            x0 = bar_area_left + bar_gap + i * (bar_width + bar_gap)
            x1 = x0 + bar_width
            bar_height = int(count / max_count * bar_area_h) if max_count else 0
            y0 = bar_area_bottom - bar_height
            y1 = bar_area_bottom

            color = BAR_COLORS[i % len(BAR_COLORS)]
            tag = f"bar_{i}"
            canvas.create_rectangle(x0, y0, x1, y1, fill=color, outline="",
                                     width=0, tags=(tag,))
            self._timeline_data[tag] = (period, count)

            # Label every 3rd bar
            if i % 3 == 0 and len(period) >= 7:
                label = period[2:7]
                canvas.create_text((x0 + x1) / 2, bar_area_bottom + 12,
                                    text=label, fill=C["dim"],
                                    font=("Consolas", 7), angle=45,
                                    anchor="nw")

        self._timeline_tip = None

        def on_move(event):
            x = canvas.canvasx(event.x)
            y = canvas.canvasy(event.y)
            overlapping = canvas.find_overlapping(x - 2, y - 2, x + 2, y + 2)
            for item_id in overlapping:
                tags = canvas.gettags(item_id)
                for tag in tags:
                    if tag.startswith("bar_"):
                        period, count = self._timeline_data[tag]
                        tip_text = f"{period}: {count:,} messages"
                        if self._timeline_tip is None:
                            self._timeline_tip = tk.Toplevel(canvas)
                            self._timeline_tip.wm_overrideredirect(True)
                            label = tk.Label(self._timeline_tip, text=tip_text,
                                             font=("Segoe UI", 9),
                                             bg=C["surface0"], fg=C["text"],
                                             padx=8, pady=3, relief=tk.FLAT, bd=0)
                            label.pack()
                        else:
                            self._timeline_tip.winfo_children()[0].configure(text=tip_text)
                        rx = canvas.winfo_rootx() + event.x + 14
                        ry = canvas.winfo_rooty() + event.y - 34
                        self._timeline_tip.wm_geometry(f"+{rx}+{ry}")
                        return
            if self._timeline_tip:
                self._timeline_tip.destroy()
                self._timeline_tip = None

        canvas.bind("<Motion>", on_move)
        canvas.bind("<Leave>", lambda e: (
            self._timeline_tip.destroy() if self._timeline_tip else None,
            setattr(self, '_timeline_tip', None),
        ))

        # Max label
        canvas.create_text(bar_area_left - 6, bar_area_top,
                            text=str(max_count), fill=C["dim"],
                            font=("Consolas", 8), anchor="ne")

    # -- Helpers --------------------------------------------------------

    def _section_header(self, title: str, count: int):
        hdr = tk.Frame(self.content, bg=C["bg"])
        hdr.pack(fill=tk.X, padx=32, pady=(16, 0))
        tk.Label(hdr, text=title, font=("Segoe UI", 14, "bold"),
                 fg=C["text"], bg=C["bg"]).pack(side=tk.LEFT)
        tk.Label(hdr, text=str(count), font=("Segoe UI", 12, "bold"),
                 fg=C["blue"], bg=C["bg"]).pack(side=tk.LEFT, padx=(8, 0))

    def _section_body(self) -> tk.Frame:
        outer = tk.Frame(self.content, bg=C["surface"])
        outer.pack(fill=tk.X, padx=32, pady=(4, 0))
        body = tk.Frame(outer, bg=C["base"], padx=1, pady=4)
        body.pack(fill=tk.BOTH, expand=True, padx=12, pady=10)
        return body

    def run(self):
        self.root.mainloop()


def main():
    app = DashboardApp()
    app.run()


if __name__ == "__main__":
    main()
