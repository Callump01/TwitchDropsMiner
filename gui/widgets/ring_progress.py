from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import (
    Qt, QRectF, Property, QPropertyAnimation, QEasingCurve,
)
from PySide6.QtGui import (
    QPainter, QColor, QPen, QFont, QConicalGradient,
)
from PySide6.QtWidgets import QWidget

if TYPE_CHECKING:
    from gui.theme import ThemeManager


class RingProgress(QWidget):
    """Circular progress ring with center text.

    Draws an antialiased arc from 12 o'clock clockwise with an accent
    gradient.  Center shows the time remaining (large) and percentage
    (small, muted).
    """

    RING_SIZE = 120
    RING_THICKNESS = 8

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        theme: ThemeManager | None = None,
    ):
        super().__init__(parent)
        self._theme = theme
        self._progress: float = 0.0  # 0.0 to 1.0
        self._center_text: str = "--:--"
        self._sub_text: str = "-%"
        self.setFixedSize(self.RING_SIZE, self.RING_SIZE)

        # Smooth progress animation
        self._anim = QPropertyAnimation(self, b"ring_progress", self)
        self._anim.setDuration(600)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    # ---- Animated property ----
    def _get_progress(self) -> float:
        return self._progress

    def _set_progress(self, val: float) -> None:
        self._progress = max(0.0, min(1.0, val))
        self.update()

    ring_progress = Property(float, _get_progress, _set_progress)

    # ---- Public API ----
    def set_progress(self, value: float, animated: bool = True) -> None:
        """Set progress (0.0-1.0), optionally animated."""
        value = max(0.0, min(1.0, value))
        if animated:
            self._anim.stop()
            self._anim.setStartValue(self._progress)
            self._anim.setEndValue(value)
            self._anim.start()
        else:
            self._progress = value
            self.update()

    def set_center_text(self, text: str) -> None:
        self._center_text = text
        self.update()

    def set_sub_text(self, text: str) -> None:
        self._sub_text = text
        self.update()

    # ---- Painting ----
    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        size = min(self.width(), self.height())
        margin = self.RING_THICKNESS / 2 + 2
        ring_rect = QRectF(margin, margin, size - 2 * margin, size - 2 * margin)

        # Colors from theme
        if self._theme is not None:
            palette = self._theme.palette
            bg_color = QColor(palette.border_light)
            accent_start = QColor(palette.accent)
            accent_end = QColor(palette.accent_hover)
            text_color = QColor(palette.foreground)
            muted_color = QColor(palette.foreground_muted)
        else:
            bg_color = QColor("#26262C")
            accent_start = QColor("#9146FF")
            accent_end = QColor("#A970FF")
            text_color = QColor("#EFEFF1")
            muted_color = QColor("#ADADB8")

        # Background ring (full circle)
        bg_pen = QPen(bg_color, self.RING_THICKNESS)
        bg_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(bg_pen)
        p.drawArc(ring_rect, 0, 360 * 16)

        # Progress arc
        if self._progress > 0.001:
            # Conical gradient for the arc
            gradient = QConicalGradient(ring_rect.center(), 90)
            gradient.setColorAt(0.0, accent_start)
            gradient.setColorAt(1.0, accent_end)

            arc_pen = QPen(accent_start, self.RING_THICKNESS)
            arc_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(arc_pen)

            # Qt arcs: start at 3 o'clock, CCW in 1/16th degrees.
            # We want start at 12 o'clock (90 deg), going clockwise.
            start_angle = 90 * 16
            span_angle = -int(self._progress * 360 * 16)
            p.drawArc(ring_rect, start_angle, span_angle)

        # Center text (time remaining)
        p.setPen(text_color)
        center_font = QFont("Segoe UI", 16)
        center_font.setWeight(QFont.Weight.DemiBold)
        p.setFont(center_font)
        center_rect = QRectF(0, size * 0.25, size, size * 0.35)
        p.drawText(center_rect, Qt.AlignmentFlag.AlignCenter, self._center_text)

        # Sub text (percentage)
        p.setPen(muted_color)
        sub_font = QFont("Segoe UI", 10)
        p.setFont(sub_font)
        sub_rect = QRectF(0, size * 0.55, size, size * 0.2)
        p.drawText(sub_rect, Qt.AlignmentFlag.AlignCenter, self._sub_text)

        p.end()
