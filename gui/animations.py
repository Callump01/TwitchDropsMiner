from __future__ import annotations

from PySide6.QtCore import (
    QPropertyAnimation,
    QVariantAnimation,
    QEasingCurve,
    QParallelAnimationGroup,
    QSequentialAnimationGroup,
    QPauseAnimation,
    QTimer,
    Property,
    QObject,
    Signal,
    QPointF,
)
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QWidget, QGraphicsOpacityEffect


def fade_in(widget: QWidget, duration: int = 300, start: float = 0.0, end: float = 1.0) -> QPropertyAnimation:
    """Fade a widget in by animating its opacity."""
    effect = widget.graphicsEffect()
    if not isinstance(effect, QGraphicsOpacityEffect):
        effect = QGraphicsOpacityEffect(widget)
        widget.setGraphicsEffect(effect)
    effect.setOpacity(start)
    anim = QPropertyAnimation(effect, b"opacity", widget)
    anim.setDuration(duration)
    anim.setStartValue(start)
    anim.setEndValue(end)
    anim.setEasingCurve(QEasingCurve.Type.OutCubic)
    anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
    return anim


def fade_out(widget: QWidget, duration: int = 200, start: float = 1.0, end: float = 0.0) -> QPropertyAnimation:
    """Fade a widget out by animating its opacity."""
    effect = widget.graphicsEffect()
    if not isinstance(effect, QGraphicsOpacityEffect):
        effect = QGraphicsOpacityEffect(widget)
        widget.setGraphicsEffect(effect)
    effect.setOpacity(start)
    anim = QPropertyAnimation(effect, b"opacity", widget)
    anim.setDuration(duration)
    anim.setStartValue(start)
    anim.setEndValue(end)
    anim.setEasingCurve(QEasingCurve.Type.InCubic)
    anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
    return anim


def slide_in_right(widget: QWidget, distance: int = 30, duration: int = 350) -> QPropertyAnimation:
    """Slide a widget in from the right with a fade."""
    group = QParallelAnimationGroup(widget)
    # Position animation
    start_pos = widget.pos()
    from PySide6.QtCore import QPoint
    anim_pos = QPropertyAnimation(widget, b"pos", widget)
    anim_pos.setDuration(duration)
    anim_pos.setStartValue(QPoint(start_pos.x() + distance, start_pos.y()))
    anim_pos.setEndValue(start_pos)
    anim_pos.setEasingCurve(QEasingCurve.Type.OutCubic)
    group.addAnimation(anim_pos)
    # Opacity animation
    effect = QGraphicsOpacityEffect(widget)
    widget.setGraphicsEffect(effect)
    anim_op = QPropertyAnimation(effect, b"opacity", widget)
    anim_op.setDuration(duration)
    anim_op.setStartValue(0.0)
    anim_op.setEndValue(1.0)
    anim_op.setEasingCurve(QEasingCurve.Type.OutCubic)
    group.addAnimation(anim_op)
    group.start(QParallelAnimationGroup.DeletionPolicy.DeleteWhenStopped)
    return anim_pos


def smooth_value(
    animation_target: QObject,
    prop: bytes,
    start: float,
    end: float,
    duration: int = 500,
) -> QPropertyAnimation:
    """Smoothly animate a numeric property (e.g. progress bar value)."""
    anim = QPropertyAnimation(animation_target, prop, animation_target)
    anim.setDuration(duration)
    anim.setStartValue(start)
    anim.setEndValue(end)
    anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
    anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
    return anim


class PulseAnimator(QObject):
    """Creates a repeating pulse (opacity oscillation) on a widget."""

    def __init__(self, widget: QWidget, duration: int = 1200, parent: QObject | None = None):
        super().__init__(parent or widget)
        self._widget = widget
        self._effect = QGraphicsOpacityEffect(widget)
        widget.setGraphicsEffect(self._effect)
        self._effect.setOpacity(1.0)

        self._anim = QPropertyAnimation(self._effect, b"opacity", self)
        self._anim.setDuration(duration)
        self._anim.setStartValue(1.0)
        self._anim.setEndValue(0.35)
        self._anim.setEasingCurve(QEasingCurve.Type.InOutSine)
        self._anim.setLoopCount(-1)  # infinite

    def start(self) -> None:
        self._anim.start()

    def stop(self) -> None:
        self._anim.stop()
        self._effect.setOpacity(1.0)

    @property
    def running(self) -> bool:
        return self._anim.state() == QPropertyAnimation.State.Running


class StylePulseAnimator(QObject):
    """Pulsing loading indicator using stylesheet background color changes.

    Unlike PulseAnimator, this does NOT use QGraphicsOpacityEffect, avoiding
    the 'QPainter::begin: A paint device can only be painted by one painter
    at a time' error that occurs when many opacity effects run simultaneously
    inside a scroll area.
    """

    def __init__(
        self,
        widget: QWidget,
        base_color: str,
        style_template: str = "background: {color}; border-radius: 6px;",
        duration: int = 1200,
        parent: QObject | None = None,
    ):
        super().__init__(parent or widget)
        self._widget = widget
        self._style_template = style_template

        # Parse base colour and build a faded variant
        base = QColor(base_color)
        faded = QColor(base)
        faded.setAlphaF(0.35)

        self._anim = QVariantAnimation(self)
        self._anim.setDuration(duration)
        self._anim.setStartValue(base)
        self._anim.setEndValue(faded)
        self._anim.setEasingCurve(QEasingCurve.Type.InOutSine)
        self._anim.setLoopCount(-1)  # infinite
        self._anim.valueChanged.connect(self._apply)

    def _apply(self, color: QColor) -> None:
        self._widget.setStyleSheet(
            self._style_template.format(color=color.name(QColor.NameFormat.HexArgb))
        )

    def start(self) -> None:
        self._anim.start()

    def stop(self) -> None:
        self._anim.stop()

    @property
    def running(self) -> bool:
        return self._anim.state() == QVariantAnimation.State.Running


class SmoothProgressHelper(QObject):
    """Helper to animate a QProgressBar value smoothly."""

    value_changed = Signal(int)

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._current: float = 0.0
        self._anim: QPropertyAnimation | None = None

    def _get_value(self) -> float:
        return self._current

    def _set_value(self, val: float) -> None:
        self._current = val
        self.value_changed.emit(int(val))

    animated_value = Property(float, _get_value, _set_value)

    def _stop_current(self) -> None:
        """Safely stop the current animation if it exists and hasn't been deleted."""
        if self._anim is not None:
            try:
                self._anim.stop()
            except RuntimeError:
                pass  # C++ object already deleted
            self._anim = None

    def animate_to(self, target: int, duration: int = 400) -> None:
        self._stop_current()
        self._anim = QPropertyAnimation(self, b"animated_value", self)
        self._anim.setDuration(duration)
        self._anim.setStartValue(self._current)
        self._anim.setEndValue(float(target))
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        # Do NOT use DeleteWhenStopped - it deletes the C++ object while
        # our Python self._anim still references it, causing RuntimeError
        # on the next call.  We manage the lifecycle ourselves.
        self._anim.finished.connect(self._on_finished)
        self._anim.start()

    def _on_finished(self) -> None:
        self._anim = None

    def set_value_instant(self, value: int) -> None:
        self._stop_current()
        self._current = float(value)
        self.value_changed.emit(value)


def stagger_fade_in(
    widgets: list[QWidget],
    duration: int = 300,
    delay_per: int = 50,
    parent: QObject | None = None,
) -> QSequentialAnimationGroup:
    """Fade in a list of widgets with staggered delays.

    Each widget fades from 0 to 1 opacity with a configurable delay
    between each successive widget.  The returned animation group
    auto-deletes itself when finished.
    """
    group = QSequentialAnimationGroup(parent)

    for i, widget in enumerate(widgets):
        effect = widget.graphicsEffect()
        if not isinstance(effect, QGraphicsOpacityEffect):
            effect = QGraphicsOpacityEffect(widget)
            widget.setGraphicsEffect(effect)
        effect.setOpacity(0.0)
        widget.setVisible(True)

        if i > 0:
            group.addAnimation(QPauseAnimation(delay_per))

        anim = QPropertyAnimation(effect, b"opacity", widget)
        anim.setDuration(duration)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        group.addAnimation(anim)

    group.start(QSequentialAnimationGroup.DeletionPolicy.DeleteWhenStopped)
    return group
