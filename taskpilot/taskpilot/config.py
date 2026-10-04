"""Configuration storage for TaskPilot.

The config lives in a single JSON file so it is easy to inspect and edit by hand.

Location
--------
Windows  : %APPDATA%\\TaskPilot\\config.json
Override : set the TASKPILOT_HOME environment variable
"""
from __future__ import annotations

import copy
import json
import os
import sys
import threading
from pathlib import Path
from typing import Any

APP_NAME = "TaskPilot"
CONFIG_VERSION = 1

# Categories the user can assign to an application.
DEFAULT_CATEGORIES: dict[str, dict[str, Any]] = {
    "income": {
        "label": "Work / Money making",
        "color": "#2FBF71",
        "hourly_value": 0.0,
        "restricted": False,
    },
    "study": {
        "label": "Study / Learning",
        "color": "#4F8CFF",
        "hourly_value": 0.0,
        "restricted": False,
    },
    "communication": {
        "label": "Communication",
        "color": "#9B6BFF",
        "hourly_value": 0.0,
        "restricted": False,
    },
    "entertainment": {
        "label": "Entertainment / Games",
        "color": "#F5A623",
        "hourly_value": 0.0,
        "restricted": True,
    },
    "other": {
        "label": "Other",
        "color": "#8A93A6",
        "hourly_value": 0.0,
        "restricted": False,
    },
}

# Heuristic used only when an app has never been categorised by the user.
# Key = a substring of the process name, lower case.
AUTO_CATEGORY_RULES: list[tuple[str, str]] = [
    ("steam", "entertainment"),
    ("epicgames", "entertainment"),
    ("minecraft", "entertainment"),
    ("valorant", "entertainment"),
    ("league", "entertainment"),
    ("dota", "entertainment"),
    ("csgo", "entertainment"),
    ("cs2", "entertainment"),
    ("roblox", "entertainment"),
    ("spotify", "entertainment"),
    ("vlc", "entertainment"),
    ("netflix", "entertainment"),
    ("code", "income"),
    ("devenv", "income"),
    ("pycharm", "income"),
    ("idea64", "income"),
    ("webstorm", "income"),
    ("android studio", "income"),
    ("excel", "income"),
    ("winword", "income"),
    ("powerpnt", "income"),
    ("outlook", "income"),
    ("photoshop", "income"),
    ("blender", "income"),
    ("figma", "income"),
    ("autocad", "income"),
    ("teams", "communication"),
    ("slack", "communication"),
    ("discord", "communication"),
    ("zoom", "communication"),
    ("telegram", "communication"),
    ("whatsapp", "communication"),
    ("notepad", "study"),
    ("anki", "study"),
    ("pdf", "study"),
    ("acrord", "study"),
    ("sumatra", "study"),
]

# Applications offered on the dashboard the first time the program runs.
DEFAULT_APPS: list[dict[str, Any]] = [
    {
        "name": "Notepad",
        "path": r"%WINDIR%\System32\notepad.exe",
        "args": "",
        "category": "study",
        "important": False,
        "daily_limit_minutes": 0,
    },
    {
        "name": "Calculator",
        "path": r"%WINDIR%\System32\calc.exe",
        "args": "",
        "category": "other",
        "important": False,
        "daily_limit_minutes": 0,
    },
    {
        "name": "File Explorer",
        "path": r"%WINDIR%\explorer.exe",
        "args": "",
        "category": "other",
        "important": False,
        "daily_limit_minutes": 0,
    },
]


def is_windows() -> bool:
    return sys.platform.startswith("win")


def data_dir() -> Path:
    """Return (and create) the directory that holds config + database."""
    override = os.environ.get("TASKPILOT_HOME")
    if override:
        base = Path(override).expanduser()
    elif is_windows():
        base = Path(os.environ.get("APPDATA", str(Path.home()))) / APP_NAME
    else:
        base = Path.home() / ".taskpilot"
    base.mkdir(parents=True, exist_ok=True)
    return base


def default_config() -> dict[str, Any]:
    return {
        "version": CONFIG_VERSION,
        "general": {
            "theme": "dark",
            "start_minimized": False,
            "confirm_destructive": True,
        },
        "tracker": {
            "enabled": True,
            "poll_seconds": 3,
            "idle_threshold_seconds": 120,
            "enforce_limits": False,
            "keep_days": 180,
        },
        "music": {
            "playlist_path": "",
            "player_path": "",
        },
        "power": {
            "action": "shutdown",  # shutdown | restart | sleep | lock
            "delay_seconds": 0,
        },
        "apps": copy.deepcopy(DEFAULT_APPS),
        "categories": copy.deepcopy(DEFAULT_CATEGORIES),
        "focus": {
            "enabled": False,
            "blocked_categories": ["entertainment"],
            "grace_minutes": 5,
        },
        "ui": {
            "window_width": 1040,
            "window_height": 680,
        },
    }


def _deep_merge(base: dict, patch: dict) -> dict:
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value
    return base


class Config:
    """Thread-safe wrapper around the JSON configuration file."""

    def __init__(self, path: Path | None = None, data: dict | None = None) -> None:
        self.path = path or (data_dir() / "config.json")
        self._lock = threading.RLock()
        self.data = data if data is not None else default_config()

    # ---------------------------------------------------------------- loading
    @classmethod
    def load(cls, path: Path | None = None) -> "Config":
        cfg = cls(path=path)
        cfg.reload()
        return cfg

    def reload(self) -> dict:
        with self._lock:
            if self.path.exists():
                try:
                    saved = json.loads(self.path.read_text(encoding="utf-8"))
                except (json.JSONDecodeError, OSError):
                    saved = {}
                merged = default_config()
                _deep_merge(merged, saved)
                self.data = merged
            else:
                self.data = default_config()
            return self.data

    def save(self) -> None:
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".json.tmp")
            tmp.write_text(
                json.dumps(self.data, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            tmp.replace(self.path)

    # ---------------------------------------------------------------- access
    def get(self, dotted: str, default: Any = None) -> Any:
        with self._lock:
            node: Any = self.data
            for part in dotted.split("."):
                if not isinstance(node, dict) or part not in node:
                    return default
                node = node[part]
            return node

    def set(self, dotted: str, value: Any, save: bool = True) -> None:
        with self._lock:
            parts = dotted.split(".")
            node = self.data
            for part in parts[:-1]:
                node = node.setdefault(part, {})
            node[parts[-1]] = value
            if save:
                self.save()

    def update(self, patch: dict, save: bool = True) -> None:
        with self._lock:
            _deep_merge(self.data, patch)
            if save:
                self.save()

    # ----------------------------------------------------------------- apps
    @property
    def apps(self) -> list[dict]:
        with self._lock:
            return list(self.data.get("apps", []))

    def add_app(self, app: dict) -> None:
        with self._lock:
            self.data.setdefault("apps", []).append(app)
            self.save()

    def remove_app(self, name: str) -> None:
        with self._lock:
            self.data["apps"] = [
                a for a in self.data.get("apps", []) if a.get("name") != name
            ]
            self.save()

    def upsert_app(self, name: str, patch: dict) -> None:
        """Update an application entry, creating it when it does not exist."""
        with self._lock:
            apps = self.data.setdefault("apps", [])
            for entry in apps:
                if entry.get("name") == name:
                    entry.update(patch)
                    break
            else:
                apps.append({"name": name, "path": "", "args": "", **patch})
            self.save()

    def find_app(self, name: str) -> dict | None:
        lowered = name.lower()
        for app in self.apps:
            if app.get("name", "").lower() == lowered:
                return app
        return None

    # ------------------------------------------------------------- categories
    @property
    def categories(self) -> dict[str, dict]:
        with self._lock:
            return dict(self.data.get("categories", DEFAULT_CATEGORIES))

    def category_label(self, key: str) -> str:
        return self.categories.get(key, {}).get("label", key.title())

    def category_color(self, key: str) -> str:
        return self.categories.get(key, {}).get("color", "#8A93A6")

    def category_restricted(self, key: str) -> bool:
        return bool(self.categories.get(key, {}).get("restricted", False))

    def hourly_value(self, key: str) -> float:
        try:
            return float(self.categories.get(key, {}).get("hourly_value", 0.0))
        except (TypeError, ValueError):
            return 0.0

    def category_for(self, app_name: str, exe_name: str = "") -> str:
        """Resolve the category of a running application."""
        app = self.find_app(app_name)
        if app and app.get("category"):
            return app["category"]
        haystack = f"{app_name} {exe_name}".lower()
        for needle, category in AUTO_CATEGORY_RULES:
            if needle in haystack:
                return category
        return "other"

    def limit_minutes_for(self, app_name: str) -> int:
        """Daily limit in minutes; 0 means unlimited."""
        app = self.find_app(app_name)
        if app:
            try:
                return int(app.get("daily_limit_minutes", 0) or 0)
            except (TypeError, ValueError):
                return 0
        return 0

    def blocked_categories(self) -> list[str]:
        with self._lock:
            return list(self.data.get("focus", {}).get("blocked_categories", []))
