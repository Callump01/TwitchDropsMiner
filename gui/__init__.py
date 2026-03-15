"""
PySide6-based GUI for Twitch Drops Miner.

This package replaces the original monolithic tkinter gui.py with a modular
Qt-based interface featuring modern Fluent-inspired design, smooth animations,
and a collapsible sidebar navigation.

Public API (consumed by twitch.py):
    from gui import GUIManager

The GUIManager class preserves the exact same interface contract as the
original tkinter-based GUIManager, ensuring twitch.py requires no changes.
"""

from gui.manager import GUIManager

__all__ = ["GUIManager"]
