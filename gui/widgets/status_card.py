from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, Property
from PySide6.QtGui import QPainter, QColor, QPainterPath
from PySide6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel

from gui.widgets.animated_card import AnimatedCard
from gui.animations import PulseAnimator

if TYPE_CHECKING:
    from gui.theme import ThemeManager


class _StatusDot(QWidget):
    """Animated coloured status indicator dot."""

    SIZE = 12

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setFixedSize(self.SIZE, self.SIZE)
        self._color = QColor("#53535F")  # overwritten once theme is applied
        self._pulse: PulseAnimator | None = None

    def set_color(self, hex_color: str, pulse: bool = False) -> None:
        self._color = QColor(hex_color)
        self.update()
        if pulse and self._pulse is None:
            self._pulse = PulseAnimator(self, duration=1500)
            self._pulse.start()
        elif not pulse and self._pulse is not None:
            self._pulse.stop()
            self._pulse = None

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addEllipse(1.0, 1.0, self.SIZE - 2.0, self.SIZE - 2.0)
        p.fillPath(path, self._color)
        p.end()


class StatusCard(AnimatedCard):
    """
    Status bar card with an animated colour dot and status text.

    Replaces the original tkinter StatusBar + provides visual state feedback.
    """

    # State → (palette attribute name, pulse)
    _STATE_TOKENS: dict[str, tuple[str, bool]] = {
        "idle":     ("foreground_muted", False),
        "active":   ("success",         True),
        "watching": ("accent",          True),
        "error":    ("error",           False),
        "maint":    ("warning",         False),
        "exiting":  ("foreground_muted", False),
    }

    COMPACT_HEIGHT = 64

    def __init__(self, manager, parent=None):
        super().__init__(parent, padding=12)
        self._theme: ThemeManager = manager._theme
        self.setFixedHeight(self.COMPACT_HEIGHT)
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        self._dot = _StatusDot(self)
        layout.addWidget(self._dot, 0, Qt.AlignmentFlag.AlignVCenter)

        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(2)

        self._title = QLabel("Status", self)
        self._title.setProperty("class", "section-title")
        text_layout.addWidget(self._title)

        self._label = QLabel("", self)
        text_layout.addWidget(self._label)

        layout.addLayout(text_layout, 1)
        self.card_layout.addLayout(layout)

    def update(self, text: str) -> None:  # type: ignore[override]
        """Update the status text. (Shadows QWidget.update intentionally for API compat.)"""
        self._label.setText(text)

    # Alias for explicit usage where you want to avoid shadowing concerns
    update_status = update

    def set_state(self, state: str) -> None:
        """Set visual state: idle, active, watching, error, maint, exiting."""
        token, pulse = self._STATE_TOKENS.get(state, ("foreground_muted", False))
        color = getattr(self._theme.palette, token)
        self._dot.set_color(color, pulse=pulse)

    def clear(self) -> None:
        self._label.setText("")
        self._dot.set_color(self._theme.palette.foreground_muted, pulse=False)
