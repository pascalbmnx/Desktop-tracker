"""Shared base class for the pages of the main window."""
from __future__ import annotations

import tkinter as tk

from . import theme


class Tab:
    """Base class for a page in the content area.

    ``app`` is the TaskPilotApp instance (typed loosely to avoid a circular
    import - see ui/app.py).
    """

    title = "Page"
    subtitle = ""

    def __init__(self, app, parent: tk.Widget) -> None:
        self.app = app
        self.frame = tk.Frame(parent, bg=theme.BG)

    def refresh(self) -> None:
        """Reload this page's contents from config + usage data."""

    def on_show(self) -> None:
        """Called when the page becomes visible."""
        self.refresh()
