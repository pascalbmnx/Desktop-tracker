"""Foreground-window usage tracker.

A background thread samples the active window every few seconds, turns the
samples into usage sessions and writes them to the SQLite store.  It also
watches daily limits and Focus Mode restrictions and emits events that the
UI turns into notifications.

Windows-specific imports are isolated in ``_ActiveWindowSampler`` so the rest
of the program can be imported (and unit-tested) on any platform.
"""
from __future__ import annotations

import queue
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from .config import Config
from .storage import UsageStore, day_start


@dataclass
class TrackerEvent:
    kind: str  # app_change | limit_reached | blocked | idle_start | idle_end
    app_name: str = ""
    category: str = ""
    detail: str = ""
    ts: float = field(default_factory=time.time)


# ------------------------------------------------------------------ sampler
class _ActiveWindowSampler:
    """Returns (process_name, exe_path, window_title) for the foreground window."""

    def __init__(self) -> None:
        import psutil  # noqa: F401  - imported early to fail fast
        import win32api  # noqa: F401
        import win32gui  # noqa: F401
        import win32process  # noqa: F401

        self._psutil = psutil
        self._win32api = win32api
        self._win32gui = win32gui
        self._win32process = win32process
        self._proc_cache: dict[int, tuple[str, str]] = {}

    def current(self) -> tuple[str, str, str]:
        gui = self._win32gui
        hwnd = gui.GetForegroundWindow()
        if not hwnd:
            return ("", "", "")
        try:
            _, pid = self._win32process.GetWindowThreadProcessId(hwnd)
        except Exception:
            return ("", "", "")
        if not pid:
            return ("", "", "")
        name, path = self._process(pid)
        try:
            title = gui.GetWindowText(hwnd) or ""
        except Exception:
            title = ""
        return (name, path, title)

    def _process(self, pid: int) -> tuple[str, str]:
        cached = self._proc_cache.get(pid)
        if cached:
            return cached
        try:
            proc = self._psutil.Process(pid)
            name = proc.name()
            try:
                path = proc.exe()
            except Exception:
                path = ""
        except Exception:
            name, path = (f"pid-{pid}", "")
        self._proc_cache[pid] = (name, path)
        if len(self._proc_cache) > 512:
            self._proc_cache.clear()
        return name, path

    def idle_seconds(self) -> float:
        """Seconds since the last keyboard/mouse input."""
        try:
            last = self._win32api.GetLastInputInfo()
            now = self._win32api.GetTickCount()
            return max(0.0, (now - last) / 1000.0)
        except Exception:
            return 0.0


# ------------------------------------------------------------------- thread
class UsageTracker(threading.Thread):
    """Polls the foreground window and stores usage sessions."""

    def __init__(
        self,
        config: Config,
        store: UsageStore,
        events: "queue.Queue[TrackerEvent] | None" = None,
        on_event: Callable[[TrackerEvent], None] | None = None,
    ) -> None:
        super().__init__(daemon=True, name="TaskPilot-usage-tracker")
        self.config = config
        self.store = store
        self.events: "queue.Queue[TrackerEvent]" = events or queue.Queue()
        self.on_event = on_event

        self._stop_event = threading.Event()
        self._sampler: Any = None
        self._sampler_error: str = ""

        # Current session bookkeeping
        self._current: dict | None = None
        self._idle = False
        self._warned: set[str] = set()      # apps whose limit warning fired today
        self._blocked: set[str] = set()     # apps blocked today by focus mode
        self._warned_day: float = day_start()

    # ------------------------------------------------------------- control
    def stop(self, flush: bool = True) -> None:
        self._stop_event.set()
        if flush:
            self._flush()

    def run(self) -> None:  # pragma: no cover - needs a real desktop
        try:
            self._sampler = _ActiveWindowSampler()
        except Exception as exc:
            self._sampler_error = f"Usage tracking unavailable: {exc}"
            self._emit(TrackerEvent("error", detail=self._sampler_error))
            return

        poll = self._poll_interval()
        while not self._stop_event.is_set():
            started = time.time()
            try:
                self.tick()
            except Exception as exc:  # keep the loop alive
                self._emit(TrackerEvent("error", detail=str(exc)))
            elapsed = time.time() - started
            self._stop_event.wait(max(0.5, poll - elapsed))
        self._flush()

    def _poll_interval(self) -> float:
        try:
            return max(1.0, float(self.config.get("tracker.poll_seconds", 3)))
        except (TypeError, ValueError):
            return 3.0

    # ---------------------------------------------------------------- tick
    def tick(self, now: float | None = None) -> None:
        """One sampling step.  Exposed for tests."""
        now = now if now is not None else time.time()
        self._roll_day(now)

        if not self.config.get("tracker.enabled", True):
            if self._current:
                self._close_session(now)
            return

        if self._sampler is None:  # no desktop integration available
            return

        idle_limit = float(self.config.get("tracker.idle_threshold_seconds", 120) or 120)
        idle_for = self._sampler.idle_seconds()
        if idle_for >= idle_limit:
            if not self._idle:
                self._idle = True
                self._emit(TrackerEvent("idle_start"))
                self._close_session(now)
            return
        if self._idle:
            self._idle = False
            self._emit(TrackerEvent("idle_end"))

        name, path, title = self._sampler.current()
        if not name:
            self._close_session(now)
            return

        if self._current and self._current["app_name"] == name:
            self._current["ended_at"] = now
            self._current["window_title"] = title or self._current["window_title"]
            return

        self._close_session(now)
        category = self.config.category_for(name, path)
        self._current = {
            "app_name": name,
            "exe_path": path,
            "window_title": title,
            "category": category,
            "started_at": now,
            "ended_at": now,
        }
        self._emit(TrackerEvent("app_change", app_name=name, category=category))
        self._check_limits(name, category, now)

    # ------------------------------------------------------------- helpers
    def _roll_day(self, now: float) -> None:
        today = day_start(now)
        if today != self._warned_day:
            self._warned_day = today
            self._warned.clear()
            self._blocked.clear()

    def _close_session(self, now: float) -> None:
        cur = self._current
        self._current = None
        if not cur:
            return
        duration = now - cur["started_at"]
        if duration < 1.0:  # ignore one-frame focus flips
            return
        self.store.record(
            app_name=cur["app_name"],
            exe_path=cur["exe_path"],
            window_title=cur["window_title"],
            category=cur["category"],
            started_at=cur["started_at"],
            ended_at=now,
        )

    def _flush(self) -> None:
        try:
            self._close_session(time.time())
        except Exception:
            pass

    def _emit(self, event: TrackerEvent) -> None:
        try:
            self.events.put_nowait(event)
        except queue.Full:
            pass
        if self.on_event:
            try:
                self.on_event(event)
            except Exception:
                pass

    def _check_limits(self, app_name: str, category: str, now: float) -> None:
        """Warn when a daily limit is reached and block restricted categories."""
        # 1. per-application daily limit
        limit_min = self.config.limit_minutes_for(app_name)
        if limit_min > 0 and app_name not in self._warned:
            used = self.store.today_by_app().get(app_name, 0.0)
            if used >= limit_min * 60:
                self._warned.add(app_name)
                self.store.log_event("limit", f"{app_name} reached its {limit_min} min limit")
                self._emit(
                    TrackerEvent(
                        "limit_reached",
                        app_name=app_name,
                        category=category,
                        detail=f"{app_name} has reached today's {limit_min} minute limit.",
                    )
                )

        # 2. focus mode category blocking
        focus_on = bool(self.config.get("focus.enabled", False))
        if focus_on and category in self.config.blocked_categories():
            if app_name not in self._blocked:
                self._blocked.add(app_name)
                self.store.log_event("blocked", f"Focus mode: {app_name} ({category})")
                self._emit(
                    TrackerEvent(
                        "blocked",
                        app_name=app_name,
                        category=category,
                        detail=f"Focus Mode is on - {app_name} is in the "
                               f"'{self.config.category_label(category)}' category.",
                    )
                )
            if self.config.get("tracker.enforce_limits", False):
                self._terminate(app_name)

    @staticmethod
    def _terminate(app_name: str) -> None:  # pragma: no cover - destructive
        try:
            import psutil

            for proc in psutil.process_iter(["name"]):
                if proc.info.get("name", "").lower() == app_name.lower():
                    proc.terminate()
        except Exception:
            pass
