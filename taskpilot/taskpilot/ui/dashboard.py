"""Dashboard: one-click actions, quick launch and today's snapshot."""
from __future__ import annotations

import time
import tkinter as tk

from .. import actions
from ..storage import day_start, seconds_to_hms
from . import theme
from .base import Tab


class DashboardTab(Tab):
    title = "Dashboard"
    subtitle = "One-click actions and a quick look at your day"

    def __init__(self, app, parent: tk.Widget) -> None:
        super().__init__(app, parent)
        self.frame.configure(bg=theme.BG)

        body = tk.Frame(self.frame, bg=theme.BG)
        body.pack(fill="both", expand=True)

        # ------------------------------------------------ action cards row
        row = tk.Frame(body, bg=theme.BG)
        row.pack(fill="x")
        for column in (0, 1, 2):
            row.grid_columnconfigure(column, weight=1, uniform="actions")

        self.bin_card = self._action_card(
            row, "🗑  Empty Recycle Bin",
            "Permanently delete everything in the bin",
            theme.WARNING, self._empty_bin)
        self.bin_card.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

        self.music_card = self._action_card(
            row, "🎵  Play My Music",
            "Open your playlist with the default player",
            theme.ACCENT, self._play_music)
        self.music_card.grid(row=0, column=1, sticky="nsew", padx=10)

        self.power_card = self._power_card(row)
        self.power_card.grid(row=0, column=2, sticky="nsew", padx=(10, 0))

        # -------------------------------------------------- quick launch
        quick_header = tk.Frame(body, bg=theme.BG)
        quick_header.pack(fill="x", pady=(24, 10))
        theme.section_title(quick_header, "Quick Launch",
                            "Click once to open an application").pack(side="left")
        theme.flat_button(quick_header, "+  Add app", self._add_app,
                          bg=theme.PANEL_HOVER, font=theme.SMALL_FONT,
                          padx=12, pady=6).pack(side="right")

        self.quick_frame = tk.Frame(body, bg=theme.BG)
        self.quick_frame.pack(fill="x")

        # --------------------------------------------------- today snapshot
        theme.section_title(body, "Today's Snapshot").pack(anchor="w", pady=(26, 10))
        self.snapshot = tk.Frame(body, bg=theme.BG)
        self.snapshot.pack(fill="x")
        for column in (0, 1, 2):
            self.snapshot.grid_columnconfigure(column, weight=1, uniform="snap")

    # ------------------------------------------------------------- widgets
    def _action_card(self, parent, title: str, sub: str, colour: str,
                     command) -> tk.Frame:
        card = theme.Card(parent, padding=18)
        bar = tk.Frame(card, bg=colour, height=4)
        bar.pack_propagate(False)
        bar.pack(fill="x", pady=(0, 12))
        title_lbl = tk.Label(card, text=title, bg=theme.CARD, fg=theme.TEXT,
                             font=theme.H2_FONT, anchor="w", justify="left")
        title_lbl.pack(anchor="w")
        tk.Label(card, text=sub, bg=theme.CARD, fg=theme.MUTED,
                 font=theme.SMALL_FONT, anchor="w", justify="left",
                 wraplength=240).pack(anchor="w", pady=(6, 14))
        theme.flat_button(card, "Run", command, bg=colour, fg="#FFFFFF",
                          font=(theme.FONT_FAMILY, 10, "bold")).pack(anchor="w")

        def enter(_e, c=card):
            c.configure(highlightbackground=colour)

        def leave(_e, c=card):
            c.configure(highlightbackground=theme.BORDER)

        card.bind("<Enter>", enter)
        card.bind("<Leave>", leave)
        return card

    def _power_card(self, parent) -> tk.Frame:
        card = theme.Card(parent, padding=18)
        bar = tk.Frame(card, bg=theme.DANGER, height=4)
        bar.pack_propagate(False)
        bar.pack(fill="x", pady=(0, 12))
        tk.Label(card, text="⏻  Power", bg=theme.CARD, fg=theme.TEXT,
                 font=theme.H2_FONT).pack(anchor="w")
        tk.Label(card, text="Shut down, restart, sleep or lock",
                 bg=theme.CARD, fg=theme.MUTED, font=theme.SMALL_FONT,
                 anchor="w", justify="left", wraplength=240).pack(anchor="w",
                                                                  pady=(6, 14))
        grid = tk.Frame(card, bg=theme.CARD)
        grid.pack(fill="x")
        for i, (key, label) in enumerate(actions.POWER_ACTIONS.items()):
            colour = theme.DANGER if key in ("shutdown", "restart") else theme.PANEL_HOVER
            button = theme.flat_button(grid, label, lambda k=key: self._power(k),
                                       bg=colour, fg="#FFFFFF",
                                       font=theme.SMALL_FONT, padx=10, pady=6)
            button.grid(row=i // 2, column=i % 2, sticky="ew", padx=2, pady=2)
        for column in (0, 1):
            grid.grid_columnconfigure(column, weight=1)
        return card

    # ------------------------------------------------------------- actions
    def _empty_bin(self) -> None:
        if self.app.config.get("general.confirm_destructive", True):
            if not self.app.ask_confirm(
                    "Empty Recycle Bin",
                    "This permanently deletes everything in the Recycle Bin.\n"
                    "Continue?"):
                return
        ok, message = actions.empty_recycle_bin()
        self.app.toast(message, kind="success" if ok else "error")
        if ok:
            self.app.store.log_event("action", "Recycle bin emptied")
            self.refresh()

    def _play_music(self) -> None:
        ok, message = actions.play_music(
            self.app.config.get("music.playlist_path", ""),
            self.app.config.get("music.player_path", ""))
        self.app.toast(message, kind="success" if ok else "warning")
        if not ok:
            self.app.show_tab("settings")

    def _power(self, key: str) -> None:
        label = actions.POWER_ACTIONS[key]
        if key in ("shutdown", "restart"):
            if not self.app.ask_confirm(
                    label, f"Are you sure you want to {label.lower()} the PC?"):
                return
        ok, message = actions.power_action(
            key, int(self.app.config.get("power.delay_seconds", 0) or 0))
        self.app.toast(message, kind="success" if ok else "error")
        if ok:
            self.app.store.log_event("action", label)

    def _launch(self, app_entry: dict) -> None:
        ok, message = actions.launch_app(app_entry.get("path", ""),
                                         app_entry.get("args", ""))
        self.app.toast(message, kind="success" if ok else "error")
        if ok:
            self.app.store.log_event("launch", app_entry.get("name", ""))

    def _add_app(self) -> None:
        self.app.show_tab("settings")

    # -------------------------------------------------------------- refresh
    def refresh(self) -> None:
        # quick launch grid
        for child in self.quick_frame.winfo_children():
            child.destroy()
        apps = self.app.config.apps
        if not apps:
            tk.Label(self.quick_frame, text="No quick-launch apps yet - add one in Settings.",
                     bg=theme.BG, fg=theme.MUTED, font=theme.SMALL_FONT).pack(anchor="w")
        else:
            columns = 4
            for index, entry in enumerate(apps):
                chip = tk.Frame(self.quick_frame, bg=theme.CARD,
                                highlightbackground=theme.BORDER,
                                highlightthickness=1, cursor="hand2")
                chip.grid(row=index // columns, column=index % columns,
                          sticky="nsew", padx=4, pady=4)
                self.quick_frame.grid_columnconfigure(index % columns, weight=1)
                colour = self.app.config.category_color(entry.get("category", "other"))
                dot = tk.Canvas(chip, width=8, height=8, bg=theme.CARD,
                                highlightthickness=0)
                dot.create_oval(2, 2, 8, 8, fill=colour, width=0)
                dot.pack(side="left", padx=(12, 8), pady=12)
                label = tk.Label(chip, text=entry.get("name", "?"),
                                 bg=theme.CARD, fg=theme.TEXT, font=theme.BODY_FONT,
                                 anchor="w")
                label.pack(side="left", fill="x", expand=True, pady=12)

                def launch(_e, entry=entry):
                    self._launch(entry)

                def enter(_e, widgets=(chip, dot, label)):
                    for widget in widgets:
                        widget.configure(bg=theme.PANEL_HOVER)

                def leave(_e, widgets=(chip, dot, label)):
                    for widget in widgets:
                        widget.configure(bg=theme.CARD)

                for widget in (chip, dot, label):
                    widget.bind("<Button-1>", launch)
                    widget.bind("<Enter>", enter)
                    widget.bind("<Leave>", leave)

        # snapshot cards
        for child in self.snapshot.winfo_children():
            child.destroy()

        today_start = day_start()
        totals = self.app.store.totals(today_start)
        top = self.app.store.top_apps(today_start, limit=1)
        by_app = self.app.store.today_by_app()
        blocked = self.app.config.blocked_categories()
        entertainment = sum(
            seconds for name, seconds in by_app.items()
            if self.app.config.category_for(name) in blocked
        )

        theme.stat_card(
            self.snapshot, "Screen time today", seconds_to_hms(totals["total_sec"]),
            f"{totals['sessions']} sessions · {totals['apps']} apps",
            theme.ACCENT).grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        theme.stat_card(
            self.snapshot, "Most used today",
            top[0]["app_name"] if top else "—",
            seconds_to_hms(top[0]["total_sec"]) if top else "no activity yet",
            theme.SUCCESS).grid(row=0, column=1, sticky="nsew", padx=8)

        theme.stat_card(
            self.snapshot, "Fun / games time", seconds_to_hms(entertainment),
            "keep it under your daily budget", theme.WARNING
        ).grid(row=0, column=2, sticky="nsew", padx=(8, 0))
