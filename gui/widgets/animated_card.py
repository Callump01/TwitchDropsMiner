from __future__ import annotations

from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve, Property
from PySide6.QtGui import QPainter, QColor, QPaintEvent
from PySide6.QtWidgets import QFrame, QVBoxLayout, QGraphicsDropShadowEffect


class AnimatedCard(QFrame):
    """
    Base card widget with rounded corners and optional shadow + hover elevation.

    Use as a container for any content that should appear as a 'card'.
    Set layout contents by accessing self.card_layout.

    Pass shadow=False to disable the QGraphicsDropShadowEffect (recommended
    for cards created in bulk, e.g. inventory campaign cards, to avoid
    Qt rendering crashes when many shadow effects are active simultaneously).
    """

    SHADOW_REST = 4.0
    SHADOW_HOVER = 12.0
    ANIMATION_DURATION = 200

    def __init__(self, parent=None, padding: int = 16, *, shadow: bool = True):
        super().__init__(parent)
        self.setProperty("class", "card")

        # Internal layout
        self.card_layout = QVBoxLayout(self)
        self.card_layout.setContentsMargins(padding, padding, padding, padding)
        self.card_layout.setSpacing(8)

        # Drop-shadow effect (optional)
        self._shadow_enabled = shadow
        self._shadow_effect: QGraphicsDropShadowEffect | None = None
        self._shadow_anim: QPropertyAnimation | None = None

        if shadow:
            self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
            self._shadow_effect = QGraphicsDropShadowEffect(self)
            self._shadow_effect.setBlurRadius(self.SHADOW_REST)
            self._shadow_effect.setOffset(0, 2)
            self._update_shadow_color()
            self.setGraphicsEffect(self._shadow_effect)

            self._shadow_anim = QPropertyAnimation(self, b"shadow_blur", self)
            self._shadow_anim.setDuration(self.ANIMATION_DURATION)
            self._shadow_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    # ---- Animated property ----
    def _get_shadow_blur(self) -> float:
        if self._shadow_effect is not None:
            return self._shadow_effect.blurRadius()
        return 0.0

    def _set_shadow_blur(self, val: float) -> None:
        if self._shadow_effect is not None:
            self._shadow_effect.setBlurRadius(val)

    shadow_blur = Property(float, _get_shadow_blur, _set_shadow_blur)

    def _update_shadow_color(self) -> None:
        if self._shadow_effect is None:
            return
        if self._is_dark():
            self._shadow_effect.setColor(QColor(0, 0, 0, int(255 * 0.45)))
        else:
            self._shadow_effect.setColor(QColor(0, 0, 0, int(255 * 0.10)))

    def _is_dark(self) -> bool:
        bg = self.palette().color(self.backgroundRole())
        return bg.lightness() < 128

    # ---- Hover events ----
    def enterEvent(self, event) -> None:
        if self._shadow_anim is not None and self._shadow_effect is not None:
            self._shadow_anim.stop()
            self._shadow_anim.setStartValue(self._shadow_effect.blurRadius())
            self._shadow_anim.setEndValue(self.SHADOW_HOVER)
            self._shadow_anim.start()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        if self._shadow_anim is not None and self._shadow_effect is not None:
            self._shadow_anim.stop()
            self._shadow_anim.setStartValue(self._shadow_effect.blurRadius())
            self._shadow_anim.setEndValue(self.SHADOW_REST)
            self._shadow_anim.start()
        super().leaveEvent(event)

    def showEvent(self, event) -> None:
        self._update_shadow_color()
        super().showEvent(event)
