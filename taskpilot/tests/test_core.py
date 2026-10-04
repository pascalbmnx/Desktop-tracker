"""Tests for the TaskPilot core (no GUI, no Windows APIs required).

Run with:  python -m pytest tests -q   or   python tests/test_core.py
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Keep every test artefact out of the user's real data directory.
SCRATCH = Path(os.environ.get(
    "TASKPILOT_HOME", ROOT / ".openclaw" / "tmp" / "taskpilot-tests"))
SCRATCH.mkdir(parents=True, exist_ok=True)
os.environ["TASKPILOT_HOME"] = str(SCRATCH)

from taskpilot.config import Config, default_config  # noqa: E402
from taskpilot.storage import UsageStore, day_start, seconds_to_hms  # noqa: E402
from taskpilot.tracker import UsageTracker  # noqa: E402


# --------------------------------------------------------------------- utils
def fresh_store(name: str) -> UsageStore:
    path = SCRATCH / f"{name}.db"
    if path.exists():
        path.unlink()
    return UsageStore(db_path=path)


def fresh_config(name: str, data: dict | None = None) -> Config:
    return Config(path=SCRATCH / f"{name}.json", data=data or default_config())


# -------------------------------------------------------------------- config
def test_config_defaults():
    cfg = fresh_config("defaults")
    assert cfg.get("tracker.poll_seconds") == 3
    assert cfg.get("music.playlist_path") == ""
    assert "entertainment" in cfg.categories
    assert cfg.category_restricted("entertainment") is True
    assert cfg.category_restricted("income") is False


def test_config_get_set_and_persist():
    path = SCRATCH / "persist.json"
    if path.exists():
        path.unlink()
    cfg = Config(path=path)
    cfg.set("music.playlist_path", r"C:\Music\my.m3u8")
    cfg.add_app({"name": "Word", "path": "winword.exe", "category": "income"})

    reloaded = Config.load(path)
    assert reloaded.get("music.playlist_path") == r"C:\Music\my.m3u8"
    assert reloaded.find_app("word")["category"] == "income"
    assert reloaded.limit_minutes_for("Word") == 0


def test_category_resolution():
    cfg = fresh_config("cats")
    cfg.add_app({"name": "Photoshop", "path": "photoshop.exe",
                 "category": "income", "daily_limit_minutes": 30})
    assert cfg.category_for("Photoshop.exe") == "income"
    assert cfg.limit_minutes_for("Photoshop") == 30
    # heuristic fallback
    assert cfg.category_for("steam.exe") == "entertainment"
    assert cfg.category_for("totally-unknown-app") == "other"


# ------------------------------------------------------------------- storage
def test_record_and_top_apps():
    store = fresh_store("top")
    now = time.time()
    store.record("Code.exe", category="income", started_at=now - 3600,
                 ended_at=now - 2400)
    store.record("Code.exe", category="income", started_at=now - 2000,
                 ended_at=now - 1600)
    store.record("Spotify.exe", category="entertainment", started_at=now - 1500,
                 ended_at=now - 1000)

    top = store.top_apps(0, now)
    assert top[0]["app_name"] == "Code.exe"
    assert top[0]["total_sec"] == 1600
    assert top[0]["sessions"] == 2

    totals = store.totals(0, now)
    assert totals["apps"] == 2
    assert totals["sessions"] == 3


def test_most_opened_and_income():
    store = fresh_store("favourite")
    now = time.time()
    for i in range(4):
        store.record("Chrome.exe", category="other", started_at=now - 1000 + i * 10,
                     ended_at=now - 995 + i * 10)
    store.record("Excel.exe", category="income", started_at=now - 500,
                 ended_at=now - 100)

    fav = store.most_opened(0, now, limit=1)
    assert fav[0]["app_name"] == "Chrome.exe"
    assert fav[0]["sessions"] == 4

    income = store.income_apps(0, now)
    assert [r["app_name"] for r in income] == ["Excel.exe"]
    assert income[0]["total_sec"] == 400


def test_category_totals_and_today():
    store = fresh_store("cats")
    now = time.time()
    store.record("A", category="income", started_at=now - 3000, ended_at=now - 2000)
    store.record("B", category="entertainment", started_at=now - 1900,
                 ended_at=now - 1400)
    totals = store.category_totals(0, now)
    assert totals["income"] == 1000
    assert totals["entertainment"] == 500

    today = store.today_by_app()
    assert set(today) == {"A", "B"}


def test_daily_totals_are_complete():
    store = fresh_store("daily")
    now = time.time()
    store.record("A", started_at=now - 60, ended_at=now)
    days = store.daily_totals(days=7, end_ts=now)
    assert len(days) == 7
    assert days[-1]["total_sec"] >= 59          # today has the session
    assert all(d["total_sec"] == 0 for d in days[:-1])


def test_export_and_prune():
    store = fresh_store("export")
    now = time.time()
    store.record("A", category="income", started_at=now - 100, ended_at=now)
    out = SCRATCH / "export.csv"
    assert store.export_csv(out) == 1
    text = out.read_text(encoding="utf-8")
    assert "app_name" in text and "A" in text

    store.record("Old", started_at=now - 400 * 86400, ended_at=now - 400 * 86400 + 10)
    removed = store.prune(older_than_days=180)
    assert removed == 1
    assert store.totals(0, now)["sessions"] == 1


def test_recent_sessions_order():
    store = fresh_store("recent")
    now = time.time()
    store.record("Newest", started_at=now - 10, ended_at=now)
    store.record("Oldest", started_at=now - 500, ended_at=now - 400)
    rows = store.recent_sessions(0, now)
    assert rows[0]["app_name"] == "Newest"


# --------------------------------------------------------------- formatting
def test_seconds_to_hms():
    assert seconds_to_hms(0) == "0s"
    assert seconds_to_hms(45) == "45s"
    assert seconds_to_hms(90) == "1m 30s"
    assert seconds_to_hms(3725) == "1h 02m"


def test_day_start_is_midnight():
    now = time.time()
    start = day_start(now)
    assert 0 <= now - start < 86400
    assert start == day_start(start + 60)


# ------------------------------------------------------------------ tracker
class FakeSampler:
    """Pretends to be the Windows foreground-window sampler."""

    def __init__(self):
        self.app = ("Code.exe", r"C:\VSCode\Code.exe", "main.py - VSCode")
        self.idle_for = 0.0

    def current(self):
        return self.app

    def idle_seconds(self):
        return self.idle_for


def make_tracker(cfg: Config, store: UsageStore) -> UsageTracker:
    tracker = UsageTracker(cfg, store)
    tracker._sampler = FakeSampler()
    return tracker


def test_tracker_records_sessions():
    cfg = fresh_config("track")
    cfg.set("tracker.idle_threshold_seconds", 120, save=False)
    store = fresh_store("track")
    tracker = make_tracker(cfg, store)

    t = time.time()
    tracker.tick(t)                     # opens Code.exe
    tracker.tick(t + 20)                # same app, extends session
    assert tracker._current is not None

    tracker._sampler.app = ("Spotify.exe", r"C:\Spotify\Spotify.exe", "Playlist")
    tracker.tick(t + 30)                # switch -> closes previous session
    rows = store.recent_sessions(0, t + 120)
    assert rows[0]["app_name"] == "Code.exe"
    assert rows[0]["duration_sec"] == 30

    tracker._close_session(t + 60)      # flush the current (Spotify) session
    tracker.stop(flush=False)
    names = [r["app_name"] for r in store.recent_sessions(0, t + 120)]
    assert names[0] == "Spotify.exe"
    assert store.totals(0, t + 120)["sessions"] == 2


def test_tracker_ignores_pauses_and_idle():
    cfg = fresh_config("idle")
    cfg.set("tracker.idle_threshold_seconds", 120, save=False)
    store = fresh_store("idle")
    tracker = make_tracker(cfg, store)

    t = time.time()
    tracker.tick(t)
    tracker._sampler.idle_for = 500
    tracker.tick(t + 60)                # idle -> session closed
    assert tracker._current is None
    assert store.totals(0, t + 100)["sessions"] == 1

    tracker._sampler.idle_for = 0
    tracker._sampler.app = ("Chrome.exe", "", "New tab")
    tracker.tick(t + 70)                # back to work
    assert tracker._current["app_name"] == "Chrome.exe"
    tracker.stop(flush=False)


def test_tracker_warns_on_daily_limit():
    cfg = fresh_config("limit")
    cfg.set("tracker.idle_threshold_seconds", 120, save=False)
    cfg.add_app({"name": "Game.exe", "path": "game.exe",
                 "category": "entertainment", "daily_limit_minutes": 5})
    store = fresh_store("limit")
    store.record("Game.exe", category="entertainment", started_at=time.time() - 600,
                 ended_at=time.time() - 300)   # 5 minutes already used

    tracker = make_tracker(cfg, store)
    tracker._sampler.app = ("Game.exe", "game.exe", "Game")
    tracker.tick(time.time())

    events = []
    while not tracker.events.empty():
        events.append(tracker.events.get_nowait())
    assert any(e.kind == "limit_reached" for e in events)


def test_focus_mode_flags_blocked_category():
    cfg = fresh_config("focus")
    cfg.set("tracker.idle_threshold_seconds", 120, save=False)
    cfg.set("focus.enabled", True, save=False)
    cfg.set("focus.blocked_categories", ["entertainment"], save=False)
    store = fresh_store("focus")

    tracker = make_tracker(cfg, store)
    tracker._sampler.app = ("Minecraft.exe", "minecraft.exe", "Minecraft")
    tracker.tick(time.time())

    events = []
    while not tracker.events.empty():
        events.append(tracker.events.get_nowait())
    assert any(e.kind == "blocked" for e in events)


def test_tracker_disabled_records_nothing():
    cfg = fresh_config("off")
    cfg.set("tracker.enabled", False, save=False)
    store = fresh_store("off")
    tracker = make_tracker(cfg, store)
    tracker.tick(time.time())
    tracker.tick(time.time() + 30)
    assert store.totals(0, time.time() + 60)["sessions"] == 0


# --------------------------------------------------------------------- main
if __name__ == "__main__":
    failures = 0
    tests = [(name, fn) for name, fn in sorted(globals().items())
             if name.startswith("test_") and callable(fn)]
    for name, fn in tests:
        try:
            fn()
            print(f"  PASS  {name}")
        except AssertionError as exc:
            failures += 1
            print(f"  FAIL  {name}: {exc}")
        except Exception as exc:  # pragma: no cover
            failures += 1
            print(f"  ERROR {name}: {type(exc).__name__}: {exc}")
    print(f"\n{len(tests) - failures}/{len(tests)} tests passed")
    sys.exit(1 if failures else 0)
