from __future__ import annotations

from PySide6.QtCore import (
    Qt, QSize, QRect, QRectF, QPointF,
    QPropertyAnimation, QEasingCurve, Property, Signal,
)
from PySide6.QtGui import QPainter, QColor, QPainterPath, QMouseEvent
from PySide6.QtWidgets import QWidget


class ToggleSwitch(QWidget):
    """
    Modern animated toggle switch widget.

    Replaces standard checkboxes with a smooth sliding toggle
    using Twitch-purple accent when ON and neutral grey when OFF.
    """

    toggled = Signal(bool)

    # Dimensions
    TRACK_WIDTH = 40
    TRACK_HEIGHT = 22
    THUMB_MARGIN = 3
    THUMB_SIZE = TRACK_HEIGHT - 2 * THUMB_MARGIN

    def __init__(self, parent: QWidget | None = None, checked: bool = False):
        super().__init__(parent)
        self._checked = checked
        self._thumb_pos: float = float(self._target_pos())
        self._anim = QPropertyAnimation(self, b"thumb_position", self)
        self._anim.setDuration(180)
        self._anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self.setFixedSize(QSize(self.TRACK_WIDTH, self.TRACK_HEIGHT))
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    # ---- Animated property ----
    def _get_thumb_pos(self) -> float:
        return self._thumb_pos

    def _set_thumb_pos(self, pos: float) -> None:
        self._thumb_pos = pos
        self.update()

    thumb_position = Property(float, _get_thumb_pos, _set_thumb_pos)

    # ---- Public API ----
    def isChecked(self) -> bool:
        return self._checked

    def setChecked(self, checked: bool, animated: bool = True) -> None:
        if self._checked == checked:
            return
        self._checked = checked
        if animated:
            self._animate()
        else:
            self._thumb_pos = float(self._target_pos())
            self.update()
        self.toggled.emit(self._checked)

    def toggle(self) -> None:
        self.setChecked(not self._checked)

    # ---- Internal ----
    def _target_pos(self) -> float:
        if self._checked:
            return float(self.TRACK_WIDTH - self.THUMB_MARGIN - self.THUMB_SIZE)
        return float(self.THUMB_MARGIN)

    def _animate(self) -> None:
        self._anim.stop()
        self._anim.setStartValue(self._thumb_pos)
        self._anim.setEndValue(self._target_pos())
        self._anim.start()

    # ---- Events ----
    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.toggle()
        super().mousePressEvent(event)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Track
        track_rect = QRectF(0, 0, self.TRACK_WIDTH, self.TRACK_HEIGHT)
        track_path = QPainterPath()
        track_path.addRoundedRect(track_rect, self.TRACK_HEIGHT / 2, self.TRACK_HEIGHT / 2)

        if self._checked:
            track_color = QColor("#9146FF")
        else:
            track_color = QColor("#53535F") if self._is_dark() else QColor("#C8C8D0")

        p.fillPath(track_path, track_color)

        # Thumb (white circle)
        thumb_rect = QRectF(
            self._thumb_pos,
            self.THUMB_MARGIN,
            self.THUMB_SIZE,
            self.THUMB_SIZE,
        )
        thumb_path = QPainterPath()
        thumb_path.addEllipse(thumb_rect)
        p.fillPath(thumb_path, QColor("#FFFFFF"))

        p.end()

    def _is_dark(self) -> bool:
        """Detect if the parent window is using a dark palette."""
        bg = self.palette().color(self.backgroundRole())
        # Heuristic: dark if luminance < 128
        return bg.lightness() < 128

    def sizeHint(self) -> QSize:
        return QSize(self.TRACK_WIDTH, self.TRACK_HEIGHT)
