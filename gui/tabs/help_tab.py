from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QScrollArea, QFrame, QSizePolicy,
)

from gui.widgets.animated_card import AnimatedCard
from utils import webopen
from translate import _

if TYPE_CHECKING:
    from gui.manager import GUIManager


class _LinkLabel(QLabel):
    """Clickable link label with hand cursor."""

    def __init__(self, text: str, url: str, parent=None):
        super().__init__(text, parent)
        self._url = url
        self.setProperty("class", "link")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(
            "QLabel { text-decoration: underline; }"
        )

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            webopen(self._url)
        super().mousePressEvent(event)


class HelpTab(QWidget):
    """
    Help / About tab with clean card layout.

    Contains: About section, Useful Links, How It Works, Getting Started.
    """

    MAX_WIDTH = 700

    def __init__(self, manager: GUIManager, parent=None):
        super().__init__(parent)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)

        # ---- About ----
        about_card = AnimatedCard(container, padding=16)
        about_card.setMaximumWidth(self.MAX_WIDTH)
        al = about_card.card_layout

        about_title = QLabel("About", about_card)
        about_title.setProperty("class", "heading")
        al.addWidget(about_title)

        al.addWidget(QLabel("Application created by:", about_card))
        al.addWidget(_LinkLabel("DevilXD", "https://github.com/DevilXD", about_card))

        al.addWidget(QLabel("Repository:", about_card))
        al.addWidget(_LinkLabel(
            "https://github.com/DevilXD/TwitchDropsMiner",
            "https://github.com/DevilXD/TwitchDropsMiner",
            about_card,
        ))

        sep = QFrame(about_card)
        sep.setProperty("class", "separator")
        sep.setFrameShape(QFrame.Shape.HLine)
        al.addWidget(sep)

        al.addWidget(QLabel("Donate:", about_card))
        donate_link = _LinkLabel(
            "If you like the application and found it useful, "
            "please consider donating a small amount of money to support me. Thank you!",
            "https://www.buymeacoffee.com/DevilXD",
            about_card,
        )
        donate_link.setWordWrap(True)
        al.addWidget(donate_link)

        layout.addWidget(about_card, 0, Qt.AlignmentFlag.AlignHCenter)

        # ---- Useful Links ----
        links_card = AnimatedCard(container, padding=16)
        links_card.setMaximumWidth(self.MAX_WIDTH)
        ll = links_card.card_layout

        links_title = QLabel(_("gui", "help", "links", "name"), links_card)
        links_title.setProperty("class", "heading")
        ll.addWidget(links_title)

        ll.addWidget(_LinkLabel(
            _("gui", "help", "links", "inventory"),
            "https://www.twitch.tv/drops/inventory",
            links_card,
        ))
        ll.addWidget(_LinkLabel(
            _("gui", "help", "links", "campaigns"),
            "https://www.twitch.tv/drops/campaigns",
            links_card,
        ))

        layout.addWidget(links_card, 0, Qt.AlignmentFlag.AlignHCenter)

        # ---- How It Works ----
        hiw_card = AnimatedCard(container, padding=16)
        hiw_card.setMaximumWidth(self.MAX_WIDTH)
        hl = hiw_card.card_layout

        hiw_title = QLabel(_("gui", "help", "how_it_works"), hiw_card)
        hiw_title.setProperty("class", "heading")
        hl.addWidget(hiw_title)

        hiw_text = QLabel(_("gui", "help", "how_it_works_text"), hiw_card)
        hiw_text.setWordWrap(True)
        hl.addWidget(hiw_text)

        layout.addWidget(hiw_card, 0, Qt.AlignmentFlag.AlignHCenter)

        # ---- Getting Started ----
        gs_card = AnimatedCard(container, padding=16)
        gs_card.setMaximumWidth(self.MAX_WIDTH)
        gl = gs_card.card_layout

        gs_title = QLabel(_("gui", "help", "getting_started"), gs_card)
        gs_title.setProperty("class", "heading")
        gl.addWidget(gs_title)

        gs_text = QLabel(_("gui", "help", "getting_started_text"), gs_card)
        gs_text.setWordWrap(True)
        gl.addWidget(gs_text)

        layout.addWidget(gs_card, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addStretch(1)

        scroll.setWidget(container)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)
