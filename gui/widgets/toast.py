from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import (
    Qt, QTimer, QPropertyAnimation, QEasingCurve, QPoint, QSize,
)
from PySide6.QtGui import QPainter, QPainterPath, QColor
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QLabel, QPushButton, QGraphicsOpacityEffect,
)

if TYPE_CHECKING:
    from gui.theme import ThemeManager


# Toast type → (icon character, palette colour attribute)
_TOAST_TYPES: dict[str, tuple[str, str]] = {
    "success": ("\u2714", "success"),
    "info":    ("\u2139", "accent"),
    "warning": ("\u26A0", "warning"),
    "error":   ("\u2716", "error"),
}


class _ToastCard(QWidget):
    """A single toast notification card."""

    WIDTH = 320
    SLIDE_DISTANCE = 340

    def __init__(
        self,
        message: str,
        toast_type: str,
        theme: ThemeManager,
        duration: int,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._theme = theme
        self._duration = duration
        self.setFixedWidth(self.WIDTH)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)

        palette = theme.palette
        icon_char, color_attr = _TOAST_TYPES.get(toast_type, _TOAST_TYPES["info"])
        color = getattr(palette, color_attr)

        # Card styling
        self.setStyleSheet(
            f"background: {palette.surface};"
            f" border: 1px solid {palette.border_light};"
            f" border-left: 3px solid {color};"
            f" border-radius: 8px;"
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 8, 10)
        layout.setSpacing(10)

        # Colored icon
        icon_label = QLabel(icon_char, self)
        icon_label.setStyleSheet(
            f"color: {color}; font-size: 16px; background: transparent; border: none;"
        )
        icon_label.setFixedWidth(20)
        layout.addWidget(icon_label)

        # Message text
        msg_label = QLabel(message, self)
        msg_label.setWordWrap(True)
        msg_label.setStyleSheet(
            f"color: {palette.foreground}; font-size: 12px;"
            f" background: transparent; border: none;"
        )
        layout.addWidget(msg_label, 1)

        # Close button
        close_btn = QPushButton("\u2715", self)
        close_btn.setFixedSize(20, 20)
        close_btn.setStyleSheet(
            f"color: {palette.foreground_muted}; background: transparent;"
            f" border: none; font-size: 12px; border-radius: 10px;"
        )
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(self.dismiss)
        layout.addWidget(close_btn, 0, Qt.AlignmentFlag.AlignTop)

        self.adjustSize()

        # Dismiss timer
        self._dismiss_timer = QTimer(self)
        self._dismiss_timer.setSingleShot(True)
        self._dismiss_timer.timeout.connect(self.dismiss)

        # Slide-in animation
        self._slide_anim = QPropertyAnimation(self, b"pos", self)
        self._slide_anim.setDuration(300)
        self._slide_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        # Fade-out animation
        self._opacity = QGraphicsOpacityEffect(self)
        self._opacity.setOpacity(1.0)
        self.setGraphicsEffect(self._opacity)
        self._fade_anim = QPropertyAnimation(self._opacity, b"opacity", self)
        self._fade_anim.setDuration(200)
        self._fade_anim.setEasingCurve(QEasingCurve.Type.InCubic)

    def show_animated(self, target_pos: QPoint) -> None:
        """Slide in from the right to target_pos."""
        start = QPoint(target_pos.x() + self.SLIDE_DISTANCE, target_pos.y())
        self.move(start)
        self.show()
        self._slide_anim.setStartValue(start)
        self._slide_anim.setEndValue(target_pos)
        self._slide_anim.start()
        self._dismiss_timer.start(self._duration)

    def dismiss(self) -> None:
        """Fade out and remove the toast."""
        self._dismiss_timer.stop()
        self._fade_anim.setStartValue(1.0)
        self._fade_anim.setEndValue(0.0)
        self._fade_anim.finished.connect(self._on_dismissed)
        self._fade_anim.start()

    def _on_dismissed(self) -> None:
        self.hide()
        self.setParent(None)
        self.deleteLater()

    def slide_to(self, new_pos: QPoint) -> None:
        """Smoothly reposition (used when a toast above is dismissed)."""
        self._slide_anim.stop()
        self._slide_anim.setStartValue(self.pos())
        self._slide_anim.setEndValue(new_pos)
        self._slide_anim.setDuration(200)
        self._slide_anim.start()


class ToastManager:
    """Manages a stack of toast notifications at the top-right of the window."""

    MAX_VISIBLE = 5
    MARGIN_TOP = 16
    MARGIN_RIGHT = 16
    SPACING = 8

    def __init__(self, parent_window: QWidget, theme: ThemeManager):
        self._parent = parent_window
        self._theme = theme
        self._toasts: list[_ToastCard] = []

    def show_toast(
        self,
        message: str,
        toast_type: str = "info",
        duration: int = 5000,
    ) -> None:
        """Display a new toast notification."""
        # Remove oldest if at capacity
        while len(self._toasts) >= self.MAX_VISIBLE:
            oldest = self._toasts.pop(0)
            oldest.dismiss()

        toast = _ToastCard(message, toast_type, self._theme, duration, self._parent)
        toast._fade_anim.finished.connect(lambda t=toast: self._on_toast_removed(t))
        self._toasts.append(toast)

        # Position and show
        pos = self._compute_position(len(self._toasts) - 1, toast.sizeHint().height())
        toast.show_animated(pos)

    def _compute_position(self, index: int, height: int) -> QPoint:
        """Compute position for toast at the given stack index."""
        parent_rect = self._parent.rect()
        x = parent_rect.width() - _ToastCard.WIDTH - self.MARGIN_RIGHT
        y = self.MARGIN_TOP
        for i in range(index):
            if i < len(self._toasts):
                y += self._toasts[i].sizeHint().height() + self.SPACING
        return QPoint(x, y)

    def _on_toast_removed(self, toast: _ToastCard) -> None:
        """Reposition remaining toasts after one is removed."""
        if toast in self._toasts:
            self._toasts.remove(toast)
        # Slide remaining toasts up
        y = self.MARGIN_TOP
        parent_rect = self._parent.rect()
        x = parent_rect.width() - _ToastCard.WIDTH - self.MARGIN_RIGHT
        for t in self._toasts:
            target = QPoint(x, y)
            if t.pos() != target:
                t.slide_to(target)
            y += t.sizeHint().height() + self.SPACING
