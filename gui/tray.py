from __future__ import annotations

import sys
import asyncio
from typing import TYPE_CHECKING

from PySide6.QtCore import QTimer
from PySide6.QtGui import QIcon, QPixmap, QImage
from PySide6.QtWidgets import QSystemTrayIcon, QMenu

from PIL import Image as Image_module

from translate import _
from utils import resource_path
from exceptions import MinerException

if TYPE_CHECKING:
    from gui.manager import GUIManager
    from inventory import TimedDrop


def _pil_to_qicon(pil_image: Image_module.Image) -> QIcon:
    """Convert a PIL Image to a QIcon."""
    img = pil_image.convert("RGBA")
    data = img.tobytes("raw", "RGBA")
    qimg = QImage(data, img.width, img.height, QImage.Format.Format_RGBA8888).copy()
    return QIcon(QPixmap.fromImage(qimg))


class TrayIcon:
    """
    System tray icon using QSystemTrayIcon.

    Replaces the pystray-based TrayIcon with native Qt integration.
    Features: context menu, notifications, icon state management, minimize/restore.
    """

    TITLE = "Twitch Drops Miner"

    def __init__(self, manager: GUIManager):
        self._manager = manager
        self._tray: QSystemTrayIcon | None = None

        # Load icon images from disk
        self._icon_images: dict[str, Image_module.Image] = {
            "pickaxe": Image_module.open(resource_path("icons/pickaxe.ico")),
            "active": Image_module.open(resource_path("icons/active.ico")),
            "idle": Image_module.open(resource_path("icons/idle.ico")),
            "error": Image_module.open(resource_path("icons/error.ico")),
            "maint": Image_module.open(resource_path("icons/maint.ico")),
        }
        # Convert to QIcons
        self._qicons: dict[str, QIcon] = {
            name: _pil_to_qicon(img) for name, img in self._icon_images.items()
        }
        self._icon_state: str = "pickaxe"

    def __del__(self) -> None:
        self.stop()
        for img in self._icon_images.values():
            img.close()

    def _shorten(self, text: str, by_len: int, min_len: int) -> str:
        if (text_len := len(text)) <= min_len + 3 or by_len <= 0:
            return text
        return text[:-min(by_len + 3, text_len - min_len)] + "..."

    def get_title(self, drop: TimedDrop | None) -> str:
        if drop is None:
            return self.TITLE
        campaign = drop.campaign
        title_parts = [
            f"{self.TITLE}\n",
            f"{campaign.game.name}\n",
            drop.rewards_text(),
            f" {drop.progress:.1%} ({campaign.claimed_drops}/{campaign.total_drops})"
        ]
        min_len = 30
        max_len = 127
        missing_len = len(''.join(title_parts)) - max_len
        if missing_len > 0:
            title_parts[2] = self._shorten(title_parts[2], missing_len, min_len)
            missing_len = len(''.join(title_parts)) - max_len
        if missing_len > 0:
            title_parts[1] = self._shorten(title_parts[1], missing_len, min_len)
            missing_len = len(''.join(title_parts)) - max_len
        if missing_len > 0:
            raise MinerException(f"Title couldn't be shortened: {''.join(title_parts)}")
        return ''.join(title_parts)

    def _ensure_tray(self) -> QSystemTrayIcon:
        if self._tray is None:
            self._tray = QSystemTrayIcon(self._manager._window)
            self._tray.setIcon(self._qicons[self._icon_state])

            # Build context menu
            menu = QMenu()
            show_action = menu.addAction(_("gui", "tray", "show"))
            show_action.triggered.connect(self.restore)
            menu.addSeparator()
            quit_action = menu.addAction(_("gui", "tray", "quit"))
            quit_action.triggered.connect(self.quit)

            self._tray.setContextMenu(menu)
            self._tray.activated.connect(self._on_activated)

            drop = self._manager.progress._drop
            self._tray.setToolTip(self.get_title(drop))
        return self._tray

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.restore()

    def stop(self) -> None:
        if self._tray is not None:
            self._tray.hide()
            self._tray = None

    def quit(self) -> None:
        self._manager.close()

    def minimize(self) -> None:
        if sys.platform == "darwin":
            return
        tray = self._ensure_tray()
        tray.show()
        self._manager._window.hide()

    def restore(self) -> None:
        if self._tray is not None:
            self._tray.hide()
        self._manager._window.show()
        self._manager._window.raise_()
        self._manager._window.activateWindow()

    def notify(
        self, message: str, title: str | None = None, duration: float = 10
    ) -> asyncio.Task[None] | None:
        if not self._manager._twitch.settings.tray_notifications:
            return None
        tray = self._ensure_tray()
        if not tray.isVisible():
            tray.show()

        tray.showMessage(
            title or _("gui", "tray", "notification_title"),
            message,
            QSystemTrayIcon.MessageIcon.Information,
            int(duration * 1000),
        )
        return None

    def update_title(self, drop: TimedDrop | None) -> None:
        if self._tray is not None:
            self._tray.setToolTip(self.get_title(drop))

    def change_icon(self, state: str) -> None:
        if state not in self._qicons:
            raise ValueError("Invalid icon state")
        self._icon_state = state
        if self._tray is not None:
            self._tray.setIcon(self._qicons[state])
