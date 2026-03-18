from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCursor, QFont
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QLabel, QPushButton,
    QSizePolicy,
)

from gui.widgets.animated_card import AnimatedCard
from translate import _


class ConsoleOutput(AnimatedCard):
    """
    Terminal-like log output with header, unread badge, and auto-scroll.

    Designed to sit inside a QSplitter so the user can resize it
    relative to the channel table above.
    """

    MAX_LINES: int = 1000

    def __init__(self, parent=None):
        super().__init__(parent, padding=0)

        # Remove card border and set flat style for embedded feel
        self.setProperty("class", "card-flat")

        self._unread_count = 0
        self._last_message = ""

        inner = QVBoxLayout()
        inner.setContentsMargins(12, 8, 12, 8)
        inner.setSpacing(4)

        # ---- Header bar ----
        header = QHBoxLayout()
        header.setSpacing(8)

        title = QLabel(_("gui", "output"), self)
        title.setProperty("class", "section-title")
        header.addWidget(title)

        # Unread badge (shown when tab is not active)
        self._unread_badge = QLabel("", self)
        self._unread_badge.setStyleSheet(
            "background: #9146FF; color: white; border-radius: 8px;"
            " padding: 1px 6px; font-size: 10px; font-weight: 600;"
        )
        self._unread_badge.setVisible(False)
        header.addWidget(self._unread_badge)

        header.addStretch(1)
        inner.addLayout(header)

        # ---- Text output ----
        self._text = QTextEdit(self)
        self._text.setReadOnly(True)
        self._text.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._text.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        # Monospace font
        text_font = QFont("Cascadia Code", 11)
        text_font.setStyleHint(QFont.StyleHint.Monospace)
        if not text_font.exactMatch():
            text_font = QFont("Consolas", 11)
            text_font.setStyleHint(QFont.StyleHint.Monospace)
        self._text.setFont(text_font)

        inner.addWidget(self._text, 1)
        self.card_layout.addLayout(inner)

        # Sensible min height so the splitter handle is always visible
        self.setMinimumHeight(60)

    def print(self, message: str) -> None:
        stamp = datetime.now().strftime("%X")
        if '\n' in message:
            message = message.replace('\n', f"\n{stamp}: ")
        formatted = f"{stamp}: {message}"
        self._text.append(formatted)

        self._last_message = message

        # Prune oldest lines if over the cap
        doc = self._text.document()
        excess = doc.blockCount() - self.MAX_LINES
        if excess > 0:
            cursor = QTextCursor(doc)
            cursor.movePosition(QTextCursor.MoveOperation.Start)
            for _ in range(excess):
                cursor.movePosition(
                    QTextCursor.MoveOperation.Down,
                    QTextCursor.MoveMode.KeepAnchor,
                )
            cursor.removeSelectedText()
            cursor.deleteChar()  # remove leftover newline

        # Auto-scroll to bottom
        cursor = self._text.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self._text.setTextCursor(cursor)
