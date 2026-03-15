from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCursor, QFont
from PySide6.QtWidgets import QWidget, QVBoxLayout, QTextEdit, QLabel

from gui.widgets.animated_card import AnimatedCard
from translate import _


class ConsoleOutput(AnimatedCard):
    """
    Styled terminal-like log output with timestamp, auto-scroll, and monospace font.

    Replaces the original tkinter ConsoleOutput (tk.Text with scrollbars).
    """

    def __init__(self, parent=None):
        super().__init__(parent, padding=0)

        # Remove card border and set flat style for embedded feel
        self.setProperty("class", "card-flat")

        inner = QVBoxLayout()
        inner.setContentsMargins(12, 10, 12, 10)
        inner.setSpacing(4)

        title = QLabel(_("gui", "output"), self)
        title.setProperty("class", "section-title")
        inner.addWidget(title)

        self._text = QTextEdit(self)
        self._text.setReadOnly(True)
        self._text.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._text.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        # Monospace font
        font = QFont("Cascadia Code", 11)
        font.setStyleHint(QFont.StyleHint.Monospace)
        if not font.exactMatch():
            font = QFont("Consolas", 11)
            font.setStyleHint(QFont.StyleHint.Monospace)
        self._text.setFont(font)
        self._text.setMinimumHeight(120)

        inner.addWidget(self._text, 1)
        self.card_layout.addLayout(inner)

    def print(self, message: str) -> None:
        stamp = datetime.now().strftime("%X")
        if '\n' in message:
            message = message.replace('\n', f"\n{stamp}: ")
        self._text.append(f"{stamp}: {message}")
        # Auto-scroll to bottom
        cursor = self._text.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self._text.setTextCursor(cursor)
