from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, Property
from PySide6.QtGui import QPainter, QColor, QPainterPath
from PySide6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel

from gui.widgets.animated_card import AnimatedCard
from gui.animations import PulseAnimator


class _StatusDot(QWidget):
    """Animated coloured status indicator dot."""

    SIZE = 12

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setFixedSize(self.SIZE, self.SIZE)
        self._color = QColor("#53535F")  # idle grey
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

    # State → (colour hex, pulse)
    STATE_STYLES: dict[str, tuple[str, bool]] = {
        "idle":     ("#ADADB8", False),
        "active":   ("#00C853", True),
        "watching": ("#9146FF", True),
        "error":    ("#EB0400", False),
        "maint":    ("#E6A817", False),
        "exiting":  ("#ADADB8", False),
    }

    def __init__(self, parent=None):
        super().__init__(parent, padding=12)
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
        color, pulse = self.STATE_STYLES.get(state, ("#ADADB8", False))
        self._dot.set_color(color, pulse=pulse)

    def clear(self) -> None:
        self._label.setText("")
        self._dot.set_color("#ADADB8", pulse=False)
