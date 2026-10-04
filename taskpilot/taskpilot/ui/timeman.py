"""Time management: categories, daily limits, focus mode and priorities."""
from __future__ import annotations

import time
import tkinter as tk
from tkinter import ttk

from ..storage import day_start, seconds_to_hms
from . import theme
from .base import Tab


class TimeManagementTab(Tab):
    title = "Time Management"
    subtitle = "Protect time for what matters, cap the rest"

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

        # ---------------- top row: focus mode + live activity
        top = tk.Frame(body, bg=theme.BG)
        top.pack(fill="x")
        top.grid_columnconfigure(0, weight=1, uniform="tm")
        top.grid_columnconfigure(1, weight=1, uniform="tm")

        self.focus_card = self._build_focus_card(top)
        self.focus_card.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

        self.live_card = self._build_live_card(top)
        self.live_card.grid(row=0, column=1, sticky="nsew", padx=(10, 0))

        # ---------------- app rules
        header = tk.Frame(body, bg=theme.BG)
        header.pack(fill="x", pady=(26, 8))
        theme.section_title(
            header, "Application Rules",
            "Set a category and a daily limit (0 = unlimited) for each app"
        ).pack(side="left")
        theme.flat_button(header, "+  Add app", self._add_app,
                          font=theme.SMALL_FONT, padx=12, pady=6).pack(side="right")

        self.rules_frame = tk.Frame(body, bg=theme.BG)
        self.rules_frame.pack(fill="x")

        # ---------------- legend
        tk.Label(body, text="Tip: mark your key apps as ★ Important so they stay "
                            "first on the dashboard and never get blocked.",
                 bg=theme.BG, fg=theme.MUTED, font=theme.SMALL_FONT,
                 justify="left").pack(anchor="w", pady=(18, 0))

    # ----------------------------------------------------------------- cards
    def _build_focus_card(self, parent: tk.Widget) -> theme.Card:
        card = theme.Card(parent, padding=18)
        tk.Label(card, text="🎯 Focus Mode", bg=theme.CARD, fg=theme.TEXT,
                 font=theme.H2_FONT).pack(anchor="w")
        self.focus_desc = tk.Label(
            card, text="", bg=theme.CARD, fg=theme.MUTED, font=theme.SMALL_FONT,
            wraplength=380, justify="left")
        self.focus_desc.pack(anchor="w", pady=(6, 12))

        controls = tk.Frame(card, bg=theme.CARD)
        controls.pack(fill="x")
        self.focus_var = tk.BooleanVar(value=bool(self.app.config.get("focus.enabled",
                                                                      False)))
        switch = tk.Checkbutton(controls, text="Block distracting apps",
                                variable=self.focus_var, command=self._toggle_focus,
                                bg=theme.CARD, fg=theme.TEXT, selectcolor=theme.TRACK,
                                activebackground=theme.CARD,
                                activeforeground=theme.TEXT,
                                font=theme.BODY_FONT)
        switch.pack(side="left")

        self.blocked_frame = tk.Frame(card, bg=theme.CARD)
        self.blocked_frame.pack(fill="x", pady=(12, 0))
        self._build_blocked_choices()
        return card

    def _build_blocked_choices(self) -> None:
        for child in self.blocked_frame.winfo_children():
            child.destroy()
        tk.Label(self.blocked_frame, text="Blocked categories:",
                 bg=theme.CARD, fg=theme.MUTED, font=theme.TINY_FONT
                 ).pack(anchor="w")
        row = tk.Frame(self.blocked_frame, bg=theme.CARD)
        row.pack(anchor="w", pady=(4, 0))
        blocked = set(self.app.config.blocked_categories())
        self._blocked_vars: dict[str, tk.BooleanVar] = {}
        for key, meta in self.app.config.categories.items():
            var = tk.BooleanVar(value=key in blocked)
            self._blocked_vars[key] = var
            box = tk.Checkbutton(row, text=meta.get("label", key), variable=var,
                                 command=self._save_blocked, bg=theme.CARD,
                                 fg=theme.TEXT, selectcolor=theme.TRACK,
                                 activebackground=theme.CARD,
                                 activeforeground=theme.TEXT,
                                 font=theme.SMALL_FONT)
            box.pack(side="left", padx=(0, 10))

    def _build_live_card(self, parent: tk.Widget) -> theme.Card:
        card = theme.Card(parent, padding=18)
        tk.Label(card, text="👀 Right Now", bg=theme.CARD, fg=theme.TEXT,
                 font=theme.H2_FONT).pack(anchor="w")
        self.live_app = tk.Label(card, text="Nothing tracked yet", bg=theme.CARD,
                                 fg=theme.ACCENT, font=(theme.FONT_FAMILY, 14, "bold"))
        self.live_app.pack(anchor="w", pady=(10, 2))
        self.live_detail = tk.Label(card, text="", bg=theme.CARD, fg=theme.MUTED,
                                    font=theme.SMALL_FONT, justify="left")
        self.live_detail.pack(anchor="w")
        self.live_bar = theme.ProgressBar(card, height=8)
        self.live_bar.pack(fill="x", pady=(14, 4))
        self.live_limit = tk.Label(card, text="", bg=theme.CARD, fg=theme.MUTED,
                                   font=theme.TINY_FONT)
        self.live_limit.pack(anchor="w")
        return card

    # --------------------------------------------------------------- actions
    def _toggle_focus(self) -> None:
        enabled = bool(self.focus_var.get())
        self.app.config.set("focus.enabled", enabled)
        self.app.store.log_event("focus", f"Focus mode {'on' if enabled else 'off'}")
        self.app.toast(f"Focus Mode {'enabled' if enabled else 'disabled'}.",
                       kind="success" if not enabled else "warning")
        self._update_focus_desc()

    def _save_blocked(self) -> None:
        keys = [k for k, v in self._blocked_vars.items() if v.get()]
        self.app.config.set("focus.blocked_categories", keys)
        self._update_focus_desc()

    def _update_focus_desc(self) -> None:
        if self.focus_var.get():
            names = ", ".join(self.app.config.category_label(k)
                              for k in self.app.config.blocked_categories()) or "nothing"
            self.focus_desc.configure(
                text=f"Active — {names} will be flagged while you use them.")
        else:
            self.focus_desc.configure(
                text="Off — distracting apps are tracked but not restricted.")

    def _add_app(self) -> None:
        self.app.show_tab("settings")

    # ---------------------------------------------------------- rules table
    def _build_rule_row(self, parent: tk.Widget, entry: dict, today_seconds: float):
        name = entry.get("name", "?")
        row = tk.Frame(parent, bg=theme.CARD, highlightbackground=theme.BORDER,
                       highlightthickness=1)
        row.pack(fill="x", pady=3)
        row.grid_columnconfigure(1, weight=1)

        important = bool(entry.get("important", False))
        star = tk.Label(row, text="★" if important else "☆", bg=theme.CARD,
                        fg=theme.WARNING if important else theme.MUTED,
                        font=(theme.FONT_FAMILY, 13), cursor="hand2", width=2)
        star.grid(row=0, column=0, padx=(12, 4), pady=10, sticky="n")
        star.bind("<Button-1>",
                  lambda e, n=name, s=star: self._toggle_important(n, s))

        info = tk.Frame(row, bg=theme.CARD)
        info.grid(row=0, column=1, sticky="nsew", padx=8, pady=10)
        tk.Label(info, text=name, bg=theme.CARD, fg=theme.TEXT,
                 font=theme.BODY_FONT).pack(anchor="w")
        limit = int(entry.get("daily_limit_minutes", 0) or 0)
        if limit > 0:
            remaining = max(0, limit * 60 - today_seconds)
            status = f"today {seconds_to_hms(today_seconds)} / {limit} min · " \
                     f"{seconds_to_hms(remaining)} left"
            colour = theme.WARNING if remaining < 300 else theme.MUTED
        else:
            status = f"today {seconds_to_hms(today_seconds)} · unlimited"
            colour = theme.MUTED
        tk.Label(info, text=status, bg=theme.CARD, fg=colour,
                 font=theme.TINY_FONT).pack(anchor="w", pady=(2, 0))

        # category selector
        categories = list(self.app.config.categories.keys())
        cat_var = tk.StringVar(value=entry.get("category", "other"))
        cat_box = ttk.Combobox(row, values=categories, textvariable=cat_var,
                               state="readonly", width=14)
        cat_box.grid(row=0, column=2, padx=6, pady=10)
        cat_box.bind("<<ComboboxSelected>>",
                     lambda e, n=name, v=cat_var: self._set_category(n, v.get()))

        # daily limit
        limit_frame = tk.Frame(row, bg=theme.CARD)
        limit_frame.grid(row=0, column=3, padx=6, pady=10)
        limit_var = tk.StringVar(value=str(limit))
        limit_entry = tk.Entry(limit_frame, textvariable=limit_var, width=5,
                               bg=theme.PANEL, fg=theme.TEXT,
                               insertbackground=theme.TEXT,
                               relief="flat", font=theme.SMALL_FONT)
        limit_entry.pack(side="left")
        tk.Label(limit_frame, text="min/day", bg=theme.CARD, fg=theme.MUTED,
                 font=theme.TINY_FONT).pack(side="left", padx=(4, 0))
        limit_entry.bind("<FocusOut>",
                         lambda e, n=name, v=limit_var: self._set_limit(n, v))
        limit_entry.bind("<Return>",
                         lambda e, n=name, v=limit_var: self._set_limit(n, v))

        remove = tk.Label(row, text="✕", bg=theme.CARD, fg=theme.MUTED,
                          font=theme.BODY_FONT, cursor="hand2", padx=8)
        remove.grid(row=0, column=4, padx=(4, 10))
        remove.bind("<Button-1>", lambda e, n=name: self._remove_app(n))

    def _toggle_important(self, name: str, star: tk.Label) -> None:
        entry = self.app.config.find_app(name) or {"name": name}
        new_value = not bool(entry.get("important", False))
        self._patch_app(name, {"important": new_value})
        star.configure(text="★" if new_value else "☆",
                       fg=theme.WARNING if new_value else theme.MUTED)

    def _set_category(self, name: str, category: str) -> None:
        self._patch_app(name, {"category": category})
        self.app.toast(f"{name} → {self.app.config.category_label(category)}",
                       kind="success")
        self.refresh()

    def _set_limit(self, name: str, var: tk.StringVar) -> None:
        try:
            value = max(0, int(float(var.get().strip() or 0)))
        except ValueError:
            var.set("0")
            value = 0
        self._patch_app(name, {"daily_limit_minutes": value})
        self.refresh()

    def _patch_app(self, name: str, patch: dict) -> None:
        self.app.config.upsert_app(name, patch)

    def _remove_app(self, name: str) -> None:
        if self.app.ask_confirm("Remove rule",
                                f"Stop tracking rules for '{name}'?\n"
                                f"Past usage history is kept."):
            self.app.config.remove_app(name)
            self.refresh()

    # -------------------------------------------------------------- refresh
    def refresh_live(self) -> None:
        current = self.app.tracker._current
        if not current:
            self.live_app.configure(text="Nothing tracked right now")
            self.live_detail.configure(text="Idle or no foreground window.")
            self.live_bar.set(0, 100)
            self.live_limit.configure(text="")
            return

        name = current["app_name"]
        category = current["category"]
        session = time.time() - current["started_at"]
        today_total = self.app.store.today_by_app().get(name, 0.0) + session
        limit_min = self.app.config.limit_minutes_for(name)

        self.live_app.configure(text=name)
        self.live_detail.configure(
            text=f"{self.app.config.category_label(category)} · "
                 f"session {seconds_to_hms(session)} · "
                 f"today {seconds_to_hms(today_total)}")
        if limit_min > 0:
            colour = theme.DANGER if today_total > limit_min * 60 else theme.ACCENT
            self.live_bar.set(today_total, limit_min * 60, colour)
            self.live_limit.configure(
                text=f"daily limit {limit_min} min · "
                     f"{seconds_to_hms(max(0, limit_min * 60 - today_total))} left")
        else:
            self.live_bar.set(0, 100)
            self.live_limit.configure(text="no daily limit set")

    def refresh(self) -> None:
        self._update_focus_desc()
        for child in self.rules_frame.winfo_children():
            child.destroy()

        today = self.app.store.today_by_app()
        entries = sorted(
            self.app.config.apps,
            key=lambda e: (not e.get("important", False),
                           e.get("name", "").lower()))
        if not entries:
            tk.Label(self.rules_frame,
                     text="No rules yet. Add the apps you care about and give "
                          "each one a category and a limit.",
                     bg=theme.BG, fg=theme.MUTED, font=theme.SMALL_FONT,
                     wraplength=520, justify="left").pack(anchor="w")
        for entry in entries:
            self._build_rule_row(self.rules_frame, entry,
                                 today.get(entry.get("name", ""), 0.0))
        self.refresh_live()
