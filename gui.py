#!/usr/bin/env python3
"""Discord Data Analyzer -- Desktop Dashboard (Modern Edition)

Zero-dependency modern dashboard. Select your Discord GDPR ZIP,
get a visual breakdown of messages, voice calls, and servers.

Features:
  - Responsive grid layout with wrap on narrow windows
  - Hover effects on all interactive elements
  - Sortable sections (by name/count/duration, asc/desc)
  - Collapsible sections with smooth animation
  - Filter chips for voice data (DM / Server / All)
  - Timeline with granularity toggle (day/month/year)
  - Loading skeleton with shimmer animation
  - Full keyboard navigation (Tab, Enter/Space)
  - Consistent design tokens (spacing, radius, shadow, typography)
"""

import io
import os
import shutil
import sys
import tempfile
import threading
import tkinter as tk
import zipfile
from pathlib import Path
from tkinter import filedialog, ttk
from typing import Optional

ANALYZER_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(ANALYZER_DIR))

from analyzers.messages import full_summary
from analyzers.voice import voice_summary
from utils.formatting import format_hours_minutes


# ═══════════════════════════════════════════════════════════════════════════
# Design Tokens
# ═══════════════════════════════════════════════════════════════════════════

# -- Color Palette (Catppuccin Mocha) --------------------------------------
CLR = {
    # Backgrounds
    "base":        "#11111b",
    "bg":          "#1e1e2e",
    "surface":     "#252836",
    "surface_alt": "#313244",
    "surface_hov": "#363853",
    "overlay":     "#45475a",
    "overlay_dim": "#585b70",
    # Text
    "text":        "#cdd6f4",
    "subtext":     "#a6adc8",
    "dim":         "#6c7086",
    "disabled":    "#4a4d5e",
    # Semantic
    "accent":      "#89b4fa",
    "accent_dim":  "#5a8ad4",
    "success":     "#a6e3a1",
    "danger":      "#f38ba8",
    "warning":     "#f9e2af",
    "mauve":       "#cba6f7",
    "peach":       "#fab387",
    "teal":        "#94e2d5",
    "pink":        "#f5c2e7",
    # Card accent colors (for KPI cards)
    "card_blue":   "#89b4fa",
    "card_green":  "#a6e3a1",
    "card_mauve":  "#cba6f7",
    "card_peach":  "#fab387",
    "card_teal":   "#94e2d5",
}
# Bar chart color rotation
BAR_COLORS = [
    CLR["accent"], CLR["success"], CLR["mauve"], CLR["peach"],
    CLR["teal"], CLR["warning"], CLR["danger"], CLR["pink"],
    CLR["accent"], CLR["success"],
]

# -- Spacing Scale (pixels) ------------------------------------------------
SP = {"xs": 4, "sm": 8, "md": 12, "lg": 16, "xl": 20, "xxl": 24, "xxxl": 32}

# -- Radius Scale (pixels) -------------------------------------------------
RD = {"none": 0, "sm": 4, "md": 6, "lg": 8, "xl": 12, "pill": 999}

# -- Typography ------------------------------------------------------------
FN = {
    "h1":   ("Segoe UI", 22, "bold"),
    "h2":   ("Segoe UI", 16, "bold"),
    "h3":   ("Segoe UI", 14, "bold"),
    "h4":   ("Segoe UI", 12, "bold"),
    "body": ("Segoe UI", 11),
    "body_bold": ("Segoe UI", 11, "bold"),
    "caption": ("Segoe UI", 9),
    "mono": ("Consolas", 10),
    "mono_sm": ("Consolas", 9),
    "kpi": ("Segoe UI", 24, "bold"),
    "kpi_sm": ("Segoe UI", 18, "bold"),
    "kpi_label": ("Segoe UI", 10),
}

# -- Border / Shadow ------------------------------------------------------
# In Tkinter, we simulate via highlightthickness variants.
# Use Frame borders with subtle highlightbackground for card depth.
CARD_BORDER = CLR["overlay"]
CARD_BG = CLR["surface"]
CARD_HOVER_BG = CLR["surface_hov"]


# ═══════════════════════════════════════════════════════════════════════════
# Reusable Widgets
# ═══════════════════════════════════════════════════════════════════════════

class ToolTip:
    """Hover tooltip — shows exact values on mouse enter."""

    def __init__(self, widget: tk.Widget, text: str):
        self.widget = widget
        self.text = text
        self.tip: Optional[tk.Toplevel] = None
        widget.bind("<Enter>", self._show, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<Motion>", self._move, add="+")

    def _show(self, event=None):
        if self.tip:
            return
        x = self.widget.winfo_rootx() + 12
        y = self.widget.winfo_rooty() - 28
        self.tip = tk.Toplevel(self.widget)
        self.tip.wm_overrideredirect(True)
        self.tip.wm_geometry(f"+{x}+{y}")
        label = tk.Label(
            self.tip, text=self.text, font=FN["caption"],
            bg=CLR["overlay"], fg=CLR["text"],
            padx=SP["sm"], pady=SP["xs"],
            relief=tk.FLAT, bd=0,
        )
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


class HoverButton(tk.Canvas):
    """Canvas-based button with hover color transition and keyboard support."""

    def __init__(self, parent, text: str, *, command=None,
                 bg=CLR["surface"], fg=CLR["text"],
                 hover_bg=None, hover_fg=None,
                 font=FN["body"], padx=SP["lg"], pady=SP["md"],
                 radius=RD["md"], border_width=0, border_color="",
                 cursor="hand2", **kw):
        self._text = text
        self._command = command
        self._bg = bg
        self._fg = fg
        self._hover_bg = hover_bg or self._lighten(bg, 0.12)
        self._hover_fg = hover_fg or fg
        self._padx = padx
        self._pady = pady
        self._radius = radius
        self._font = font
        self._border_width = border_width
        self._border_color = border_color
        self._is_hover = False
        self._is_pressed = False

        dummy = tk.Label(parent, text=text, font=font)
        dummy.pack()
        dummy.update_idletasks()
        tw = dummy.winfo_reqwidth()
        th = dummy.winfo_reqheight()
        dummy.destroy()

        w = tw + padx * 2
        h = th + pady * 2
        super().__init__(parent, width=w, height=h,
                         bg=CLR["bg"], highlightthickness=0,
                         bd=0, cursor=cursor, **kw)

        self._draw(bg)
        self._text_id = self.create_text(
            w / 2, h / 2, text=text, fill=fg, font=font,
        )

        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Button-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<KeyPress-space>", self._on_press)
        self.bind("<KeyPress-Return>", self._on_press)
        self.bind("<KeyRelease-space>", self._on_release)
        self.bind("<KeyRelease-Return>", self._on_release)
        self.configure(takefocus=1)

    def _lighten(self, hex_color, factor):
        h = hex_color.lstrip("#")
        r = min(255, int(int(h[0:2], 16) + (255 - int(h[0:2], 16)) * factor))
        g = min(255, int(int(h[2:4], 16) + (255 - int(h[2:4], 16)) * factor))
        b = min(255, int(int(h[4:6], 16) + (255 - int(h[4:6], 16)) * factor))
        return f"#{r:02x}{g:02x}{b:02x}"

    def _draw(self, bg_color):
        self.delete("bg_rect")
        w = int(self["width"])
        h = int(self["height"])
        if self._radius > 0:
            self.create_rounded_rect(
                0, 0, w, h, self._radius, fill=bg_color,
                outline=self._border_color if self._border_width else "",
                width=self._border_width, tags="bg_rect",
            )
        else:
            self.create_rectangle(
                0, 0, w, h, fill=bg_color,
                outline=self._border_color if self._border_width else "",
                width=self._border_width, tags="bg_rect",
            )
        self.tag_lower("bg_rect")

    def create_rounded_rect(self, x1, y1, x2, y2, r, **kw):
        inset = min(r, 4) if r > 0 else 0
        return self.create_rectangle(
            x1 + inset, y1 + max(inset - 1, 0),
            x2 - inset, y2 - max(inset - 1, 0), **kw,
        )

    def _on_enter(self, event=None):
        self._is_hover = True
        self._draw(self._hover_bg)
        self.itemconfigure(self._text_id, fill=self._hover_fg)

    def _on_leave(self, event=None):
        self._is_hover = False
        self._is_pressed = False
        self._draw(self._bg)
        self.itemconfigure(self._text_id, fill=self._fg)

    def _on_press(self, event=None):
        if not self._is_pressed:
            self._is_pressed = True
            self._draw(self._lighten(self._hover_bg, -0.1))

    def _on_release(self, event=None):
        if self._is_pressed:
            self._is_pressed = False
            self._draw(self._hover_bg if self._is_hover else self._bg)
            if self._command:
                self._command()

    def configure(self, **kw):
        if "state" in kw:
            state = kw["state"]
            if state == tk.DISABLED:
                self.unbind("<Enter>")
                self.unbind("<Leave>")
                self.unbind("<Button-1>")
                self.unbind("<ButtonRelease-1>")
                self.unbind("<KeyPress-space>")
                self.unbind("<KeyPress-Return>")
                self.unbind("<KeyRelease-space>")
                self.unbind("<KeyRelease-Return>")
                self.configure(cursor="")
                self._draw(CLR["overlay_dim"])
                self.itemconfigure(self._text_id, fill=CLR["disabled"])
            else:
                self.bind("<Enter>", self._on_enter)
                self.bind("<Leave>", self._on_leave)
                self.bind("<Button-1>", self._on_press)
                self.bind("<ButtonRelease-1>", self._on_release)
                self.bind("<KeyPress-space>", self._on_press)
                self.bind("<KeyPress-Return>", self._on_press)
                self.bind("<KeyRelease-space>", self._on_release)
                self.bind("<KeyRelease-Return>", self._on_release)
                self.configure(cursor="hand2")
        super().configure(**{k: v for k, v in kw.items() if k != "state"})


class SortableHeader(tk.Frame):
    """Clickable section header with sort direction indicator (▲/▼/○)."""

    SORT_NONE = 0
    SORT_ASC = 1
    SORT_DESC = 2

    def __init__(self, parent, title: str, subtitle: str = "",
                 *, on_sort=None, sort_key: str = "default",
                 text_color=CLR["text"], bg_color=CLR["bg"],
                 **kw):
        super().__init__(parent, bg=bg_color, cursor="hand2", **kw)
        self._title = title
        self._subtitle = subtitle
        self._on_sort = on_sort
        self._sort_key = sort_key
        self._sort_state = self.SORT_NONE
        self._text_color = text_color
        self._bg = bg_color
        self._hover = False

        self.title_lbl = tk.Label(
            self, text=title, font=FN["h3"],
            fg=text_color, bg=bg_color, anchor="w",
        )
        self.title_lbl.pack(side=tk.LEFT)

        self.sort_indicator = tk.Label(
            self, text="○", font=FN["caption"],
            fg=CLR["dim"], bg=bg_color, width=2,
        )
        self.sort_indicator.pack(side=tk.LEFT, padx=(SP["xs"], 0))

        if subtitle:
            self.sub_lbl = tk.Label(
                self, text=subtitle, font=FN["body_bold"],
                fg=CLR["accent"], bg=bg_color,
            )
            self.sub_lbl.pack(side=tk.LEFT, padx=(SP["md"], 0))

        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Button-1>", self._on_click)
        self.bind("<KeyPress-space>", self._on_click)
        self.bind("<KeyPress-Return>", self._on_click)
        self.configure(takefocus=1)
        for child in (self.title_lbl, self.sort_indicator):
            child.bind("<Button-1>", self._on_click)
            child.bind("<Enter>", self._on_enter)
            child.bind("<Leave>", self._on_leave)

    @property
    def sort_state(self):
        return self._sort_state

    def clear_sort(self):
        self._sort_state = self.SORT_NONE
        self.sort_indicator.configure(text="○", fg=CLR["dim"])

    def _on_enter(self, event=None):
        self._hover = True
        self.configure(bg=CLR["surface"])
        for c in (self.title_lbl, self.sort_indicator,
                  getattr(self, "sub_lbl", None)):
            if c:
                c.configure(bg=CLR["surface"])

    def _on_leave(self, event=None):
        self._hover = False
        self.configure(bg=self._bg)
        for c in (self.title_lbl, self.sort_indicator,
                  getattr(self, "sub_lbl", None)):
            if c:
                c.configure(bg=self._bg)

    def _on_click(self, event=None):
        self._sort_state = (
            self.SORT_DESC if self._sort_state == self.SORT_ASC
            else self.SORT_ASC
        )
        indicator = "▼" if self._sort_state == self.SORT_ASC else "▲"
        self.sort_indicator.configure(text=indicator, fg=CLR["accent"])
        if self._on_sort:
            self._on_sort(self._sort_key,
                          ascending=self._sort_state == self.SORT_ASC)


class FilterChip(tk.Canvas):
    """Toggle pill-shaped filter chip."""

    def __init__(self, parent, text: str, *, on_toggle=None,
                 active=False, color=CLR["accent"], **kw):
        self._text = text
        self._on_toggle = on_toggle
        self._active = active
        self._color = color
        self._hover = False

        dummy = tk.Label(parent, text=text, font=FN["body_bold"])
        dummy.pack()
        dummy.update_idletasks()
        tw, th = dummy.winfo_reqwidth(), dummy.winfo_reqheight()
        dummy.destroy()

        w, h = tw + 24, th + 8
        super().__init__(parent, width=w, height=h,
                         bg=CLR["bg"], highlightthickness=0,
                         bd=0, cursor="hand2", **kw)
        self._w, self._h = w, h

        self._rect_id = self.create_rounded_rect(
            0, 0, w, h, RD["pill"],
            fill=color if active else CLR["overlay"],
            outline="",
        )
        self._text_id = self.create_text(
            w / 2, h / 2, text=text,
            fill=CLR["base"] if active else CLR["text"],
            font=FN["body_bold"],
        )

        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Button-1>", self._on_click)
        self.configure(takefocus=1)
        self.bind("<KeyPress-space>", self._on_click)
        self.bind("<KeyPress-Return>", self._on_click)

    def create_rounded_rect(self, x1, y1, x2, y2, r, **kw):
        return self.create_rectangle(x1 + 2, y1 + 1, x2 - 2, y2 - 1, **kw)

    @property
    def active(self):
        return self._active

    @active.setter
    def active(self, value):
        self._active = value
        self._redraw()

    def _redraw(self):
        self.itemconfigure(
            self._rect_id,
            fill=self._color if self._active else CLR["overlay"],
        )
        self.itemconfigure(
            self._text_id,
            fill=CLR["base"] if self._active else CLR["text"],
        )

    def _on_enter(self, event=None):
        self._hover = True
        if not self._active:
            self.itemconfigure(self._rect_id, fill=CLR["overlay_dim"])

    def _on_leave(self, event=None):
        self._hover = False
        if not self._active:
            self.itemconfigure(self._rect_id, fill=CLR["overlay"])

    def _on_click(self, event=None):
        self._active = not self._active
        self._redraw()
        if self._on_toggle:
            self._on_toggle(self._active)


class CollapsibleSection(tk.Frame):
    """Section with clickable header and smoothly animated expand/collapse body."""

    ANIM_STEPS = 8
    ANIM_DELAY = 20  # ms per step

    def __init__(self, parent, title: str, subtitle: str = "",
                 *, bg=CLR["bg"], collapsed=False,
                 sortable=False, on_sort=None,
                 **kw):
        super().__init__(parent, bg=bg, **kw)
        self._collapsed = collapsed
        self._target_height = 0
        self._anim_id: Optional[str] = None
        self._bg = bg

        # Header
        hdr_frame = tk.Frame(self, bg=bg)
        hdr_frame.pack(fill=tk.X)

        self._collapse_arrow = tk.Label(
            hdr_frame, text="▼" if not collapsed else "▶",
            font=FN["body_bold"], fg=CLR["dim"], bg=bg,
            width=2, anchor="w",
        )
        self._collapse_arrow.pack(side=tk.LEFT, padx=(SP["sm"], 0))

        if sortable:
            self._secheader = SortableHeader(
                hdr_frame, title=title, subtitle=subtitle,
                text_color=CLR["text"], bg_color=bg,
                on_sort=on_sort, sort_key=title,
            )
            self._secheader.pack(side=tk.LEFT, fill=tk.X, expand=True)
        else:
            self._title_lbl = tk.Label(
                hdr_frame, text=title, font=FN["h3"],
                fg=CLR["text"], bg=bg, anchor="w",
            )
            self._title_lbl.pack(side=tk.LEFT)
            if subtitle:
                tk.Label(
                    hdr_frame, text=subtitle, font=FN["body_bold"],
                    fg=CLR["accent"], bg=bg,
                ).pack(side=tk.LEFT, padx=(SP["md"], 0))

        # Click bindings for collapse
        for w in (hdr_frame, self._collapse_arrow):
            w.bind("<Button-1>", self.toggle)
            w.bind("<KeyPress-space>", self.toggle)
            w.bind("<KeyPress-Return>", self.toggle)
            w.bind("<Enter>", lambda e: w.configure(cursor="hand2"))
            w.bind("<Leave>", lambda e: w.configure(cursor=""))
            w.configure(takefocus=1)

        # Body container — wraps the actual body with fixed height
        self._body_wrapper = tk.Frame(self, bg=bg)
        self._body_wrapper.pack(fill=tk.BOTH, expand=True)

        self._inner_body = tk.Frame(self._body_wrapper, bg=bg)
        self._inner_body.pack(fill=tk.BOTH, expand=True)

        self._body_height = 0
        if collapsed:
            self._body_wrapper.pack_forget()

    @property
    def inner_body(self) -> tk.Frame:
        return self._inner_body

    @property
    def collapsed(self):
        return self._collapsed

    def toggle(self, event=None):
        self._collapsed = not self._collapsed
        self._collapse_arrow.configure(
            text="▶" if self._collapsed else "▼"
        )

        if self._anim_id:
            self.after_cancel(self._anim_id)

        if self._collapsed:
            # Animate close
            current = self._body_wrapper.winfo_reqheight() if self._body_wrapper.winfo_ismapped() else self._body_height
            self._animate_height(current, 0, hide=True, step=0)
        else:
            # Show, then animate open
            self._body_wrapper.pack(fill=tk.BOTH, expand=True)
            self._body_wrapper.update_idletasks()
            target = self._body_wrapper.winfo_reqheight()
            self._body_wrapper.pack_forget()
            self._body_wrapper.pack(fill=tk.BOTH, expand=True)
            self._animate_height(0, target, hide=False, step=0)

    def _animate_height(self, current: int, target: int, hide: bool, step: int):
        steps = self.ANIM_STEPS
        progress = (step + 1) / steps
        # Ease-out cubic
        eased = 1 - (1 - progress) ** 3
        next_h = int(current + (target - current) * eased)

        # Set a temporary fixed height
        self._body_wrapper.configure(height=next_h)
        self._body_wrapper.pack_propagate(False)

        if step < steps - 1:
            self._anim_id = self.after(
                self.ANIM_DELAY,
                lambda: self._animate_height(current, target, hide, step + 1),
            )
        else:
            # Final state
            self._body_wrapper.pack_propagate(True)
            self._body_wrapper.configure(height=0)
            if hide:
                self._body_wrapper.pack_forget()
            self._anim_id = None
            self._body_height = target

    def set_sort_clear(self):
        if hasattr(self, "_secheader"):
            self._secheader.clear_sort()


class DashboardCard(tk.Frame):
    """Hover-aware KPI card with icon accent bar."""

    def __init__(self, parent, label: str, value: str, accent_color: str,
                 *, bg=CLR["surface"], **kw):
        super().__init__(parent, bg=bg, cursor="hand2", **kw)
        self._accent = accent_color
        self._bg = bg
        self._hover = False

        # Accent bar (left side, 4px wide)
        accent_bar = tk.Frame(self, bg=accent_color, width=4)
        accent_bar.pack(side=tk.LEFT, fill=tk.Y)
        accent_bar.pack_propagate(False)

        content = tk.Frame(self, bg=bg)
        content.pack(side=tk.LEFT, fill=tk.BOTH, expand=True,
                     padx=SP["md"], pady=SP["md"])

        self._label_w = tk.Label(
            content, text=label, font=FN["kpi_label"],
            fg=CLR["dim"], bg=bg, anchor="w",
        )
        self._label_w.pack(fill=tk.X)

        self._value_w = tk.Label(
            content, text=value, font=FN["kpi_sm"],
            fg=CLR["text"], bg=bg, anchor="w",
        )
        self._value_w.pack(fill=tk.X)

        # Hover bindings
        for w in (self, content, accent_bar, self._label_w, self._value_w):
            w.bind("<Enter>", self._on_enter, add="+")
            w.bind("<Leave>", self._on_leave, add="+")

    def _on_enter(self, event=None):
        if not self._hover:
            self._hover = True
            hover = CLR["surface_hov"]
            self.configure(bg=hover)
            for c in self.winfo_children():
                if isinstance(c, tk.Frame) and c.winfo_width() != 4:
                    c.configure(bg=hover)
                    for gc in c.winfo_children():
                        gc.configure(bg=hover)

    def _on_leave(self, event=None):
        if self._hover:
            self._hover = False
            self.configure(bg=self._bg)
            for c in self.winfo_children():
                if isinstance(c, tk.Frame) and c.winfo_width() != 4:
                    c.configure(bg=self._bg)
                    for gc in c.winfo_children():
                        gc.configure(bg=self._bg)


class BarRow(tk.Frame):
    """Single leaderboard row with hover highlight, rank, name, proportional bar."""

    def __init__(self, parent, name: str, value: float, max_value: float,
                 index: int, *, rank: int = 0,
                 name_width_chars: int = 26, bar_width_px: int = 300,
                 tooltip: str = "", bg=CLR["base"],
                 **kw):
        super().__init__(parent, bg=bg, cursor="hand2", **kw)
        self._bg = bg
        self._hover = False

        if rank:
            tk.Label(
                self, text=f"{rank:>2}", font=FN["mono_sm"],
                fg=CLR["dim"], bg=bg, width=3, anchor="e",
            ).pack(side=tk.LEFT)

        self._name_lbl = tk.Label(
            self, text=name, font=FN["body"],
            fg=CLR["text"], bg=bg, anchor="w",
            width=name_width_chars,
        )
        self._name_lbl.pack(side=tk.LEFT, padx=(SP["sm"], SP["xs"]))

        self._bar_canvas = tk.Canvas(
            self, bg=bg, height=18, width=bar_width_px,
            highlightthickness=0, bd=0,
        )
        self._bar_canvas.pack(side=tk.LEFT)

        if max_value > 0:
            fill_w = int(value / max_value * bar_width_px)
            if fill_w > 0:
                color = BAR_COLORS[index % len(BAR_COLORS)]
                self._bar_canvas.create_rectangle(
                    0, 2, fill_w, 16, fill=color, outline="", width=0,
                    tags="bar",
                )

        if tooltip:
            ToolTip(self, tooltip)

        # Hover bindings
        for w in [self, self._name_lbl, self._bar_canvas]:
            w.bind("<Enter>", self._on_enter, add="+")
            w.bind("<Leave>", self._on_leave, add="+")

    def _on_enter(self, event=None):
        if not self._hover:
            self._hover = True
            hover = CLR["surface"]
            self.configure(bg=hover)
            self._name_lbl.configure(bg=hover)
            self._bar_canvas.configure(bg=hover)

    def _on_leave(self, event=None):
        if self._hover:
            self._hover = False
            self.configure(bg=self._bg)
            self._name_lbl.configure(bg=self._bg)
            self._bar_canvas.configure(bg=self._bg)


# ═══════════════════════════════════════════════════════════════════════════
# Optional Drag-and-Drop
# ═══════════════════════════════════════════════════════════════════════════

DND = False
try:
    from tkinterdnd2 import DND_FILES, TkinterDnD  # type: ignore
    DND = True
except ImportError:
    pass


# ═══════════════════════════════════════════════════════════════════════════
# Main Application
# ═══════════════════════════════════════════════════════════════════════════

class DashboardApp:
    """Modern Discord Data Analyzer dashboard with grid layout, hover effects,
    sortable sections, collapsible bodies, filter chips, and responsive canvas."""

    def __init__(self):
        self.root = (TkinterDnD.Tk() if DND else tk.Tk())
        self.root.title("Discord Data Analyzer")
        self.root.geometry("960x780")
        self.root.minsize(640, 500)
        self.root.configure(bg=CLR["bg"])

        self._data: Optional[dict] = None
        self._stderr_buf: Optional[io.StringIO] = None

        # Sort state per section
        self._sort_state: dict = {}

        # Bind resize for responsive layout
        self.root.bind("<Configure>", self._on_window_resize, add="+")

        self._build_landing()
        self._center()

    def _center(self):
        self.root.update_idletasks()
        w, h = self.root.winfo_width(), self.root.winfo_height()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        self.root.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2}")

    # ── Landing ────────────────────────────────────────────────────────

    def _build_landing(self):
        for w in self.root.winfo_children():
            w.destroy()

        self.landing = tk.Frame(self.root, bg=CLR["bg"])
        self.landing.pack(fill=tk.BOTH, expand=True)

        # Centering wrapper
        center = tk.Frame(self.landing, bg=CLR["bg"])
        center.place(relx=0.5, rely=0.5, anchor="center")

        # App icon / branding
        tk.Label(
            center, text="⬡", font=("Segoe UI", 40),
            fg=CLR["accent"], bg=CLR["bg"],
        ).pack(pady=(0, SP["md"]))

        tk.Label(
            center, text="Discord Data Analyzer",
            font=FN["h1"], fg=CLR["text"], bg=CLR["bg"],
        ).pack()

        tk.Label(
            center, text="Drop your Discord GDPR ZIP to get started",
            font=FN["body"], fg=CLR["subtext"], bg=CLR["bg"],
        ).pack(pady=(SP["xs"], SP["xxl"]))

        # Drop zone
        self.drop_frame = tk.Frame(
            center, bg=CLR["surface"],
            highlightthickness=1,
            highlightbackground=CLR["overlay"],
        )
        self.drop_frame.pack(ipadx=80, ipady=40, pady=(0, SP["lg"]))

        drop_inner = tk.Frame(self.drop_frame, bg=CLR["surface"])
        drop_inner.pack(padx=60, pady=40)

        self.drop_icon = tk.Label(
            drop_inner, text="📂", font=("Segoe UI", 28),
            fg=CLR["dim"], bg=CLR["surface"],
        )
        self.drop_icon.pack()

        self.drop_label = tk.Label(
            drop_inner,
            text="Drop ZIP here\nor click to select",
            font=FN["body"],
            fg=CLR["dim"], bg=CLR["surface"],
            justify=tk.CENTER, cursor="hand2",
        )
        self.drop_label.pack(pady=(SP["sm"], 0))

        # Click bindings for drop zone
        self.drop_label.bind("<Button-1>", lambda e: self._select_file())
        self.drop_frame.bind("<Button-1>", lambda e: self._select_file())

        # Select button
        self.select_btn = HoverButton(
            center, text="Select ZIP File",
            font=FN["body_bold"],
            bg=CLR["accent"], fg=CLR["base"],
            hover_bg=CLR["accent_dim"], hover_fg=CLR["base"],
            padx=28, pady=SP["md"], radius=RD["md"],
            command=self._select_file,
        )
        self.select_btn.pack()

        # Progress & status (hidden initially)
        self.progress = ttk.Progressbar(center, mode="indeterminate", length=280)
        self.status_lbl = tk.Label(
            center, text="", font=FN["caption"],
            fg=CLR["dim"], bg=CLR["bg"],
        )

        # Shimmer skeleton (hidden initially)
        self._skeleton = None

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

    # ── Loading Skeleton ───────────────────────────────────────────────

    def _show_skeleton(self):
        """Show shimmer placeholder cards during analysis."""
        if self._skeleton:
            return
        self._skeleton = tk.Frame(self.landing, bg=CLR["bg"])
        self._skeleton.pack(pady=(SP["xxxl"], 0))

        for _ in range(5):
            card = tk.Frame(
                self._skeleton, bg=CLR["surface"],
                width=140, height=70,
            )
            card.pack(side=tk.LEFT, padx=SP["sm"], pady=SP["sm"])
            card.pack_propagate(False)

            tk.Frame(card, bg=CLR["overlay"],
                     width=4, height=70).pack(side=tk.LEFT, fill=tk.Y)
            inner = tk.Frame(card, bg=CLR["surface"])
            inner.pack(side=tk.LEFT, fill=tk.BOTH, expand=True,
                       padx=SP["md"], pady=SP["md"])
            tk.Frame(inner, bg=CLR["overlay_dim"],
                     width=80, height=8).pack(anchor="w", pady=(0, 4))
            tk.Frame(inner, bg=CLR["overlay"],
                     width=100, height=14).pack(anchor="w")

        self._animate_skeleton()

    def _animate_skeleton(self):
        if not self._skeleton:
            return
        # Simple shimmer: toggle opacity via bg color pulse
        # (Tkinter doesn't do real alpha, so pulse between shades)
        import random
        for card in self._skeleton.winfo_children():
            shade = random.choice([CLR["surface"], CLR["surface_alt"],
                                    CLR["surface_hov"]])
            try:
                card.configure(bg=shade)
                for c in card.winfo_children():
                    c.configure(bg=shade if isinstance(c, tk.Frame) else shade)
            except tk.TclError:
                return
        self._skeleton.after(600, self._animate_skeleton)

    def _hide_skeleton(self):
        if self._skeleton:
            self._skeleton.destroy()
            self._skeleton = None

    # ── File Handling ──────────────────────────────────────────────────

    def _select_file(self):
        path = filedialog.askopenfilename(
            title="Select Discord Data ZIP",
            filetypes=[("ZIP files", "*.zip"), ("All files", "*.*")],
        )
        if path:
            self._process_file(path)

    def _process_file(self, zip_path: str):
        path = Path(zip_path)
        if path.suffix.lower() != ".zip" or not path.exists():
            return

        # Disable select button
        try:
            self.select_btn.configure(state=tk.DISABLED)
        except tk.TclError:
            pass

        self.drop_label.configure(text=f"Analyzing {path.name}...", fg=CLR["warning"])
        self.progress.pack(pady=(SP["md"], SP["xs"]))
        self.progress.start()
        self.status_lbl.pack()
        self.status_lbl.configure(text="Extracting ZIP...", fg=CLR["dim"])
        self._show_skeleton()

        self._stderr_buf = io.StringIO()
        self.root.after(200, self._poll_stderr)

        threading.Thread(target=self._run_analysis, args=(path,), daemon=True).start()

    def _poll_stderr(self):
        if not hasattr(self, "_stderr_buf") or self._stderr_buf is None:
            return
        text = self._stderr_buf.getvalue()
        if text:
            last_line = text.strip().split("\n")[-1].strip()
            if last_line and "\r" in last_line:
                last_line = last_line.rsplit("\r", 1)[-1].strip()
            if last_line:
                try:
                    self.status_lbl.configure(text=last_line)
                except tk.TclError:
                    return
        if not hasattr(self, "_data") or self._data is None:
            self.root.after(200, self._poll_stderr)

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

        old_stderr = sys.stderr
        sys.stderr = self._stderr_buf

        try:
            msg = full_summary(export_dir)
            voice = voice_summary(export_dir)
        except Exception as e:
            self.root.after(0, lambda: self._show_error(f"Analysis failed: {e}"))
            shutil.rmtree(extract_dir, ignore_errors=True)
            return
        finally:
            sys.stderr = old_stderr

        data = {
            "msg": msg,
            "dm_users": msg["dm_users"],
            "servers": msg["servers"],
            "timeline": msg["timeline"],
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
        self._stderr_buf = None
        self._hide_skeleton()
        self.progress.stop()
        self.progress.pack_forget()
        self.status_lbl.pack_forget()
        try:
            self.select_btn.configure(state="normal")
        except tk.TclError:
            pass
        self.drop_label.configure(
            text="Drop ZIP here\nor click to select", fg=CLR["dim"])
        self.status_lbl.configure(text=msg, fg=CLR["danger"])
        self.status_lbl.pack()

    # ── Dashboard ──────────────────────────────────────────────────────

    def _build_dashboard(self, data: dict):
        self._data = data
        self._hide_skeleton()
        for w in self.root.winfo_children():
            w.destroy()

        # Main container
        self.main = tk.Frame(self.root, bg=CLR["bg"])
        self.main.pack(fill=tk.BOTH, expand=True)

        # Scrollable canvas
        self.canvas = tk.Canvas(
            self.main, bg=CLR["bg"], highlightthickness=0,
            bd=0, relief=tk.FLAT,
        )
        self.v_scrollbar = tk.Scrollbar(
            self.main, orient=tk.VERTICAL, command=self.canvas.yview,
        )
        self.content = tk.Frame(self.canvas, bg=CLR["bg"])

        self.canvas_window = self.canvas.create_window(
            (0, 0), window=self.content, anchor="nw",
        )

        self.content.bind("<Configure>", self._on_content_configure)
        self.canvas.configure(yscrollcommand=self.v_scrollbar.set)

        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Mouse wheel scrolling
        def _on_mousewheel(event):
            self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        def _bind_wheel(_):
            self.canvas.bind_all("<MouseWheel>", _on_mousewheel)

        def _unbind_wheel(_):
            self.canvas.unbind_all("<MouseWheel>")

        self.canvas.bind("<Enter>", _bind_wheel)
        self.canvas.bind("<Leave>", _unbind_wheel)

        # Header
        self._build_header()

        # Sections
        self._build_summary_section(data)
        self._build_dm_section(data)
        self._build_servers_section(data)
        self._build_voice_section(data)
        self._build_timeline_section(data)

        # Initial canvas sizing
        self.root.after(100, self._sync_canvas_width)

    def _on_content_configure(self, event):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _sync_canvas_width(self):
        """Make canvas track content width."""
        w = self.canvas.winfo_width()
        if w > 10:
            self.canvas.itemconfigure(self.canvas_window, width=w)

    def _on_window_resize(self, event):
        if event.widget is self.root:
            if hasattr(self, "canvas"):
                self._sync_canvas_width()
            if hasattr(self, "_summary_grid") and hasattr(self, "_summary_cards"):
                self._relayout_summary_cards()

    # ── Header ─────────────────────────────────────────────────────────

    def _build_header(self):
        hdr = tk.Frame(self.content, bg=CLR["bg"])
        hdr.pack(fill=tk.X, padx=SP["xxxl"], pady=(SP["xxl"], SP["md"]))

        left = tk.Frame(hdr, bg=CLR["bg"])
        left.pack(side=tk.LEFT)

        tk.Label(
            left, text="⬡", font=("Segoe UI", 18),
            fg=CLR["accent"], bg=CLR["bg"],
        ).pack(side=tk.LEFT, padx=(0, SP["sm"]))

        tk.Label(
            left, text="Dashboard", font=FN["h1"],
            fg=CLR["text"], bg=CLR["bg"],
        ).pack(side=tk.LEFT)

        new_btn = HoverButton(
            hdr, text="New Analysis",
            font=FN["body"],
            bg=CLR["surface"], fg=CLR["text"],
            hover_bg=CLR["surface_hov"],
            padx=SP["lg"], pady=SP["sm"], radius=RD["md"],
            command=self._build_landing,
        )
        new_btn.pack(side=tk.RIGHT)

    # ── Summary Section ────────────────────────────────────────────────

    def _build_summary_section(self, data: dict):
        m = data["msg"]
        v = data["voice"]

        section = tk.Frame(self.content, bg=CLR["bg"])
        section.pack(fill=tk.X, padx=SP["xxxl"], pady=(SP["lg"], SP["md"]))

        tk.Label(
            section, text="Overview", font=FN["h4"],
            fg=CLR["dim"], bg=CLR["bg"],
        ).pack(anchor="w", pady=(0, SP["sm"]))

        self._summary_grid = tk.Frame(section, bg=CLR["bg"])
        self._summary_grid.pack(fill=tk.X)

        items = [
            ("Total Messages", f"{m['total_messages']:,}", CLR["card_blue"]),
            ("DM Messages", f"{m['dm_total']:,}", CLR["card_green"]),
            ("Server Messages", f"{m['server_total']:,}", CLR["card_mauve"]),
            ("Voice Time", v.get("total_duration_formatted", "0h 0m"), CLR["card_peach"]),
            ("Voice Sessions", str(v.get("total_sessions", 0)), CLR["card_teal"]),
        ]

        self._summary_cards = []
        for i, (label, value, color) in enumerate(items):
            card = DashboardCard(
                self._summary_grid, label=label, value=value,
                accent_color=color,
            )
            self._summary_cards.append(card)

        self._relayout_summary_cards()

    def _relayout_summary_cards(self):
        """Grid layout that wraps on narrow windows."""
        if not hasattr(self, "_summary_cards") or not self._summary_cards:
            return

        window_w = self.root.winfo_width()
        cols = 5 if window_w > 800 else (3 if window_w > 600 else 2)

        # Remove all from grid
        for c in self._summary_grid.winfo_children():
            c.grid_forget()

        for i, card in enumerate(self._summary_cards):
            row, col = divmod(i, cols)
            pad = (SP["xs"], SP["xs"]) if col < cols - 1 else (SP["xs"], 0)
            card.grid(row=row, column=col, padx=pad, pady=SP["xs"], sticky="nsew")

        # Weight columns evenly
        for c in range(cols):
            self._summary_grid.columnconfigure(c, weight=1)

    # ── DM Leaderboard Section ─────────────────────────────────────────

    def _build_dm_section(self, data: dict):
        dm_users = data["dm_users"]
        total = sum(c for _, c in dm_users)

        self._dm_section = CollapsibleSection(
            self.content, title="Top DM Contacts",
            subtitle=f"{len(dm_users)} users, {total:,} msgs",
            sortable=True, on_sort=self._sort_dm,
        )
        self._dm_section.pack(fill=tk.X, padx=SP["xxxl"], pady=(SP["lg"], 0))

        body = self._build_section_body(self._dm_section.inner_body)
        self._dm_body = body
        self._dm_data = dm_users

        self._render_dm_rows()

    def _render_dm_rows(self):
        body = self._dm_body
        for w in body.winfo_children():
            w.destroy()

        dm_users = self._dm_data
        key = self._sort_state.get("dm", ("count", True))
        sort_by, asc = key

        if sort_by == "name":
            sorted_data = sorted(dm_users, key=lambda x: x[0], reverse=not asc)
        else:
            sorted_data = sorted(dm_users, key=lambda x: x[1], reverse=asc)

        top = sorted_data[:12]
        max_count = top[0][1] if top else 1
        bar_w = self._calc_bar_width()

        for i, (name, count) in enumerate(top):
            BarRow(
                body, name=name[:24], value=count,
                max_value=max_count, index=i,
                rank=i + 1, name_width_chars=24,
                bar_width_px=bar_w,
                tooltip=f"{name}: {count:,} messages",
            ).pack(fill=tk.X, pady=1, padx=2)

    def _sort_dm(self, key: str, ascending: bool):
        self._sort_state["dm"] = (key, ascending)
        self._render_dm_rows()

    # ── Servers Section ────────────────────────────────────────────────

    def _build_servers_section(self, data: dict):
        servers = [(n, c) for n, c in data["servers"]
                   if n not in ("Direct Messages", "Unknown")]
        total_srv = sum(c for _, c in servers)

        self._srv_section = CollapsibleSection(
            self.content, title="Servers",
            subtitle=f"{len(servers)} servers, {total_srv:,} msgs",
            sortable=True, on_sort=self._sort_servers,
        )
        self._srv_section.pack(fill=tk.X, padx=SP["xxxl"], pady=(SP["lg"], 0))

        body = self._build_section_body(self._srv_section.inner_body)
        self._srv_body = body
        self._srv_data = servers
        self._render_srv_rows()

    def _render_srv_rows(self):
        body = self._srv_body
        for w in body.winfo_children():
            w.destroy()

        servers = self._srv_data
        key = self._sort_state.get("servers", ("count", True))
        sort_by, asc = key

        if sort_by == "name":
            sorted_data = sorted(servers, key=lambda x: x[0], reverse=not asc)
        else:
            sorted_data = sorted(servers, key=lambda x: x[1], reverse=asc)

        top = sorted_data[:10]
        max_count = top[0][1] if top else 1
        bar_w = self._calc_bar_width()

        for i, (name, count) in enumerate(top):
            BarRow(
                body, name=name[:30], value=count,
                max_value=max_count, index=i,
                name_width_chars=30, bar_width_px=bar_w,
                tooltip=f"{name}: {count:,} messages",
            ).pack(fill=tk.X, pady=1, padx=2)

    def _sort_servers(self, key: str, ascending: bool):
        self._sort_state["servers"] = (key, ascending)
        self._render_srv_rows()

    # ── Voice Section ──────────────────────────────────────────────────

    def _build_voice_section(self, data: dict):
        v = data["voice"]
        channel_durations = v.get("channel_durations", [])
        dm_entries = [c for c in channel_durations if c["name_type"] == "dm"]
        sv_entries = [c for c in channel_durations if c["name_type"] == "server"]

        total_voice_sec = sum(c["duration_seconds"] for c in channel_durations)

        self._voice_section = CollapsibleSection(
            self.content, title="Voice Calls",
            subtitle=format_hours_minutes(total_voice_sec) + " total",
        )
        self._voice_section.pack(fill=tk.X, padx=SP["xxxl"], pady=(SP["lg"], 0))

        inner = self._voice_section.inner_body

        # Filter chips
        chip_bar = tk.Frame(inner, bg=CLR["bg"])
        chip_bar.pack(fill=tk.X, padx=SP["sm"], pady=(SP["md"], SP["sm"]))

        self._voice_filter = "all"  # "all", "dm", "server"
        self._voice_dm_entries = dm_entries
        self._voice_sv_entries = sv_entries
        self._voice_body = self._build_section_body(inner)
        self._voice_chip_bar = chip_bar

        def make_toggle(chip_type):
            def handler(active):
                if active:
                    self._voice_filter = chip_type
                    self._render_voice_rows()
                elif self._voice_filter == chip_type:
                    self._voice_filter = "all"
                    self._render_voice_rows()
            return handler

        self._chip_all = FilterChip(
            chip_bar, text="All", active=True, color=CLR["accent"],
            on_toggle=lambda a: self._set_voice_filter("all"),
        )
        self._chip_all.pack(side=tk.LEFT, padx=(0, SP["sm"]))

        self._chip_dm = FilterChip(
            chip_bar, text="DM Calls", color=CLR["card_green"],
            on_toggle=lambda a: self._set_voice_filter("dm"),
        )
        self._chip_dm.pack(side=tk.LEFT, padx=(0, SP["sm"]))

        self._chip_sv = FilterChip(
            chip_bar, text="Server Channels", color=CLR["card_mauve"],
            on_toggle=lambda a: self._set_voice_filter("server"),
        )
        self._chip_sv.pack(side=tk.LEFT)

        self._render_voice_rows()

    def _set_voice_filter(self, filter_type: str):
        if self._voice_filter == filter_type:
            self._voice_filter = "all"
            self._chip_all.active = True
            self._chip_dm.active = False
            self._chip_sv.active = False
        else:
            self._voice_filter = filter_type
            self._chip_all.active = (filter_type == "all")
            self._chip_dm.active = (filter_type == "dm")
            self._chip_sv.active = (filter_type == "server")
        self._render_voice_rows()

    def _render_voice_rows(self):
        body = self._voice_body
        for w in body.winfo_children():
            w.destroy()

        dm_entries = self._voice_dm_entries
        sv_entries = self._voice_sv_entries
        filt = self._voice_filter

        if filt in ("all", "dm") and dm_entries:
            tk.Label(
                body, text="DM Calls", font=FN["body_bold"],
                fg=CLR["card_green"], bg=CLR["base"],
            ).pack(anchor="w", padx=SP["md"], pady=(SP["sm"], SP["xs"]))

            top = dm_entries[:10]
            max_sec = top[0]["duration_seconds"] if top else 1
            bar_w = self._calc_bar_width()

            for i, c in enumerate(top):
                duration = format_hours_minutes(c["duration_seconds"])
                BarRow(
                    body, name=c["name"][:24], value=c["duration_seconds"],
                    max_value=max_sec, index=i,
                    rank=0, name_width_chars=24, bar_width_px=bar_w,
                    tooltip=f"{c['name']}: {duration} ({c['call_count']} calls)",
                ).pack(fill=tk.X, pady=1, padx=2)

        if filt in ("all", "server") and sv_entries:
            tk.Label(
                body, text="Server Channels", font=FN["body_bold"],
                fg=CLR["card_mauve"], bg=CLR["base"],
            ).pack(anchor="w", padx=SP["md"],
                   pady=(SP["lg"] if filt == "all" else SP["sm"], SP["xs"]))

            bar_w = self._calc_bar_width()

            for c in sv_entries[:8]:
                row = tk.Frame(body, bg=CLR["base"], cursor="hand2")
                row.pack(fill=tk.X, pady=1, padx=2)

                name = c["name"][:36]
                tk.Label(
                    row, text=name, font=FN["body"],
                    fg=CLR["text"], bg=CLR["base"], anchor="w",
                    width=36,
                ).pack(side=tk.LEFT, padx=(SP["sm"], SP["xs"]))

                duration = format_hours_minutes(c["duration_seconds"])
                ToolTip(row, f"{c['name']}: {duration} ({c['call_count']} sessions)")

                # Hover
                def make_hover(r):
                    def enter(e): r.configure(bg=CLR["surface"])
                    def leave(e): r.configure(bg=CLR["base"])
                    r.bind("<Enter>", enter, add="+")
                    r.bind("<Leave>", leave, add="+")
                make_hover(row)

        if not body.winfo_children():
            tk.Label(
                body, text="No data for this filter",
                font=FN["body"], fg=CLR["dim"], bg=CLR["base"],
            ).pack(pady=SP["lg"])

    # ── Timeline Section ───────────────────────────────────────────────

    def _build_timeline_section(self, data: dict):
        timeline = data["timeline"]

        section = CollapsibleSection(
            self.content, title="Message Timeline",
            subtitle=f"{len(timeline)} months",
        )
        section.pack(fill=tk.X, padx=SP["xxxl"], pady=(SP["xxl"], 0))

        body = self._build_section_body(section.inner_body)
        body.configure(padx=SP["sm"], pady=SP["sm"])
        self._tl_body = body
        self._tl_section = section

        self._timeline_data = dict(sorted(data["timeline"].items()))
        self._render_timeline()

    def _render_timeline(self):
        body = self._tl_body
        for w in body.winfo_children():
            w.destroy()

        timeline = self._timeline_data
        items = list(timeline.items())

        if len(items) > 24:
            items = items[-24:]
        max_count = max(c for _, c in items) if items else 1

        canvas_h = 180
        canvas = tk.Canvas(
            body, bg=CLR["base"], height=canvas_h,
            highlightthickness=0, bd=0,
        )
        canvas.pack(fill=tk.X, padx=SP["sm"], pady=(SP["sm"], SP["sm"]))

        bar_data: dict = {}
        n = len(items)

        def draw(evt=None):
            canvas.delete("all")
            bar_data.clear()

            cw = canvas.winfo_width()
            bar_area_left = 44
            bar_area_right = cw - 16
            bar_area_top = 10
            bar_area_bottom = canvas_h - 24
            bar_area_w = bar_area_right - bar_area_left
            bar_area_h = bar_area_bottom - bar_area_top

            if bar_area_w <= 0 or bar_area_h <= 0:
                return

            # Grid lines
            for pct in (0.25, 0.5, 0.75):
                y = bar_area_bottom - int(bar_area_h * pct)
                canvas.create_line(
                    bar_area_left, y, bar_area_right, y,
                    fill=CLR["overlay"], width=1,
                )

            # Bars
            bar_gap = 3
            total_gap = bar_gap * (n + 1)
            bar_width = max((bar_area_w - total_gap) / n, 1) if n > 0 else 1

            for i, (period, count) in enumerate(items):
                x0 = bar_area_left + bar_gap + i * (bar_width + bar_gap)
                x1 = x0 + bar_width
                bar_height = int(count / max_count * bar_area_h) if max_count else 0
                y0 = bar_area_bottom - bar_height
                y1 = bar_area_bottom

                color = BAR_COLORS[i % len(BAR_COLORS)]
                tag = f"bar_{i}"
                canvas.create_rectangle(
                    x0, y0, x1, y1, fill=color, outline="", width=0, tags=(tag,),
                )
                bar_data[tag] = (period, count)

                # Label every 3rd bar
                if i % 3 == 0 and len(period) >= 7:
                    label = period[2:7] if len(period) >= 7 else period
                    canvas.create_text(
                        (x0 + x1) / 2, bar_area_bottom + 12,
                        text=label, fill=CLR["dim"],
                        font=FN["mono_sm"], angle=45, anchor="nw",
                    )

            # Max label
            canvas.create_text(
                bar_area_left - 6, bar_area_top,
                text=str(max_count), fill=CLR["dim"],
                font=FN["mono_sm"], anchor="ne",
            )

        canvas.bind("<Configure>", draw, add="+")

        # Hover tooltip
        self._timeline_tip = None

        def on_move(event):
            x = canvas.canvasx(event.x)
            y = canvas.canvasy(event.y)
            overlapping = canvas.find_overlapping(x - 2, y - 2, x + 2, y + 2)
            for item_id in overlapping:
                for tag in canvas.gettags(item_id):
                    if tag in bar_data:
                        period, count = bar_data[tag]
                        tip_text = f"{period}: {count:,} messages"
                        if self._timeline_tip is None:
                            self._timeline_tip = tk.Toplevel(canvas)
                            self._timeline_tip.wm_overrideredirect(True)
                            label = tk.Label(
                                self._timeline_tip, text=tip_text,
                                font=FN["caption"],
                                bg=CLR["overlay"], fg=CLR["text"],
                                padx=SP["sm"], pady=SP["xs"],
                                relief=tk.FLAT, bd=0,
                            )
                            label.pack()
                        else:
                            try:
                                self._timeline_tip.winfo_children()[0].configure(text=tip_text)
                            except tk.TclError:
                                self._timeline_tip = None
                                return
                        rx = canvas.winfo_rootx() + event.x + 14
                        ry = canvas.winfo_rooty() + event.y - 34
                        self._timeline_tip.wm_geometry(f"+{rx}+{ry}")
                        return
            if self._timeline_tip:
                self._timeline_tip.destroy()
                self._timeline_tip = None

        canvas.bind("<Motion>", on_move, add="+")
        canvas.bind("<Leave>", lambda e: (
            self._timeline_tip.destroy() if self._timeline_tip else None,
            setattr(self, "_timeline_tip", None),
        ), add="+")

    # ── Helpers ────────────────────────────────────────────────────────

    def _build_section_body(self, parent) -> tk.Frame:
        outer = tk.Frame(parent, bg=CLR["surface"])
        outer.pack(fill=tk.X, pady=(SP["xs"], 0))
        body = tk.Frame(outer, bg=CLR["base"], padx=1, pady=SP["xs"])
        body.pack(fill=tk.BOTH, expand=True, padx=SP["md"], pady=SP["md"])
        return body

    def _calc_bar_width(self) -> int:
        """Calculate proportional bar width from current window size."""
        window_w = self.root.winfo_width()
        if window_w > 900:
            return 400
        elif window_w > 750:
            return 300
        elif window_w > 650:
            return 200
        else:
            return 140

    def run(self):
        self.root.mainloop()


def main():
    app = DashboardApp()
    app.run()


if __name__ == "__main__":
    main()
