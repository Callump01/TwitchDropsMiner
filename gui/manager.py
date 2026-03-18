from __future__ import annotations

import sys
import logging
import asyncio
from collections import abc
from functools import cached_property
from typing import Any, NoReturn, TypeVar, TYPE_CHECKING

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon, QPixmap, QImage, QCloseEvent
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QStackedWidget, QApplication,
)

from PIL import Image as Image_module

from gui.theme import ThemeManager
from gui.tray import TrayIcon
from gui.widgets.toast import ToastManager
from gui.widgets.websocket_panel import WebsocketPanel
from gui.widgets.nav_sidebar import NavSidebar, NavItem
from gui.tabs.main_tab import MainTab
from gui.tabs.inventory_tab import InventoryTab
from gui.tabs.settings_tab import SettingsTab
from gui.tabs.help_tab import HelpTab
from cache import ImageCache
from translate import _
from utils import resource_path, Game
from exceptions import ExitRequest
from constants import WINDOW_TITLE, OUTPUT_FORMATTER

if TYPE_CHECKING:
    from twitch import Twitch
    from channel import Channel
    from settings import Settings
    from inventory import DropsCampaign, TimedDrop

_T = TypeVar("_T")


class _TKOutputHandler(logging.Handler):
    """Log handler that forwards messages to the GUI console."""
    def __init__(self, output: GUIManager):
        super().__init__()
        self._output = output

    def emit(self, record):
        self._output.print(self.format(record))


class _MainWindow(QMainWindow):
    """
    Custom QMainWindow that intercepts close events
    to go through the GUIManager's close logic.
    """

    def __init__(self, manager: GUIManager):
        super().__init__()
        self._manager = manager

    def closeEvent(self, event: QCloseEvent) -> None:
        self._manager.close()
        event.ignore()  # We handle closing ourselves


class _NotebookCompat:
    """
    Compatibility shim providing the original Notebook interface
    used by InventoryOverview._on_tab_switched.
    """

    def __init__(self, sidebar: NavSidebar, stack: QStackedWidget):
        self._sidebar = sidebar
        self._stack = stack
        self._callbacks: list[Any] = []

    def current_tab(self) -> int:
        return self._sidebar.current_index()

    def add_view_event(self, callback) -> None:
        self._callbacks.append(callback)

    def _fire_tab_changed(self, index: int) -> None:
        for cb in self._callbacks:
            try:
                cb(None)  # Original passes a tk.Event; we pass None
            except Exception:
                pass


class GUIManager:
    """
    Master GUI orchestrator.

    Creates the QMainWindow with sidebar navigation, assembles all tabs,
    manages the async bridge, theming, tray, and preserves the full
    public API contract expected by twitch.py.
    """

    def __init__(self, twitch: Twitch):
        self._twitch: Twitch = twitch
        self._close_requested = asyncio.Event()
        self._theme = ThemeManager()

        # Create main window
        self._window = _MainWindow(self)
        self._window.setWindowTitle(WINDOW_TITLE)
        self._window.setMinimumSize(QSize(960, 780))

        # Set window icon
        icon_path = resource_path("icons/pickaxe.ico")
        try:
            with Image_module.open(icon_path) as pil_img:
                rgba = pil_img.convert("RGBA")
                data = rgba.tobytes("raw", "RGBA")
                qimg = QImage(data, rgba.width, rgba.height, QImage.Format.Format_RGBA8888).copy()
                self._window.setWindowIcon(QIcon(QPixmap.fromImage(qimg)))
        except Exception:
            pass

        # Image cache
        self._cache = ImageCache(self)

        # Central widget
        central = QWidget(self._window)
        central.setObjectName("CentralWidget")
        central_layout = QHBoxLayout(central)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.setSpacing(0)
        self._window.setCentralWidget(central)

        # Sidebar navigation
        nav_items = [
            NavItem(icon="\U0001F3E0", label=_("gui", "tabs", "main"), tooltip="Dashboard"),
            NavItem(icon="\U0001F4E6", label=_("gui", "tabs", "inventory"), tooltip="Inventory"),
            NavItem(icon="\u2699", label=_("gui", "tabs", "settings"), tooltip="Settings"),
            NavItem(icon="\u2139", label=_("gui", "tabs", "help"), tooltip="Help"),
        ]
        self._sidebar = NavSidebar(nav_items, self._theme, central)
        central_layout.addWidget(self._sidebar)

        # Stacked widget for tab content
        self._stack = QStackedWidget(central)
        central_layout.addWidget(self._stack, 1)

        # Notebook compatibility shim
        self.tabs = _NotebookCompat(self._sidebar, self._stack)

        # Create tabs
        self._main_tab = MainTab(self, self._stack)
        self._stack.addWidget(self._main_tab)

        self._inv_tab = InventoryTab(self, self._stack)
        self._stack.addWidget(self._inv_tab)

        self._settings_tab = SettingsTab(self, self._stack)
        self._stack.addWidget(self._settings_tab)

        self._help_tab = HelpTab(self, self._stack)
        self._stack.addWidget(self._help_tab)

        # Connect sidebar navigation to stacked widget
        self._sidebar.tab_changed.connect(self._on_tab_changed)

        # WebsocketPanel lives in the sidebar
        self._ws_panel = WebsocketPanel(self._sidebar)
        self._sidebar.set_aux_widget(self._ws_panel)

        # Expose sub-components via the original interface names
        self.status = self._main_tab.status
        self.login = self._main_tab.login
        self.websockets = self._ws_panel
        self.progress = self._main_tab.progress
        self.output = self._main_tab.output
        self.channels = self._main_tab.channels
        self.inv = self._inv_tab
        self.settings = self._settings_tab

        # Toast notification manager
        self._toasts = ToastManager(self._window, self._theme)

        # Tray icon
        self.tray = TrayIcon(self)

        # Logging handler
        self._handler = _TKOutputHandler(self)
        self._handler.setFormatter(OUTPUT_FORMATTER)
        logger = logging.getLogger("TwitchDrops")
        logger.addHandler(self._handler)
        if (logging_level := logger.getEffectiveLevel()) < logging.ERROR:
            self.print(f"Logging level: {logging.getLevelName(logging_level)}")

        # Connect theme change handler for widgets with baked-in palette colors
        self._theme.theme_changed.connect(self._on_theme_changed)

        # Apply theme
        app = QApplication.instance()
        if app is not None:
            self._theme.apply(app, self._twitch.settings.dark_mode)

        # Set title bar colour on Windows
        if sys.platform == "win32":
            # Need to defer this slightly to ensure the window has been created
            from PySide6.QtCore import QTimer
            QTimer.singleShot(100, lambda: self._apply_title_bar_color())

        # Show or minimize
        if self._twitch.settings.tray and sys.platform != "darwin":
            self.tray.minimize()
        else:
            self._window.show()

    def _apply_title_bar_color(self) -> None:
        if sys.platform == "win32":
            hwnd = int(self._window.winId())
            ThemeManager.set_title_bar_color(hwnd, self._theme.is_dark)

    def _on_tab_changed(self, index: int) -> None:
        self._stack.setCurrentIndex(index)
        self.tabs._fire_tab_changed(index)

    # ---------------------------------------------------------------- #
    #  Public API - Lifecycle                                           #
    # ---------------------------------------------------------------- #

    @property
    def running(self) -> bool:
        return self._window.isVisible() or (self.tray._tray is not None)

    @property
    def close_requested(self) -> bool:
        return self._close_requested.is_set()

    async def wait_until_closed(self) -> None:
        await self._close_requested.wait()

    async def coro_unless_closed(self, coro: abc.Awaitable[_T]) -> _T:
        tasks = [asyncio.ensure_future(coro), asyncio.ensure_future(self._close_requested.wait())]
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in pending:
            task.cancel()
        if self._close_requested.is_set():
            raise ExitRequest()
        return await next(iter(done))

    def prevent_close(self) -> None:
        self._close_requested.clear()

    def start(self) -> None:
        # With qasync, the Qt event loop is already running.
        # This is a no-op compatibility method.
        pass

    def stop(self) -> None:
        self.progress.stop_timer()

    def close(self, *args) -> int:
        self._close_requested.set()
        self._twitch.close()
        return 0

    def close_window(self) -> None:
        self.tray.stop()
        logging.getLogger("TwitchDrops").removeHandler(self._handler)
        self._window.close()
        # Actually allow the close now
        app = QApplication.instance()
        if app is not None:
            app.quit()

    # ---------------------------------------------------------------- #
    #  Public API - Display                                             #
    # ---------------------------------------------------------------- #

    def print(self, message: str) -> None:
        self.output.print(message)

    def toast(self, message: str, toast_type: str = "info", duration: int = 5000) -> None:
        """Show an in-app toast notification."""
        self._toasts.show_toast(message, toast_type, duration)

    def display_drop(
        self, drop: TimedDrop, *, countdown: bool = True, subone: bool = False
    ) -> None:
        # Toast when switching to a different drop
        prev_drop = self.progress._drop
        if drop is not None and (prev_drop is None or prev_drop.id != drop.id):
            reward = drop.rewards_text()
            game = drop.campaign.game.name
            self.toast(f"{game}: {reward}", "info", 4000)
        self.progress.display(drop, countdown=countdown, subone=subone)
        self.tray.update_title(drop)

    def clear_drop(self) -> None:
        self.progress.display(None)
        self.tray.update_title(None)

    def set_games(self, games: set[Game]) -> None:
        self.settings.set_games(games)

    def save(self, *, force: bool = False) -> None:
        self._cache.save(force=force)

    def grab_attention(self, *, sound: bool = True) -> None:
        self.tray.restore()
        self._window.raise_()
        self._window.activateWindow()
        if sound:
            QApplication.beep()

    def unfocus(self) -> None:
        self._window.setFocus()
        self.channels.clear_selection()
        self.settings.clear_selection()

    # ---------------------------------------------------------------- #
    #  Public API - Theming                                             #
    # ---------------------------------------------------------------- #

    def apply_theme(self, dark: bool) -> None:
        app = QApplication.instance()
        if app is not None:
            self._theme.apply(app, dark)
        if sys.platform == "win32":
            try:
                hwnd = int(self._window.winId())
                ThemeManager.set_title_bar_color(hwnd, dark)
            except Exception:
                pass

    def _on_theme_changed(self) -> None:
        """Refresh widgets that bake palette colors at construction time."""
        self._sidebar.refresh_theme()
        self._main_tab.channels._refresh_watching_highlight()
        self._inv_tab.refresh()
