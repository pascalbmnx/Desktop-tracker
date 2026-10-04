"""System actions: recycle bin, power, music, launching applications.

All functions return ``(ok, message)`` so the UI can show a toast without
worrying about the Windows specifics.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Tuple

Result = Tuple[bool, str]

IS_WINDOWS = sys.platform.startswith("win")

POWER_ACTIONS = {
    "shutdown": "Shut down",
    "restart": "Restart",
    "sleep": "Sleep",
    "lock": "Lock screen",
}


# ------------------------------------------------------------ recycle bin
def empty_recycle_bin() -> Result:
    """Permanently empty the Windows Recycle Bin."""
    if not IS_WINDOWS:
        return False, "Recycle bin is only available on Windows."
    try:
        import ctypes

        # SHERB_NOCONFIRMATION | SHERB_NOPROGRESSUI | SHERB_NOSOUND = 7
        rc = ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, 7)
        if rc == 0:
            return True, "Recycle bin emptied."
        # Fall back to PowerShell for unusual shell states.
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-Command", "Clear-RecycleBin -Force -ErrorAction Stop"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if proc.returncode == 0:
            return True, "Recycle bin emptied."
        detail = (proc.stderr or proc.stdout or "").strip().splitlines()
        return False, detail[-1] if detail else f"Could not empty the recycle bin (code {rc})."
    except Exception as exc:  # pragma: no cover - defensive
        return False, f"Could not empty the recycle bin: {exc}"


# ------------------------------------------------------------------ power
def power_action(action: str, delay_seconds: int = 0) -> Result:
    """shutdown | restart | sleep | lock"""
    if action not in POWER_ACTIONS:
        return False, f"Unknown power action: {action}"
    if not IS_WINDOWS:
        return False, "Power actions are only available on Windows."
    delay = max(0, int(delay_seconds or 0))
    try:
        if action in ("shutdown", "restart"):
            flag = "/s" if action == "shutdown" else "/r"
            subprocess.Popen(["shutdown", flag, "/t", str(delay)])
            return True, f"{POWER_ACTIONS[action]} scheduled in {delay}s."
        if action == "lock":
            import ctypes

            ctypes.windll.user32.LockWorkStation()
            return True, "Screen locked."
        if action == "sleep":
            import ctypes

            # (hibernate=False, forceCritical=False, disableWakeEvent=False)
            ctypes.windll.powrprof.SetSuspendState(0, 0, 0)
            return True, "Going to sleep..."
    except Exception as exc:  # pragma: no cover - defensive
        return False, f"{POWER_ACTIONS[action]} failed: {exc}"
    return False, "Nothing happened."


def cancel_shutdown() -> Result:
    if not IS_WINDOWS:
        return False, "Only available on Windows."
    try:
        subprocess.run(["shutdown", "/a"], capture_output=True, timeout=10)
        return True, "Pending shutdown cancelled."
    except Exception as exc:
        return False, f"Could not cancel: {exc}"


# ------------------------------------------------------------------ music
def play_music(playlist_path: str, player_path: str = "") -> Result:
    """Open a playlist / audio file / folder with the default (or chosen) player."""
    if not playlist_path:
        return False, "No music playlist configured. Set it in Settings."
    path = Path(os.path.expandvars(playlist_path)).expanduser()
    if not path.exists():
        return False, f"Playlist not found: {path}"

    if player_path:
        player = Path(os.path.expandvars(player_path)).expanduser()
        if not player.exists():
            return False, f"Player not found: {player}"
        try:
            subprocess.Popen([str(player), str(path)])
            return True, f"Playing {path.name} with {player.name}."
        except Exception as exc:
            return False, f"Could not start the player: {exc}"

    return open_path(path, verb="Playing" if path.is_file() else "Opening")


# --------------------------------------------------------------- launching
def open_path(path: str | Path, verb: str = "Opened") -> Result:
    target = Path(os.path.expandvars(str(path))).expanduser()
    if not target.exists():
        return False, f"Not found: {target}"
    try:
        if IS_WINDOWS:
            os.startfile(str(target))  # noqa: S606 - intentional shell open
        else:  # pragma: no cover - dev convenience
            subprocess.Popen(["xdg-open", str(target)])
        return True, f"{verb} {target.name}."
    except Exception as exc:
        return False, f"Could not open {target.name}: {exc}"


def launch_app(path: str, args: str = "") -> Result:
    """Start an application in the background."""
    if not path:
        return False, "No application path configured."
    exe = Path(os.path.expandvars(path)).expanduser()
    if not exe.exists():
        return False, f"Application not found: {exe}"
    try:
        command = [str(exe)]
        if args:
            command += args.split()
        subprocess.Popen(
            command,
            cwd=str(exe.parent) if exe.is_file() else str(exe),
            shell=False,
        )
        return True, f"Launched {exe.name}."
    except Exception as exc:
        return False, f"Could not launch {exe.name}: {exc}"


def open_folder(path: str) -> Result:
    return open_path(path, verb="Opened")
