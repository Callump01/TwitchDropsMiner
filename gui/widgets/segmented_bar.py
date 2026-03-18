from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import (
    Qt, QRectF, QVariantAnimation, QEasingCurve, QObject,
)
from PySide6.QtGui import QPainter, QColor, QPainterPath
from PySide6.QtWidgets import QWidget

if TYPE_CHECKING:
    from gui.theme import ThemeManager


class SegmentedProgressBar(QWidget):
    """Campaign progress bar showing claimed / in-progress / remaining segments.

    Each segment represents one drop in the campaign:
    - Claimed: solid accent color
    - In-progress: accent with animated pulse
    - Remaining: muted/border color

    Small gaps between segments provide visual separation.
    """

    HEIGHT = 14
    GAP = 3
    RADIUS = 4

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        theme: ThemeManager | None = None,
    ):
        super().__init__(parent)
        self._theme = theme
        self._total: int = 0
        self._claimed: int = 0
        self._in_progress: float = 0.0  # fractional progress of current drop (0-1)
        self.setFixedHeight(self.HEIGHT)
        self.setMinimumWidth(100)

        # Pulse animation for the in-progress segment
        self._pulse_alpha: float = 1.0
        self._pulse_anim = QVariantAnimation(self)
        self._pulse_anim.setDuration(1200)
        self._pulse_anim.setStartValue(1.0)
        self._pulse_anim.setEndValue(0.5)
        self._pulse_anim.setEasingCurve(QEasingCurve.Type.InOutSine)
        self._pulse_anim.setLoopCount(-1)
        self._pulse_anim.valueChanged.connect(self._on_pulse)

    def _on_pulse(self, value: float) -> None:
        self._pulse_alpha = value
        self.update()

    def set_segments(
        self, claimed: int, in_progress: float, total: int
    ) -> None:
        """Update the segment data.

        Args:
            claimed: Number of fully claimed drops.
            in_progress: Fractional progress of the current drop (0.0-1.0).
            total: Total number of drops in the campaign.
        """
        self._claimed = claimed
        self._in_progress = max(0.0, min(1.0, in_progress))
        self._total = max(total, 1)

        # Start/stop pulse based on whether we have an active drop
        if in_progress > 0.0 and not self._pulse_anim.state() == QVariantAnimation.State.Running:
            self._pulse_anim.start()
        elif in_progress <= 0.0:
            self._pulse_anim.stop()
            self._pulse_alpha = 1.0

        self.update()

    def paintEvent(self, event) -> None:
        if self._total <= 0:
            return

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()

        # Colors from theme
        if self._theme is not None:
            palette = self._theme.palette
            accent = QColor(palette.accent)
            accent_hover = QColor(palette.accent_hover)
            muted = QColor(palette.border)
        else:
            accent = QColor("#9146FF")
            accent_hover = QColor("#A970FF")
            muted = QColor("#2F2F35")

        total_gaps = (self._total - 1) * self.GAP
        segment_width = (w - total_gaps) / self._total

        for i in range(self._total):
            x = i * (segment_width + self.GAP)
            rect = QRectF(x, 0, segment_width, h)
            path = QPainterPath()
            path.addRoundedRect(rect, self.RADIUS, self.RADIUS)

            if i < self._claimed:
                # Claimed: solid accent
                p.fillPath(path, accent)
            elif i == self._claimed and self._in_progress > 0:
                # In-progress: partial fill with pulse
                # Background
                p.fillPath(path, muted)
                # Filled portion
                fill_width = segment_width * self._in_progress
                fill_rect = QRectF(x, 0, fill_width, h)
                # Clip to segment shape
                p.save()
                p.setClipPath(path)
                fill_color = QColor(accent_hover)
                fill_color.setAlphaF(self._pulse_alpha)
                p.fillRect(fill_rect, fill_color)
                p.restore()
            else:
                # Remaining: muted
                p.fillPath(path, muted)

        p.end()

    def stop(self) -> None:
        """Stop the pulse animation."""
        self._pulse_anim.stop()
