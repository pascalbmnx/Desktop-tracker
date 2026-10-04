"""Headless UI smoke test.

Installs a tkinter stub, then builds the whole application and refreshes every
page.  This catches import cycles, NameErrors and bad attribute references in
the GUI code without needing a display.

Run:  python3 tests/test_ui_smoke.py
"""
from __future__ import annotations

import os
import sys
import traceback
import types
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]

SCRATCH = PROJECT / ".openclaw" / "tmp" / "taskpilot-ui-smoke"
SCRATCH.mkdir(parents=True, exist_ok=True)
os.environ["TASKPILOT_HOME"] = str(SCRATCH)

sys.path.insert(0, str(PROJECT))


# --------------------------------------------------------------- tk stub
class _Anything:
    def __init__(self, *args, **kwargs):
        pass

    def __call__(self, *args, **kwargs):
        return _Anything()

    def __getattr__(self, name):
        return _Anything()

    def __setattr__(self, name, value):
        object.__setattr__(self, name, value)

    def __bool__(self):
        return True

    def __str__(self):
        return ""

    def __repr__(self):
        return "<stub>"

    def __int__(self):
        return 0

    def __float__(self):
        return 0.0

    def __len__(self):
        return 0

    def __iter__(self):
        return iter(())

    def __gt__(self, other):
        return True

    def __ge__(self, other):
        return True

    def __lt__(self, other):
        return False

    def __le__(self, other):
        return False

    def __eq__(self, other):
        return self is other

    def __hash__(self):
        return 0

    def __add__(self, other):
        return _Anything()

    __radd__ = __add__
    __sub__ = __add__
    __rsub__ = __add__
    __mul__ = __add__
    __rmul__ = __add__
    __truediv__ = __add__
    __rtruediv__ = __add__
    __floordiv__ = __add__
    __mod__ = __add__

    def __getitem__(self, key):
        return _Anything()

    def __setitem__(self, key, value):
        pass

    def __contains__(self, item):
        return False


class TclError(Exception):
    pass


class _Var:
    """Minimal but *real* replacement for tk.StringVar / BooleanVar / ..."""

    def __init__(self, master=None, value=None, **kwargs):
        self._value = value

    def get(self):
        return self._value

    def set(self, value):
        self._value = value

    def trace_add(self, *args, **kwargs):
        pass


class _StubModule(types.ModuleType):
    def __getattr__(self, attr):
        if attr == "TclError":
            return TclError
        if attr in ("Variable", "StringVar", "BooleanVar", "IntVar", "DoubleVar"):
            return _Var
        return type(attr, (_Anything,), {})


for _name in ("tkinter", "tkinter.ttk", "tkinter.messagebox",
              "tkinter.filedialog", "tkinter.font"):
    sys.modules.setdefault(_name, _StubModule(_name))
sys.modules["tkinter"].ttk = sys.modules["tkinter.ttk"]
sys.modules["tkinter"].messagebox = sys.modules["tkinter.messagebox"]
sys.modules["tkinter"].filedialog = sys.modules["tkinter.filedialog"]


# ------------------------------------------------------------------ checks
def main() -> int:
    failures: list[str] = []

    def step(label: str, fn) -> None:
        try:
            fn()
            print(f"  PASS  {label}")
        except Exception:
            failures.append(label)
            print(f"  FAIL  {label}")
            traceback.print_exc()

    print("Importing modules (catches circular imports)...")
    try:
        from taskpilot.ui.app import TaskPilotApp
        from taskpilot.tracker import TrackerEvent
        print("  PASS  all UI modules import")
    except Exception:
        traceback.print_exc()
        return 1

    print("Building the application...")
    app = {}

    def build():
        app["instance"] = TaskPilotApp()

    step("TaskPilotApp() constructs", build)
    if not app:
        return 1
    instance = app["instance"]

    # seed some usage history so the pages render non-empty charts
    import time

    now = time.time()
    for offset, (name, category, seconds) in enumerate([
            ("Code.exe", "income", 5400),
            ("Excel.exe", "income", 2700),
            ("Chrome.exe", "other", 3600),
            ("Spotify.exe", "entertainment", 1800),
            ("steam.exe", "entertainment", 2400)]):
        instance.store.record(name, category=category,
                              started_at=now - (offset + 1) * 3600,
                              ended_at=now - (offset + 1) * 3600 + seconds)
    instance.store.record("Code.exe", category="income",
                          started_at=now - 500, ended_at=now - 100)

    print("Rendering every page...")
    for key in ("dashboard", "stats", "timeman", "settings"):
        def show(k=key):
            instance.show_tab(k)

        step(f"show_tab({key!r})", show)

    for key, tab in instance._tabs.items():
        def refresh(t=tab, k=key):
            t.refresh()

        step(f"{key}.refresh()", refresh)

    print("Exercising action handlers...")
    step("dashboard._empty_bin()", instance._tabs["dashboard"]._empty_bin)
    step("dashboard._play_music()", instance._tabs["dashboard"]._play_music)
    step("dashboard._power('shutdown')",
         lambda: instance._tabs["dashboard"]._power("shutdown"))
    step("dashboard._launch()",
         lambda: instance._tabs["dashboard"]._launch(
             {"name": "Notepad", "path": "notepad.exe"}))
    step("stats.set_range('today')",
         lambda: instance._tabs["stats"].set_range("today"))
    step("stats.set_range('month')",
         lambda: instance._tabs["stats"].set_range("month"))
    step("timeman.refresh_live()", instance._tabs["timeman"].refresh_live)
    step("timeman._toggle_focus()", instance._tabs["timeman"]._toggle_focus)
    step("timeman._patch_app()",
         lambda: instance._tabs["timeman"]._patch_app("TestApp",
                                                      {"category": "income",
                                                       "daily_limit_minutes": 45}))
    step("settings._add_app()",
         lambda: (instance._tabs["settings"].new_name.set("SmokeApp"),
                  instance._tabs["settings"].new_path.set("C:/x.exe"),
                  instance._tabs["settings"]._add_app()))
    step("settings._remove_app('SmokeApp')",
         lambda: instance._tabs["settings"]._remove_app("SmokeApp"))
    step("settings.refresh()", instance._tabs["settings"].refresh)

    print("Exercising tracker event handling...")
    for kind in ("limit_reached", "blocked", "app_change", "error"):
        step(f"handle_event({kind!r})",
             lambda k=kind: instance._handle_event(
                 TrackerEvent(k, app_name="X", detail="test")))

    step("_tick_clock()", instance._tick_clock)
    step("toast()", lambda: instance.toast("hello", kind="success"))
    step("refresh_all()", instance.refresh_all)

    # cleanup a little
    try:
        instance.tracker.stop(flush=False)
        instance.store.close()
    except Exception:
        pass

    print()
    if failures:
        print(f"{len(failures)} step(s) failed: {failures}")
        return 1
    print("All UI smoke checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
