from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import (
    Qt, QRectF, QPointF, QVariantAnimation, QEasingCurve,
)
from PySide6.QtGui import (
    QPainter, QColor, QLinearGradient, QPainterPath,
)
from PySide6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout

from gui.widgets.animated_card import AnimatedCard

if TYPE_CHECKING:
    from gui.theme import ThemeManager


class SkeletonRect(QWidget):
    """Animated shimmer placeholder rectangle.

    Draws a rounded rectangle with a gradient highlight that sweeps
    left-to-right, creating a loading shimmer effect.
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        width: int = 0,
        height: int = 20,
        radius: int = 4,
        theme: ThemeManager | None = None,
    ):
        super().__init__(parent)
        self._radius = radius
        self._theme = theme
        self._shimmer_pos: float = -0.3  # normalized position of highlight band

        if width > 0:
            self.setFixedWidth(width)
        if height > 0:
            self.setFixedHeight(height)

        # Shimmer animation: sweeps from left to right
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(1400)
        self._anim.setStartValue(-0.3)
        self._anim.setEndValue(1.3)
        self._anim.setEasingCurve(QEasingCurve.Type.Linear)
        self._anim.setLoopCount(-1)  # infinite
        self._anim.valueChanged.connect(self._on_shimmer)
        self._anim.start()

    def _on_shimmer(self, value: float) -> None:
        self._shimmer_pos = value
        self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()
        rect = QRectF(0, 0, w, h)

        # Base color from theme or fallback
        if self._theme is not None:
            base = QColor(self._theme.palette.border)
            highlight = QColor(self._theme.palette.surface_hover)
        else:
            base = QColor("#2F2F35")
            highlight = QColor("#3A3A3D")

        # Draw base rounded rect
        path = QPainterPath()
        path.addRoundedRect(rect, self._radius, self._radius)
        p.fillPath(path, base)

        # Draw shimmer gradient overlay
        shimmer_center = self._shimmer_pos * w
        shimmer_width = w * 0.35
        gradient = QLinearGradient(
            QPointF(shimmer_center - shimmer_width, 0),
            QPointF(shimmer_center + shimmer_width, 0),
        )
        gradient.setColorAt(0.0, QColor(0, 0, 0, 0))
        gradient.setColorAt(0.5, highlight)
        gradient.setColorAt(1.0, QColor(0, 0, 0, 0))

        p.setClipPath(path)
        p.fillRect(rect, gradient)
        p.end()

    def stop(self) -> None:
        self._anim.stop()


class SkeletonCard(AnimatedCard):
    """Campaign card skeleton placeholder shown during loading.

    Mimics the layout of a real campaign card with shimmer rectangles
    standing in for image, text lines, and benefit thumbnails.
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        theme: ThemeManager | None = None,
    ):
        super().__init__(parent, padding=12, shadow=False)
        self._theme = theme
        self._skeleton_rects: list[SkeletonRect] = []

        main_h = QHBoxLayout()
        main_h.setSpacing(12)

        # Image placeholder (108x144)
        img_skel = SkeletonRect(self, width=108, height=144, radius=6, theme=theme)
        self._skeleton_rects.append(img_skel)
        main_h.addWidget(img_skel)

        # Info column
        info_layout = QVBoxLayout()
        info_layout.setSpacing(8)

        # Title line (wider)
        title_skel = SkeletonRect(self, height=18, radius=4, theme=theme)
        title_skel.setMinimumWidth(180)
        self._skeleton_rects.append(title_skel)
        info_layout.addWidget(title_skel)

        # Status line (short)
        status_skel = SkeletonRect(self, width=80, height=14, radius=4, theme=theme)
        self._skeleton_rects.append(status_skel)
        info_layout.addWidget(status_skel)

        # Date line (medium)
        date_skel = SkeletonRect(self, width=140, height=14, radius=4, theme=theme)
        self._skeleton_rects.append(date_skel)
        info_layout.addWidget(date_skel)

        # Link line (medium)
        link_skel = SkeletonRect(self, width=100, height=14, radius=4, theme=theme)
        self._skeleton_rects.append(link_skel)
        info_layout.addWidget(link_skel)

        info_layout.addStretch(1)
        main_h.addLayout(info_layout, 1)

        # Drops column
        drops_h = QHBoxLayout()
        drops_h.setSpacing(12)
        for _ in range(2):
            drop_v = QVBoxLayout()
            drop_v.setSpacing(4)
            # Benefit image placeholder
            benefit_skel = SkeletonRect(self, width=64, height=64, radius=4, theme=theme)
            self._skeleton_rects.append(benefit_skel)
            drop_v.addWidget(benefit_skel)
            # Benefit name placeholder
            name_skel = SkeletonRect(self, width=64, height=12, radius=3, theme=theme)
            self._skeleton_rects.append(name_skel)
            drop_v.addWidget(name_skel)
            drop_v.addStretch(1)
            drops_h.addLayout(drop_v)
        main_h.addLayout(drops_h)

        self.card_layout.addLayout(main_h)

    def stop(self) -> None:
        """Stop all shimmer animations."""
        for rect in self._skeleton_rects:
            rect.stop()
