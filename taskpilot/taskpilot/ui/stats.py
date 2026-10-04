"""Usage statistics: most used / favourite / money-making apps and trends."""
from __future__ import annotations

import time
import tkinter as tk
from datetime import datetime
from tkinter import ttk

from ..storage import day_start, seconds_to_hms
from . import theme
from .base import Tab

RANGES = {
    "today": ("Today", lambda: (day_start(), time.time())),
    "week": ("7 days", lambda: (day_start() - 6 * 86400, time.time())),
    "month": ("30 days", lambda: (day_start() - 29 * 86400, time.time())),
}


class StatsTab(Tab):
    title = "Usage Stats"
    subtitle = "Where your time actually goes"

    def __init__(self, app, parent: tk.Widget) -> None:
        super().__init__(app, parent)
        self.range_key = "week"
        self._building = False

        canvas = tk.Canvas(self.frame, bg=theme.BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.frame, orient="vertical", command=canvas.yview)
        self.scrollable = tk.Frame(canvas, bg=theme.BG)
        self.scrollable.bind(
            "<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.scrollable, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        def _on_mousewheel(event):
            if getattr(event, "delta", 0):
                canvas.yview_scroll(-1 * (int(event.delta) // 120), "units")

        canvas.bind("<Enter>", lambda _e: canvas.bind_all("<MouseWheel>",
                                                          _on_mousewheel))
        canvas.bind("<Leave>", lambda _e: canvas.unbind_all("<MouseWheel>"))

        body = self.scrollable

        # ---- range selector
        header = tk.Frame(body, bg=theme.BG)
        header.pack(fill="x", pady=(0, 14))
        self.range_buttons: dict[str, tk.Label] = {}
        for key, (label, _fn) in RANGES.items():
            button = theme.flat_button(header, label,
                                       lambda k=key: self.set_range(k),
                                       bg=theme.PANEL_HOVER, font=theme.SMALL_FONT,
                                       padx=14, pady=6)
            button.pack(side="left", padx=(0, 8))
            self.range_buttons[key] = button

        # ---- KPI row
        self.kpi_row = tk.Frame(body, bg=theme.BG)
        self.kpi_row.pack(fill="x")
        for column in (0, 1, 2):
            self.kpi_row.grid_columnconfigure(column, weight=1, uniform="kpi")

        # ---- money making apps
        theme.section_title(
            body, "💰 Money-Making Apps",
            "Applications tagged as work — set their hourly value in Time Management"
        ).pack(anchor="w", pady=(26, 8))
        self.income_frame = tk.Frame(body, bg=theme.BG)
        self.income_frame.pack(fill="x")

        # ---- charts
        charts = tk.Frame(body, bg=theme.BG)
        charts.pack(fill="x", pady=(26, 0))
        charts.grid_columnconfigure(0, weight=3, uniform="chart")
        charts.grid_columnconfigure(1, weight=2, uniform="chart")

        left = tk.Frame(charts, bg=theme.BG)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        theme.section_title(left, "Most Used Applications",
                            "Total time in the selected range").pack(anchor="w",
                                                                     pady=(0, 10))
        self.top_chart = tk.Frame(left, bg=theme.BG)
        self.top_chart.pack(fill="x")

        right = tk.Frame(charts, bg=theme.BG)
        right.grid(row=0, column=1, sticky="nsew", padx=(10, 0))
        theme.section_title(right, "Time by Category").pack(anchor="w",
                                                            pady=(0, 10))
        self.category_chart = tk.Frame(right, bg=theme.BG)
        self.category_chart.pack(fill="x")

        # ---- favourites + daily trend
        bottom = tk.Frame(body, bg=theme.BG)
        bottom.pack(fill="x", pady=(26, 0))
        bottom.grid_columnconfigure(0, weight=1, uniform="bottom")
        bottom.grid_columnconfigure(1, weight=1, uniform="bottom")

        fav = tk.Frame(bottom, bg=theme.BG)
        fav.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        theme.section_title(fav, "❤️ Your Favourite Apps",
                            "Opened the most times").pack(anchor="w", pady=(0, 10))
        self.fav_frame = tk.Frame(fav, bg=theme.BG)
        self.fav_frame.pack(fill="x")

        trend = tk.Frame(bottom, bg=theme.BG)
        trend.grid(row=0, column=1, sticky="nsew", padx=(10, 0))
        theme.section_title(trend, "Daily Screen Time",
                            "Last 14 days").pack(anchor="w", pady=(0, 10))
        self.trend_frame = tk.Frame(trend, bg=theme.BG)
        self.trend_frame.pack(fill="x")

        # ---- recent sessions table
        theme.section_title(body, "Recent Sessions").pack(anchor="w",
                                                          pady=(26, 8))
        self._build_history_table(body)

    # ---------------------------------------------------------------- table
    def _build_history_table(self, parent: tk.Widget) -> None:
        columns = ("app", "category", "started", "duration")
        self.history = ttk.Treeview(parent, columns=columns, show="headings",
                                    height=8)
        for key, label, width in (("app", "Application", 180),
                                  ("category", "Category", 160),
                                  ("started", "Started", 170),
                                  ("duration", "Duration", 110)):
            self.history.heading(key, text=label)
            self.history.column(key, width=width, anchor="w")
        self.history.pack(fill="x")

    # ------------------------------------------------------------- helpers
    def set_range(self, key: str) -> None:
        self.range_key = key
        for other, button in self.range_buttons.items():
            button.configure(bg=theme.ACCENT_DARK if other == key
                             else theme.PANEL_HOVER)
        self.refresh()

    def _bounds(self) -> tuple[float, float]:
        return RANGES[self.range_key][1]()

    # ------------------------------------------------------------- refresh
    def refresh(self) -> None:
        if self._building:
            return
        self._building = True
        try:
            self._refresh_inner()
        finally:
            self._building = False

    def _refresh_inner(self) -> None:
        store = self.app.store
        cfg = self.app.config
        start, end = self._bounds()

        for key, button in self.range_buttons.items():
            button.configure(bg=theme.ACCENT_DARK if key == self.range_key
                             else theme.PANEL_HOVER)

        # ---------------- KPI cards
        for child in self.kpi_row.winfo_children():
            child.destroy()
        totals = store.totals(start, end)
        top = store.top_apps(start, end, limit=1)
        fav = store.most_opened(start, end, limit=1)

        theme.stat_card(self.kpi_row, "Total screen time",
                        seconds_to_hms(totals["total_sec"]),
                        f"{totals['sessions']} sessions · {totals['apps']} apps",
                        theme.ACCENT).grid(row=0, column=0, sticky="nsew",
                                           padx=(0, 8))
        theme.stat_card(self.kpi_row, "Most used app",
                        top[0]["app_name"] if top else "—",
                        seconds_to_hms(top[0]["total_sec"]) if top else "no data",
                        theme.SUCCESS).grid(row=0, column=1, sticky="nsew", padx=8)
        theme.stat_card(self.kpi_row, "Most opened app",
                        fav[0]["app_name"] if fav else "—",
                        f"{fav[0]['sessions']} switches" if fav else "no data",
                        theme.WARNING).grid(row=0, column=2, sticky="nsew",
                                            padx=(8, 0))

        # ---------------- money-making apps
        for child in self.income_frame.winfo_children():
            child.destroy()
        income = store.income_apps(start, end, limit=6)
        if not income:
            tk.Label(self.income_frame,
                     text="No money-making apps recorded yet. Tag your work apps "
                          "as 'Work / Money making' in Time Management.",
                     bg=theme.BG, fg=theme.MUTED, font=theme.SMALL_FONT,
                     wraplength=520, justify="left").pack(anchor="w")
        else:
            columns = ("app", "time", "sessions", "value")
            table = ttk.Treeview(self.income_frame, columns=columns,
                                 show="headings", height=min(7, len(income)))
            for key, label, width in (("app", "Application", 220),
                                      ("time", "Time spent", 130),
                                      ("sessions", "Sessions", 100),
                                      ("value", "Est. value", 130)):
                table.heading(key, text=label)
                table.column(key, width=width, anchor="w")
            rate = cfg.hourly_value("income")
            total_value = 0.0
            for row in income:
                hours = row["total_sec"] / 3600.0
                value = hours * rate
                total_value += value
                table.insert("", "end", values=(
                    row["app_name"], seconds_to_hms(row["total_sec"]),
                    row["sessions"],
                    f"{value:,.0f}" if rate > 0 else "set a rate"))
            table.pack(fill="x")
            summary = (f"Total: {seconds_to_hms(sum(r['total_sec'] for r in income))} "
                       f"· estimated value {total_value:,.0f} "
                       f"(at {rate:,.0f}/hour)" if rate > 0 else
                       f"Total: {seconds_to_hms(sum(r['total_sec'] for r in income))} "
                       f"· set an hourly value in Settings to estimate earnings")
            tk.Label(self.income_frame, text=summary, bg=theme.BG, fg=theme.MUTED,
                     font=theme.SMALL_FONT).pack(anchor="w", pady=(8, 0))

        # ---------------- top apps chart
        for child in self.top_chart.winfo_children():
            child.destroy()
        top_apps = store.top_apps(start, end, limit=8)
        items = [(row["app_name"], row["total_sec"],
                  cfg.category_color(row["category"]))
                 for row in top_apps]
        theme.hbar_chart(self.top_chart, items,
                         value_formatter=lambda v: seconds_to_hms(v)).pack(fill="x")

        # ---------------- category chart
        for child in self.category_chart.winfo_children():
            child.destroy()
        cat_totals = store.category_totals(start, end)
        cat_items = sorted(cat_totals.items(), key=lambda kv: kv[1], reverse=True)
        items = [(cfg.category_label(k), v, cfg.category_color(k))
                 for k, v in cat_items if v > 0]
        theme.hbar_chart(self.category_chart, items,
                         value_formatter=lambda v: seconds_to_hms(v)).pack(fill="x")

        # ---------------- favourites
        for child in self.fav_frame.winfo_children():
            child.destroy()
        favourites = store.most_opened(start, end, limit=5)
        if not favourites:
            tk.Label(self.fav_frame, text="No data yet.", bg=theme.BG,
                     fg=theme.MUTED, font=theme.SMALL_FONT).pack(anchor="w")
        else:
            for index, row in enumerate(favourites, start=1):
                line = tk.Frame(self.fav_frame, bg=theme.BG)
                line.pack(fill="x", pady=3)
                tk.Label(line, text=f"{index}.", bg=theme.BG, fg=theme.MUTED,
                         font=theme.BODY_FONT, width=3).pack(side="left")
                tk.Label(line, text=row["app_name"], bg=theme.BG, fg=theme.TEXT,
                         font=theme.BODY_FONT, anchor="w").pack(side="left",
                                                                fill="x",
                                                                expand=True)
                tk.Label(line, text=f"{row['sessions']}×", bg=theme.BG,
                         fg=theme.ACCENT, font=theme.SMALL_FONT).pack(side="right")

        # ---------------- daily trend
        for child in self.trend_frame.winfo_children():
            child.destroy()
        daily = store.daily_totals(days=14)
        self._draw_trend(self.trend_frame, daily)

        # ---------------- history table
        for item in self.history.get_children():
            self.history.delete(item)
        for record in self._recent_sessions(start, end):
            self.history.insert("", "end", values=record)

    def _recent_sessions(self, start: float, end: float, limit: int = 25):
        out = []
        for record in self.app.store.recent_sessions(start, end, limit):
            started = datetime.fromtimestamp(record["started_at"]).strftime("%d %b %H:%M")
            out.append((record["app_name"],
                        self.app.config.category_label(record["category"]),
                        started, seconds_to_hms(record["duration_sec"])))
        return out

    def _draw_trend(self, parent: tk.Widget, daily: list[dict]) -> None:
        canvas = tk.Canvas(parent, height=140, bg=theme.BG, highlightthickness=0)
        canvas.pack(fill="x")

        def draw(_event=None):
            canvas.delete("all")
            width = max(120, canvas.winfo_width())
            height = 140
            peak = max((d["total_sec"] for d in daily), default=1.0) or 1.0
            count = max(1, len(daily))
            slot = width / count
            bar_w = max(6, slot * 0.55)
            for index, entry in enumerate(daily):
                ratio = entry["total_sec"] / peak
                bar_h = int((height - 26) * ratio)
                x0 = index * slot + (slot - bar_w) / 2
                x1 = x0 + bar_w
                y1 = height - 18
                y0 = y1 - max(2, bar_h)
                colour = theme.ACCENT if index < count - 1 else theme.SUCCESS
                canvas.create_rectangle(x0, y0, x1, y1, fill=colour, width=0)
                if index % 3 == 0 or index == count - 1:
                    label = entry["day"][5:]  # MM-DD
                    canvas.create_text((x0 + x1) / 2, height - 8, text=label,
                                       fill=theme.MUTED, font=theme.TINY_FONT)
            canvas.create_text(width - 4, 10, text=f"peak {seconds_to_hms(peak)}",
                               fill=theme.MUTED, font=theme.TINY_FONT, anchor="e")

        canvas.bind("<Configure>", draw)
        draw()
