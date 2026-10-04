"""Dark theme + reusable widgets for the TaskPilot UI (pure Tkinter/ttk)."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable, Sequence

# ------------------------------------------------------------------ colours
BG = "#0F1116"
SIDEBAR = "#141822"
PANEL = "#191E2A"
PANEL_HOVER = "#222939"
CARD = "#1C2231"
BORDER = "#2A3142"
ACCENT = "#4F8CFF"
ACCENT_DARK = "#2F6BE0"
TEXT = "#EAF0FA"
MUTED = "#8A93A6"
SUCCESS = "#2FBF71"
WARNING = "#F5A623"
DANGER = "#E5484D"
TRACK = "#262D3D"

FONT_FAMILY = "Segoe UI"
TITLE_FONT = (FONT_FAMILY, 16, "bold")
H2_FONT = (FONT_FAMILY, 12, "bold")
BODY_FONT = (FONT_FAMILY, 10)
SMALL_FONT = (FONT_FAMILY, 9)
TINY_FONT = (FONT_FAMILY, 8)
MONO = ("Consolas", 10)


def apply_theme(root: tk.Tk | tk.Widget) -> None:
    """Configure ttk styles so the native widgets match the dark theme."""
    root.option_add("*Font", BODY_FONT)
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    style.configure(".", background=BG, foreground=TEXT, fieldbackground=PANEL,
                    bordercolor=BORDER, lightcolor=BG, darkcolor=BG,
                    font=BODY_FONT, selectbackground=ACCENT,
                    selectforeground="#FFFFFF", insertcolor=TEXT)
    style.configure("TFrame", background=BG)
    style.configure("Card.TFrame", background=CARD)
    style.configure("TLabel", background=BG, foreground=TEXT)
    style.configure("Card.TLabel", background=CARD, foreground=TEXT)
    style.configure("Muted.TLabel", background=CARD, foreground=MUTED)
    style.configure("TButton", background=PANEL_HOVER, foreground=TEXT,
                    borderwidth=0, focusthickness=0, padding=(12, 7))
    style.map("TButton",
              background=[("active", ACCENT_DARK), ("pressed", ACCENT_DARK)],
              foreground=[("active", "#FFFFFF")])
    style.configure("Accent.TButton", background=ACCENT, foreground="#FFFFFF")
    style.map("Accent.TButton", background=[("active", ACCENT_DARK)])
    style.configure("Danger.TButton", background=DANGER, foreground="#FFFFFF")
    style.map("Danger.TButton", background=[("active", "#B83238")])

    style.configure("TEntry", fieldbackground=PANEL, foreground=TEXT,
                    insertcolor=TEXT, borderwidth=1)
    style.configure("TCombobox", fieldbackground=PANEL, background=PANEL,
                    foreground=TEXT, arrowcolor=TEXT, borderwidth=1)
    style.map("TCombobox", fieldbackground=[("readonly", PANEL)],
              foreground=[("readonly", TEXT)])
    root.option_add("*TCombobox*Listbox.background", PANEL)
    root.option_add("*TCombobox*Listbox.foreground", TEXT)
    root.option_add("*TCombobox*Listbox.selectBackground", ACCENT)

    style.configure("TCheckbutton", background=CARD, foreground=TEXT)
    style.map("TCheckbutton", background=[("active", CARD)])
    style.configure("Switch.TCheckbutton", background=CARD, foreground=TEXT)

    style.configure("Horizontal.TProgressbar", troughcolor=TRACK,
                    background=ACCENT, borderwidth=0, thickness=10)

    style.configure("Treeview", background=PANEL, fieldbackground=PANEL,
                    foreground=TEXT, borderwidth=0, rowheight=28)
    style.configure("Treeview.Heading", background=PANEL_HOVER,
                    foreground=MUTED, relief="flat", font=(FONT_FAMILY, 9, "bold"))
    style.map("Treeview", background=[("selected", ACCENT_DARK)],
              foreground=[("selected", "#FFFFFF")])

    style.configure("Vertical.TScrollbar", background=PANEL_HOVER,
                    troughcolor=BG, borderwidth=0, arrowcolor=MUTED)


# ----------------------------------------------------------------- widgets
class Card(tk.Frame):
    """A rounded-looking panel (flat with a subtle border)."""

    def __init__(self, parent: tk.Widget, padding: int = 16, **kwargs) -> None:
        super().__init__(parent, bg=CARD, highlightbackground=BORDER,
                         highlightthickness=1, padx=padding, pady=padding, **kwargs)


class SidebarButton(tk.Frame):
    """Navigation button used in the left sidebar."""

    def __init__(self, parent: tk.Widget, text: str, icon: str,
                 command: Callable[[], None], active: bool = False) -> None:
        super().__init__(parent, bg=SIDEBAR, cursor="hand2")
        self.command = command
        self.active = active
        self.icon_label = tk.Label(self, text=icon, bg=SIDEBAR, fg=MUTED,
                                   font=(FONT_FAMILY, 13), width=2, anchor="w")
        self.text_label = tk.Label(self, text=text, bg=SIDEBAR, fg=MUTED,
                                   font=(FONT_FAMILY, 10, "bold"), anchor="w")
        self.icon_label.pack(side="left", padx=(14, 6), pady=11)
        self.text_label.pack(side="left", fill="x", expand=True, pady=11)
        for widget in (self, self.icon_label, self.text_label):
            widget.bind("<Button-1>", self._click)
            widget.bind("<Enter>", self._enter)
            widget.bind("<Leave>", self._leave)
        self.set_active(active)

    def _click(self, _event=None) -> None:
        self.command()

    def _enter(self, _event=None) -> None:
        if not self.active:
            self._set_colors(PANEL_HOVER, TEXT)

    def _leave(self, _event=None) -> None:
        if not self.active:
            self._set_colors(SIDEBAR, MUTED)

    def _set_colors(self, bg: str, fg: str) -> None:
        self.configure(bg=bg)
        self.icon_label.configure(bg=bg, fg=fg)
        self.text_label.configure(bg=bg, fg=fg)

    def set_active(self, active: bool) -> None:
        self.active = active
        if active:
            self._set_colors(ACCENT, "#FFFFFF")
        else:
            self._set_colors(SIDEBAR, MUTED)


def flat_button(parent: tk.Widget, text: str, command: Callable[[], None],
                bg: str = PANEL_HOVER, fg: str = TEXT, padx: int = 18,
                pady: int = 9, font=BODY_FONT) -> tk.Label:
    """A label that behaves like a flat button with hover feedback."""
    label = tk.Label(parent, text=text, bg=bg, fg=fg, font=font,
                     padx=padx, pady=pady, cursor="hand2")
    original = bg

    def enter(_event) -> None:
        label.configure(bg=ACCENT_DARK if bg != DANGER else "#B83238")

    def leave(_event) -> None:
        label.configure(bg=original)

    def click(_event) -> None:
        command()

    label.bind("<Enter>", enter)
    label.bind("<Leave>", leave)
    label.bind("<Button-1>", click)
    return label


def section_title(parent: tk.Widget, text: str, sub: str = "") -> tk.Frame:
    """A heading with an optional muted subtitle, padded vertically."""
    frame = tk.Frame(parent, bg=parent.cget("bg"))
    tk.Label(frame, text=text, bg=parent.cget("bg"), fg=TEXT,
             font=H2_FONT).pack(anchor="w")
    if sub:
        tk.Label(frame, text=sub, bg=parent.cget("bg"), fg=MUTED,
                 font=SMALL_FONT).pack(anchor="w", pady=(2, 0))
    return frame


def stat_card(parent: tk.Widget, title: str, value: str, sub: str = "",
              color: str = ACCENT) -> Card:
    """Small KPI card used on the dashboard and stats pages."""
    card = Card(parent, padding=14)
    tk.Label(card, text=title.upper(), bg=CARD, fg=MUTED,
             font=TINY_FONT).pack(anchor="w")
    tk.Label(card, text=value, bg=CARD, fg=color,
             font=(FONT_FAMILY, 18, "bold")).pack(anchor="w", pady=(4, 0))
    if sub:
        tk.Label(card, text=sub, bg=CARD, fg=MUTED,
                 font=SMALL_FONT).pack(anchor="w", pady=(2, 0))
    return card


class ProgressBar(tk.Canvas):
    """Simple flat progress bar drawn on a canvas."""

    def __init__(self, parent: tk.Widget, value: float = 0.0, maximum: float = 100.0,
                 color: str = ACCENT, height: int = 8, **kwargs) -> None:
        super().__init__(parent, height=height, bg=parent.cget("bg"),
                         highlightthickness=0, **kwargs)
        self.color = color
        self.value = value
        self.maximum = max(1e-9, maximum)
        self.bar_height = height
        self.bind("<Configure>", lambda _e: self.redraw())

    def set(self, value: float, maximum: float | None = None,
            color: str | None = None) -> None:
        self.value = value
        if maximum is not None:
            self.maximum = max(1e-9, maximum)
        if color is not None:
            self.color = color
        self.redraw()

    def redraw(self) -> None:
        self.delete("all")
        width = max(10, self.winfo_width())
        self.create_rectangle(0, 0, width, self.bar_height, fill=TRACK, width=0)
        ratio = 0.0 if self.maximum <= 0 else max(0.0, min(1.0, self.value / self.maximum))
        if ratio > 0:
            self.create_rectangle(0, 0, int(width * ratio), self.bar_height,
                                  fill=self.color, width=0)


def hbar_chart(parent: tk.Widget, items: Sequence[tuple[str, float, str]],
               label_width: int = 150, bar_height: int = 14,
               value_formatter: Callable[[float], str] | None = None) -> tk.Frame:
    """Horizontal bar chart.

    items: sequence of (label, value, colour)
    """
    frame = tk.Frame(parent, bg=parent.cget("bg"))
    if not items:
        tk.Label(frame, text="No data yet - use your PC for a while and come back.",
                 bg=parent.cget("bg"), fg=MUTED, font=SMALL_FONT).pack(anchor="w", pady=8)
        return frame
    peak = max((v for _l, v, _c in items), default=1.0) or 1.0
    fmt = value_formatter or (lambda v: f"{v:.0f}")

    for name, value, colour in items:
        row = tk.Frame(frame, bg=parent.cget("bg"))
        row.pack(fill="x", pady=3)
        tk.Label(row, text=name[:26], bg=parent.cget("bg"), fg=TEXT, font=SMALL_FONT,
                 width=26, anchor="w").pack(side="left")
        canvas = tk.Canvas(row, height=bar_height, bg=parent.cget("bg"),
                           highlightthickness=0)
        canvas.pack(side="left", fill="x", expand=True, padx=(4, 8))
        tk.Label(row, text=fmt(value), bg=parent.cget("bg"), fg=MUTED,
                 font=TINY_FONT, width=10, anchor="e").pack(side="right")

        def draw(event, c=canvas, v=value, col=colour, h=bar_height, p=peak):
            c.delete("all")
            w = max(10, event.width)
            c.create_rectangle(0, 0, w, h, fill=TRACK, width=0)
            fill_w = int(w * max(0.03, min(1.0, v / p)))
            c.create_rectangle(0, 0, fill_w, h, fill=col, width=0)

        canvas.bind("<Configure>", draw)
    return frame
