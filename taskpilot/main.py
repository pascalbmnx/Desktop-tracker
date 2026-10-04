"""TaskPilot entry point.

Run with:  python main.py
Build with: build.bat  (creates TaskPilot.exe via PyInstaller)
"""
from __future__ import annotations

import sys


def main() -> int:
    try:
        import tkinter  # noqa: F401
    except Exception:
        print("Tkinter is missing. Reinstall Python from python.org with "
              "the 'tcl/tk and IDLE' option enabled.")
        return 1

    from taskpilot.ui.app import TaskPilotApp

    app = TaskPilotApp()
    app.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
