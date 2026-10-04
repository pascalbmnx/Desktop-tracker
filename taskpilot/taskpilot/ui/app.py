"""Main window: sidebar navigation + tab host + tracker event bridge."""
from __future__ import annotations

import queue
import tkinter as tk
from tkinter import messagebox
from typing import Type

from .. import __app_name__, __version__
from ..actions import POWER_ACTIONS
from ..config import Config
from ..storage import UsageStore, seconds_to_hms
from ..tracker import TrackerEvent, UsageTracker
from . import theme
from .base import Tab
from .dashboard import DashboardTab
from .settings import SettingsTab
from .stats import StatsTab
from .timeman import TimeManagementTab


class TaskPilotApp:
    def __init__(self) -> None:
        self.config = Config.load()
        self.store = UsageStore()
        self.events: "queue.Queue[TrackerEvent]" = queue.Queue()
        self.tracker = UsageTracker(self.config, self.store, events=self.events)

        self.root = tk.Tk()
        self.root.title(f"{__app_name__} {__version__}")
        self.root.configure(bg=theme.BG)
        width = int(self.config.get("ui.window_width", 1040))
        height = int(self.config.get("ui.window_height", 680))
        self.root.geometry(f"{width}x{height}")
        self.root.minsize(880, 560)

        theme.apply_theme(self.root)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        self._tabs: dict[str, Tab] = {}
        self._nav_buttons: dict[str, theme.SidebarButton] = {}
        self._toast_frame: tk.Frame | None = None

        self._build_layout()
        self._register_tabs()

        self.tracker.start()
        self.root.after(300, self._poll_events)
        self.root.after(1000, self._tick_clock)

    # ------------------------------------------------------------ layout
    def _build_layout(self) -> None:
        self.shell = tk.Frame(self.root, bg=theme.BG)
        self.shell.pack(fill="both", expand=True)

        # ---- sidebar
        self.sidebar = tk.Frame(self.shell, bg=theme.SIDEBAR, width=220)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        header = tk.Frame(self.sidebar, bg=theme.SIDEBAR)
        header.pack(fill="x", padx=16, pady=(22, 18))
        tk.Label(header, text="⚡", bg=theme.SIDEBAR, fg=theme.ACCENT,
                 font=(theme.FONT_FAMILY, 18)).pack(side="left")
        tk.Label(header, text=__app_name__, bg=theme.SIDEBAR, fg=theme.TEXT,
                 font=(theme.FONT_FAMILY, 14, "bold")).pack(side="left", padx=(8, 0))

        self.nav_frame = tk.Frame(self.sidebar, bg=theme.SIDEBAR)
        self.nav_frame.pack(fill="x", pady=(4, 0))

        self.sidebar_footer = tk.Frame(self.sidebar, bg=theme.SIDEBAR)
        self.sidebar_footer.pack(side="bottom", fill="x", padx=16, pady=16)
        self.tracker_status = tk.Label(
            self.sidebar_footer, text="", bg=theme.SIDEBAR, fg=theme.MUTED,
            font=theme.TINY_FONT, justify="left", anchor="w")
        self.tracker_status.pack(fill="x")

        # ---- content
        self.content = tk.Frame(self.shell, bg=theme.BG)
        self.content.pack(side="left", fill="both", expand=True)

        self.header = tk.Frame(self.content, bg=theme.BG)
        self.header.pack(fill="x", padx=28, pady=(24, 8))
        self.header_title = tk.Label(self.header, text="", bg=theme.BG,
                                     fg=theme.TEXT, font=theme.TITLE_FONT)
        self.header_title.pack(side="left")
        self.header_sub = tk.Label(self.header, text="", bg=theme.BG,
                                   fg=theme.MUTED, font=theme.SMALL_FONT)
        self.header_sub.pack(side="left", padx=(12, 0), pady=(6, 0))

        self.body = tk.Frame(self.content, bg=theme.BG)
        self.body.pack(fill="both", expand=True, padx=28, pady=(8, 22))

    def _register_tabs(self) -> None:
        specs: list[tuple[str, str, str, Type[Tab]]] = [
            ("dashboard", "Dashboard", "⌂", DashboardTab),
            ("stats", "Usage Stats", "📊", StatsTab),
            ("timeman", "Time Management", "⏱", TimeManagementTab),
            ("settings", "Settings", "⚙", SettingsTab),
        ]
        for key, label, icon, cls in specs:
            button = theme.SidebarButton(
                self.nav_frame, label, icon, command=lambda k=key: self.show_tab(k))
            button.pack(fill="x", pady=2)
            self._nav_buttons[key] = button

            tab = cls(self, self.body)
            tab.frame.place(relx=0, rely=0, relwidth=1, relheight=1)
            self._tabs[key] = tab

        self.show_tab("dashboard")

    # --------------------------------------------------------- navigation
    def show_tab(self, key: str) -> None:
        tab = self._tabs.get(key)
        if tab is None:
            return
        for other_key, other in self._tabs.items():
            other.frame.lower()
        tab.frame.lift()
        for other_key, button in self._nav_buttons.items():
            button.set_active(other_key == key)
        self.header_title.configure(text=tab.title)
        self.header_sub.configure(text=tab.subtitle)
        self.root.after(10, tab.on_show)

    def refresh_all(self) -> None:
        for tab in self._tabs.values():
            try:
                tab.refresh()
            except Exception:
                pass

    # ------------------------------------------------------------- toasts
    def toast(self, message: str, kind: str = "info", ms: int = 4200) -> None:
        colours = {"info": theme.ACCENT, "success": theme.SUCCESS,
                   "warning": theme.WARNING, "error": theme.DANGER}
        colour = colours.get(kind, theme.ACCENT)
        holder = tk.Frame(self.body, bg=colour)
        holder.place(relx=1.0, rely=1.0, x=-12, y=-12, anchor="se")
        inner = tk.Frame(holder, bg=colour, padx=2, pady=2)
        inner.pack(fill="both", expand=True)
        tk.Label(inner, text=message, bg=theme.CARD, fg=theme.TEXT,
                 font=theme.SMALL_FONT, padx=14, pady=10, wraplength=420,
                 justify="left").pack(fill="both")
        self.root.after(ms, holder.destroy)

    def ask_confirm(self, title: str, message: str) -> bool:
        return bool(messagebox.askyesno(title, message, parent=self.root))

    def notify(self, title: str, body: str) -> None:
        """Bring attention to a tracker event."""
        self.root.bell()
        self.toast(f"{title}\n{body}", kind="warning", ms=7000)

    # ------------------------------------------------------- tracker events
    def _poll_events(self) -> None:
        try:
            while True:
                event = self.events.get_nowait()
                self._handle_event(event)
        except queue.Empty:
            pass
        self.root.after(600, self._poll_events)

    def _handle_event(self, event: TrackerEvent) -> None:
        if event.kind == "limit_reached":
            self.notify("Time limit reached", event.detail)
            self._tabs["timeman"].refresh()
        elif event.kind == "blocked":
            self.notify("Focus Mode", event.detail)
        elif event.kind == "app_change":
            self._tabs["timeman"].refresh_live()
        elif event.kind == "error":
            self.tracker_status.configure(text=event.detail, fg=theme.DANGER)

    def _tick_clock(self) -> None:
        if self.tracker.is_alive():
            today = self.store.totals()
            self.tracker_status.configure(
                text=f"● tracking active\n"
                     f"today: {seconds_to_hms(today['total_sec'])} across "
                     f"{today['apps']} apps",
                fg=theme.MUTED)
        else:
            self.tracker_status.configure(
                text="○ tracker idle\n(usage history paused)", fg=theme.MUTED)
        self.root.after(5000, self._tick_clock)

    # ---------------------------------------------------------- lifecycle
    def _on_close(self) -> None:
        try:
            self.config.set("ui.window_width", self.root.winfo_width())
            self.config.set("ui.window_height", self.root.winfo_height())
        except Exception:
            pass
        try:
            self.tracker.stop()
        except Exception:
            pass
        try:
            self.store.close()
        except Exception:
            pass
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()
