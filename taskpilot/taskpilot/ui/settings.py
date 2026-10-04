"""Settings: music, quick-launch apps, tracker, money value and data tools."""
from __future__ import annotations

import os
import subprocess
import sys
import tkinter as tk
from tkinter import filedialog, ttk

from .. import actions
from ..config import data_dir
from ..storage import seconds_to_hms
from . import theme
from .base import Tab


class SettingsTab(Tab):
    title = "Settings"
    subtitle = "Make TaskPilot fit the way you work"

    def __init__(self, app, parent: tk.Widget) -> None:
        super().__init__(app, parent)

        canvas = tk.Canvas(self.frame, bg=theme.BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.frame, orient="vertical", command=canvas.yview)
        self.scrollable = tk.Frame(canvas, bg=theme.BG)
        self.scrollable.bind(
            "<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.scrollable, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        body = self.scrollable
        self.vars: dict[str, tk.Variable] = {}

        # ---------------- music
        music = self._card(body, "🎵 Music Playlist",
                           "Used by the 'Play My Music' button on the dashboard")
        self._file_row(music, "Playlist / audio file / folder", "music.playlist_path",
                       browse="file")
        self._file_row(music, "Music player (optional)", "music.player_path",
                       browse="exe")
        theme.flat_button(music, "▶  Test playback", self._test_music,
                          bg=theme.ACCENT, fg="#FFFFFF",
                          font=theme.SMALL_FONT).pack(anchor="w", pady=(10, 0))

        # ---------------- quick launch apps
        apps_card = self._card(body, "🚀 Quick Launch Apps",
                               "Shown on the dashboard — one click to open")
        self.apps_form = tk.Frame(apps_card, bg=theme.CARD)
        self.apps_form.pack(fill="x", pady=(4, 10))
        self._build_apps_form()
        self.apps_list = tk.Frame(apps_card, bg=theme.CARD)
        self.apps_list.pack(fill="x")

        # ---------------- tracker
        tracker = self._card(body, "📊 Usage Tracker",
                             "Samples the active window to build your usage history")
        self._switch(tracker, "Track my application usage", "tracker.enabled")
        self._number(tracker, "Sample every (seconds)", "tracker.poll_seconds",
                     width=6)
        self._number(tracker, "Count me idle after (seconds)",
                     "tracker.idle_threshold_seconds", width=6)
        self._switch(tracker, "Automatically close apps over their limit",
                     "tracker.enforce_limits")

        # ---------------- money value
        money = self._card(body, "💰 Money Value",
                           "Used to estimate what your work time is worth")
        self._number(money, "Hourly value of work apps", "categories.income.hourly_value",
                     width=10, is_float=True)

        # ---------------- power
        power = self._card(body, "⏻ Power Actions",
                           "Delay before shutdown / restart (0 = immediate)")
        self._number(power, "Delay (seconds)", "power.delay_seconds", width=6)

        # ---------------- data
        data_card = self._card(body, "🗄 Data",
                               f"Stored locally in {data_dir()}")
        buttons = tk.Frame(data_card, bg=theme.CARD)
        buttons.pack(fill="x", pady=(6, 0))
        theme.flat_button(buttons, "Export usage as CSV", self._export_csv,
                          font=theme.SMALL_FONT, padx=12, pady=7).pack(side="left",
                                                                       padx=(0, 8))
        theme.flat_button(buttons, "Open data folder", self._open_data_dir,
                          font=theme.SMALL_FONT, padx=12, pady=7).pack(side="left",
                                                                       padx=(0, 8))
        theme.flat_button(buttons, "Delete all history", self._clear_data,
                          bg=theme.DANGER, fg="#FFFFFF",
                          font=theme.SMALL_FONT, padx=12, pady=7).pack(side="left")

        self.status = tk.Label(body, text="", bg=theme.BG, fg=theme.MUTED,
                               font=theme.SMALL_FONT)
        self.status.pack(anchor="w", pady=(16, 0))

    # ---------------------------------------------------------------- cards
    def _card(self, parent, title: str, sub: str) -> theme.Card:
        card = theme.Card(parent, padding=18)
        card.pack(fill="x", pady=(0, 16))
        tk.Label(card, text=title, bg=theme.CARD, fg=theme.TEXT,
                 font=theme.H2_FONT).pack(anchor="w")
        tk.Label(card, text=sub, bg=theme.CARD, fg=theme.MUTED,
                 font=theme.SMALL_FONT, wraplength=560, justify="left").pack(
            anchor="w", pady=(2, 12))
        return card

    def _file_row(self, parent, label: str, key: str, browse: str = "file") -> None:
        row = tk.Frame(parent, bg=theme.CARD)
        row.pack(fill="x", pady=4)
        tk.Label(row, text=label, bg=theme.CARD, fg=theme.TEXT,
                 font=theme.SMALL_FONT, width=32, anchor="w").pack(side="left")
        var = tk.StringVar(value=str(self.app.config.get(key, "") or ""))
        self.vars[key] = var
        entry = tk.Entry(row, textvariable=var, bg=theme.PANEL, fg=theme.TEXT,
                         insertbackground=theme.TEXT, relief="flat",
                         font=theme.SMALL_FONT)
        entry.pack(side="left", fill="x", expand=True, padx=(0, 8), ipady=4)
        entry.bind("<FocusOut>", lambda e, k=key, v=var: self._save_text(k, v))
        entry.bind("<Return>", lambda e, k=key, v=var: self._save_text(k, v))

        def browse_cmd(k=key, v=var, mode=browse):
            if mode == "exe":
                path = filedialog.askopenfilename(
                    title="Choose a program",
                    filetypes=[("Programs", "*.exe"), ("All files", "*.*")])
            elif mode == "folder":
                path = filedialog.askdirectory(title="Choose a folder")
            else:
                path = filedialog.askopenfilename(
                    title="Choose a playlist or audio file",
                    filetypes=[("Playlists / audio",
                                "*.m3u *.m3u8 *.mp3 *.wav *.flac *.aac *.ogg"),
                               ("All files", "*.*")])
            if path:
                v.set(path)
                self._save_text(k, v)

        theme.flat_button(row, "Browse…", browse_cmd, font=theme.SMALL_FONT,
                          padx=10, pady=5).pack(side="left")

    def _switch(self, parent, label: str, key: str) -> None:
        var = tk.BooleanVar(value=bool(self.app.config.get(key, False)))
        self.vars[key] = var
        box = tk.Checkbutton(parent, text=label, variable=var,
                             command=lambda k=key, v=var: self._save_bool(k, v),
                             bg=theme.CARD, fg=theme.TEXT,
                             selectcolor=theme.TRACK, activebackground=theme.CARD,
                             activeforeground=theme.TEXT, font=theme.SMALL_FONT)
        box.pack(anchor="w", pady=3)

    def _number(self, parent, label: str, key: str, width: int = 8,
                is_float: bool = False) -> None:
        row = tk.Frame(parent, bg=theme.CARD)
        row.pack(fill="x", pady=3)
        tk.Label(row, text=label, bg=theme.CARD, fg=theme.TEXT,
                 font=theme.SMALL_FONT, width=32, anchor="w").pack(side="left")
        current = self.app.config.get(key, 0)
        var = tk.StringVar(value=str(current))
        self.vars[key] = var
        entry = tk.Entry(row, textvariable=var, width=width, bg=theme.PANEL,
                         fg=theme.TEXT, insertbackground=theme.TEXT, relief="flat",
                         font=theme.SMALL_FONT)
        entry.pack(side="left", ipady=3)

        def save(_e=None, k=key, v=var, floating=is_float):
            text = v.get().strip() or "0"
            try:
                value = float(text) if floating else int(float(text))
            except ValueError:
                value = 0
            v.set(str(value))
            self._save(k, value)

        entry.bind("<FocusOut>", save)
        entry.bind("<Return>", save)

    def _save_text(self, key: str, var: tk.StringVar) -> None:
        self._save(key, var.get().strip())

    def _save_bool(self, key: str, var: tk.BooleanVar) -> None:
        self._save(key, bool(var.get()))

    def _save(self, key: str, value) -> None:
        self.app.config.set(key, value)
        self.status.configure(text=f"Saved {key} = {value}", fg=theme.SUCCESS)

    # ----------------------------------------------------------- apps form
    def _build_apps_form(self) -> None:
        form = self.apps_form
        for child in form.winfo_children():
            child.destroy()

        self.new_name = tk.StringVar()
        self.new_path = tk.StringVar()
        self.new_args = tk.StringVar()
        self.new_category = tk.StringVar(value="other")
        self.new_limit = tk.StringVar(value="0")

        grid = tk.Frame(form, bg=theme.CARD)
        grid.pack(fill="x")

        def labelled(label: str, var: tk.Variable, width: int = 18,
                     widget: str = "entry", values=None):
            cell = tk.Frame(grid, bg=theme.CARD)
            cell.pack(side="left", padx=(0, 10))
            tk.Label(cell, text=label, bg=theme.CARD, fg=theme.MUTED,
                     font=theme.TINY_FONT).pack(anchor="w")
            if widget == "combo":
                ttk.Combobox(cell, textvariable=var, values=values,
                             state="readonly", width=width).pack(anchor="w")
            else:
                tk.Entry(cell, textvariable=var, width=width, bg=theme.PANEL,
                         fg=theme.TEXT, insertbackground=theme.TEXT, relief="flat",
                         font=theme.SMALL_FONT).pack(anchor="w", ipady=3)

        labelled("Name", self.new_name, 14)
        labelled("Path to .exe / file", self.new_path, 30)
        labelled("Arguments", self.new_args, 12)
        labelled("Category", self.new_category, 14, widget="combo",
                 values=list(self.app.config.categories.keys()))
        labelled("Limit (min/day)", self.new_limit, 8)

        actions_frame = tk.Frame(grid, bg=theme.CARD)
        actions_frame.pack(side="left", padx=(6, 0))
        tk.Label(actions_frame, text=" ", bg=theme.CARD).pack()
        theme.flat_button(actions_frame, "Add", self._add_app, bg=theme.ACCENT,
                          fg="#FFFFFF", font=theme.SMALL_FONT,
                          padx=14, pady=5).pack(anchor="w")

    def _add_app(self) -> None:
        name = (self.new_name.get() or "").strip()
        path = (self.new_path.get() or "").strip()
        if not name or not path:
            self.app.toast("Please give the app a name and a path.",
                           kind="warning")
            return
        try:
            limit = max(0, int(float((self.new_limit.get() or "0").strip() or 0)))
        except (TypeError, ValueError):
            limit = 0
        if self.app.config.find_app(name):
            self.app.toast(f"'{name}' already exists.", kind="warning")
            return
        self.app.config.add_app({
            "name": name,
            "path": path,
            "args": (self.new_args.get() or "").strip(),
            "category": self.new_category.get(),
            "important": False,
            "daily_limit_minutes": limit,
        })
        self.app.toast(f"Added {name} to Quick Launch.", kind="success")
        self.new_name.set("")
        self.new_path.set("")
        self.new_args.set("")
        self.new_limit.set("0")
        self.refresh()
        self.app.refresh_all()

    def _remove_app(self, name: str) -> None:
        self.app.config.remove_app(name)
        self.app.toast(f"Removed {name}.", kind="info")
        self.refresh()
        self.app.refresh_all()

    # ------------------------------------------------------------- refresh
    def refresh(self) -> None:
        for child in self.apps_list.winfo_children():
            child.destroy()
        apps = self.app.config.apps
        if not apps:
            tk.Label(self.apps_list, text="No quick-launch apps configured yet.",
                     bg=theme.CARD, fg=theme.MUTED, font=theme.SMALL_FONT
                     ).pack(anchor="w")
            return
        for entry in apps:
            row = tk.Frame(self.apps_list, bg=theme.PANEL)
            row.pack(fill="x", pady=2)
            colour = self.app.config.category_color(entry.get("category", "other"))
            tk.Canvas(row, width=10, height=10, bg=theme.PANEL,
                      highlightthickness=0).pack(side="left", padx=(10, 4))
            row.winfo_children()[-1].create_oval(2, 2, 9, 9, fill=colour, width=0)
            tk.Label(row, text=entry.get("name", "?"), bg=theme.PANEL,
                     fg=theme.TEXT, font=theme.SMALL_FONT, width=18,
                     anchor="w").pack(side="left")
            tk.Label(row, text=entry.get("path", ""), bg=theme.PANEL,
                     fg=theme.MUTED, font=theme.TINY_FONT, anchor="w").pack(
                side="left", fill="x", expand=True, padx=6)
            limit = int(entry.get("daily_limit_minutes", 0) or 0)
            tk.Label(row, text=f"{limit} min/day" if limit else "no limit",
                     bg=theme.PANEL, fg=theme.MUTED, font=theme.TINY_FONT).pack(
                side="left", padx=8)
            remove = tk.Label(row, text="✕", bg=theme.PANEL, fg=theme.MUTED,
                              font=theme.SMALL_FONT, cursor="hand2", padx=10)
            remove.pack(side="right")
            remove.bind("<Button-1>",
                        lambda e, n=entry.get("name", ""): self._remove_app(n))

    # --------------------------------------------------------------- tools
    def _test_music(self) -> None:
        ok, message = actions.play_music(
            self.app.config.get("music.playlist_path", ""),
            self.app.config.get("music.player_path", ""))
        self.app.toast(message, kind="success" if ok else "warning")

    def _export_csv(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Export usage history",
            defaultextension=".csv",
            initialfile="taskpilot-usage.csv",
            filetypes=[("CSV", "*.csv")])
        if not path:
            return
        count = self.app.store.export_csv(path)
        self.app.toast(f"Exported {count} sessions to {os.path.basename(path)}.",
                       kind="success")

    def _open_data_dir(self) -> None:
        folder = str(data_dir())
        try:
            if sys.platform.startswith("win"):
                os.startfile(folder)  # noqa: S606
            else:
                subprocess.Popen(["xdg-open", folder])
        except Exception as exc:
            self.app.toast(f"Could not open folder: {exc}", kind="error")

    def _clear_data(self) -> None:
        if not self.app.ask_confirm(
                "Delete all history",
                "This permanently removes every recorded usage session.\n"
                "The action cannot be undone. Continue?"):
            return
        self.app.store.clear_all()
        self.app.store.log_event("action", "usage history cleared")
        self.app.toast("Usage history deleted.", kind="success")
        self.app.refresh_all()
