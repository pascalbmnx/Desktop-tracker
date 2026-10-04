"""SQLite persistence for application usage sessions.

Everything is stored in a single file (``usage.db``) next to the config.
Timestamps are Unix seconds (float), durations in seconds.
"""
from __future__ import annotations

import csv
import sqlite3
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from .config import data_dir

SCHEMA = """
CREATE TABLE IF NOT EXISTS usage_log (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    app_name     TEXT    NOT NULL,
    exe_path     TEXT    DEFAULT '',
    window_title TEXT    DEFAULT '',
    category     TEXT    DEFAULT 'other',
    started_at   REAL    NOT NULL,
    ended_at     REAL    NOT NULL,
    duration_sec REAL    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_usage_started ON usage_log(started_at);
CREATE INDEX IF NOT EXISTS idx_usage_app     ON usage_log(app_name);

CREATE TABLE IF NOT EXISTS events (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    ts      REAL NOT NULL,
    kind    TEXT NOT NULL,
    message TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts);
"""


def day_start(ts: float | None = None) -> float:
    """Local midnight for the given (or current) timestamp."""
    dt = datetime.fromtimestamp(ts if ts is not None else time.time())
    return datetime(dt.year, dt.month, dt.day).timestamp()


class UsageStore:
    """Small thread-safe wrapper over SQLite."""

    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or (data_dir() / "usage.db")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.executescript(SCHEMA)
            self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    # ------------------------------------------------------------- writing
    def record(
        self,
        app_name: str,
        exe_path: str = "",
        window_title: str = "",
        category: str = "other",
        started_at: float | None = None,
        ended_at: float | None = None,
    ) -> int:
        start = started_at if started_at is not None else time.time()
        end = ended_at if ended_at is not None else time.time()
        if end < start:
            start, end = end, start
        duration = round(end - start, 2)
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO usage_log "
                "(app_name, exe_path, window_title, category, started_at, ended_at, duration_sec) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (app_name, exe_path, window_title, category, start, end, duration),
            )
            self._conn.commit()
            return int(cur.lastrowid or 0)

    def log_event(self, kind: str, message: str = "") -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO events (ts, kind, message) VALUES (?, ?, ?)",
                (time.time(), kind, message),
            )
            self._conn.commit()

    def prune(self, older_than_days: int = 180) -> int:
        cutoff = time.time() - max(1, older_than_days) * 86400
        with self._lock:
            cur = self._conn.execute("DELETE FROM usage_log WHERE started_at < ?", (cutoff,))
            self._conn.execute("DELETE FROM events WHERE ts < ?", (cutoff,))
            self._conn.commit()
            return int(cur.rowcount or 0)

    def clear_all(self) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM usage_log")
            self._conn.execute("DELETE FROM events")
            self._conn.commit()

    # ------------------------------------------------------------- reading
    def _rows(self, sql: str, params: Iterable[Any] = ()) -> list[sqlite3.Row]:
        with self._lock:
            return list(self._conn.execute(sql, tuple(params)))

    def top_apps(
        self, start_ts: float = 0.0, end_ts: float | None = None, limit: int = 10
    ) -> list[dict]:
        end = end_ts if end_ts is not None else time.time()
        rows = self._rows(
            """
            SELECT app_name,
                   category,
                   SUM(duration_sec) AS total_sec,
                   COUNT(*)          AS sessions
            FROM usage_log
            WHERE started_at >= ? AND started_at <= ?
            GROUP BY app_name
            ORDER BY total_sec DESC
            LIMIT ?
            """,
            (start_ts, end, limit),
        )
        return [dict(r) for r in rows]

    def most_opened(
        self, start_ts: float = 0.0, end_ts: float | None = None, limit: int = 10
    ) -> list[dict]:
        """Apps switched to most often - the 'favourite' apps."""
        end = end_ts if end_ts is not None else time.time()
        rows = self._rows(
            """
            SELECT app_name,
                   category,
                   COUNT(*)          AS sessions,
                   SUM(duration_sec) AS total_sec
            FROM usage_log
            WHERE started_at >= ? AND started_at <= ?
            GROUP BY app_name
            ORDER BY sessions DESC
            LIMIT ?
            """,
            (start_ts, end, limit),
        )
        return [dict(r) for r in rows]

    def category_totals(
        self, start_ts: float = 0.0, end_ts: float | None = None
    ) -> dict[str, float]:
        end = end_ts if end_ts is not None else time.time()
        rows = self._rows(
            """
            SELECT category, SUM(duration_sec) AS total_sec
            FROM usage_log
            WHERE started_at >= ? AND started_at <= ?
            GROUP BY category
            """,
            (start_ts, end),
        )
        return {r["category"]: float(r["total_sec"] or 0.0) for r in rows}

    def income_apps(
        self, start_ts: float = 0.0, end_ts: float | None = None, limit: int = 15
    ) -> list[dict]:
        """Applications tagged as money-making ('income') ranked by time."""
        end = end_ts if end_ts is not None else time.time()
        rows = self._rows(
            """
            SELECT app_name,
                   SUM(duration_sec) AS total_sec,
                   COUNT(*)          AS sessions
            FROM usage_log
            WHERE started_at >= ? AND started_at <= ? AND category = 'income'
            GROUP BY app_name
            ORDER BY total_sec DESC
            LIMIT ?
            """,
            (start_ts, end, limit),
        )
        return [dict(r) for r in rows]

    def daily_totals(self, days: int = 14, end_ts: float | None = None) -> list[dict]:
        """Per-day total seconds for the last N days (oldest first)."""
        end = end_ts if end_ts is not None else time.time()
        start = day_start(end) - (max(1, days) - 1) * 86400
        rows = self._rows(
            """
            SELECT date(started_at, 'unixepoch', 'localtime') AS day,
                   SUM(duration_sec)                          AS total_sec
            FROM usage_log
            WHERE started_at >= ?
            GROUP BY day
            ORDER BY day
            """,
            (start,),
        )
        found = {r["day"]: float(r["total_sec"] or 0.0) for r in rows}
        out: list[dict] = []
        for offset in range(max(1, days)):
            day_ts = start + offset * 86400
            key = datetime.fromtimestamp(day_ts).strftime("%Y-%m-%d")
            out.append({"day": key, "total_sec": found.get(key, 0.0)})
        return out

    def today_by_app(self) -> dict[str, float]:
        rows = self._rows(
            """
            SELECT app_name, SUM(duration_sec) AS total_sec
            FROM usage_log
            WHERE started_at >= ?
            GROUP BY app_name
            """,
            (day_start(),),
        )
        return {r["app_name"]: float(r["total_sec"] or 0.0) for r in rows}

    def totals(self, start_ts: float = 0.0, end_ts: float | None = None) -> dict[str, Any]:
        end = end_ts if end_ts is not None else time.time()
        rows = self._rows(
            """
            SELECT COALESCE(SUM(duration_sec), 0) AS total_sec,
                   COUNT(*)                      AS sessions,
                   COUNT(DISTINCT app_name)      AS apps
            FROM usage_log
            WHERE started_at >= ? AND started_at <= ?
            """,
            (start_ts, end),
        )
        row = rows[0] if rows else None
        return {
            "total_sec": float(row["total_sec"] if row else 0.0),
            "sessions": int(row["sessions"] if row else 0),
            "apps": int(row["apps"] if row else 0),
        }

    def distinct_apps(self, start_ts: float = 0.0, end_ts: float | None = None) -> list[dict]:
        end = end_ts if end_ts is not None else time.time()
        rows = self._rows(
            """
            SELECT app_name,
                   category,
                   SUM(duration_sec) AS total_sec,
                   COUNT(*)          AS sessions
            FROM usage_log
            WHERE started_at >= ? AND started_at <= ?
            GROUP BY app_name
            ORDER BY app_name COLLATE NOCASE
            """,
            (start_ts, end),
        )
        return [dict(r) for r in rows]

    def recent_sessions(
        self, start_ts: float = 0.0, end_ts: float | None = None, limit: int = 25
    ) -> list[dict]:
        end = end_ts if end_ts is not None else time.time()
        rows = self._rows(
            """
            SELECT app_name, category, window_title, started_at, duration_sec
            FROM usage_log
            WHERE started_at >= ? AND started_at <= ?
            ORDER BY started_at DESC
            LIMIT ?
            """,
            (start_ts, end, limit),
        )
        return [dict(r) for r in rows]

    def app_history(self, app_name: str, limit: int = 30) -> list[dict]:
        rows = self._rows(
            """
            SELECT window_title, category, started_at, ended_at, duration_sec
            FROM usage_log
            WHERE app_name = ?
            ORDER BY started_at DESC
            LIMIT ?
            """,
            (app_name, limit),
        )
        return [dict(r) for r in rows]

    def events(self, limit: int = 40) -> list[dict]:
        rows = self._rows("SELECT * FROM events ORDER BY ts DESC LIMIT ?", (limit,))
        return [dict(r) for r in rows]

    # -------------------------------------------------------------- export
    def export_csv(self, path: str | Path, start_ts: float = 0.0,
                   end_ts: float | None = None) -> int:
        end = end_ts if end_ts is not None else time.time()
        rows = self._rows(
            """
            SELECT app_name, exe_path, window_title, category,
                   started_at, ended_at, duration_sec
            FROM usage_log
            WHERE started_at >= ? AND started_at <= ?
            ORDER BY started_at
            """,
            (start_ts, end),
        )
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(
                ["app_name", "exe_path", "window_title", "category",
                 "started_at_iso", "ended_at_iso", "duration_sec"]
            )
            for r in rows:
                writer.writerow(
                    [
                        r["app_name"],
                        r["exe_path"],
                        r["window_title"],
                        r["category"],
                        datetime.fromtimestamp(r["started_at"]).isoformat(sep=" "),
                        datetime.fromtimestamp(r["ended_at"]).isoformat(sep=" "),
                        r["duration_sec"],
                    ]
                )
        return len(rows)


def seconds_to_hms(seconds: float) -> str:
    """Format seconds as ``1h 02m`` / ``12m 30s`` / ``8s``."""
    seconds = int(max(0, seconds))
    hours, rem = divmod(seconds, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}h {minutes:02d}m"
    if minutes:
        return f"{minutes}m {secs:02d}s"
    return f"{secs}s"
