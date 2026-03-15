from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import (
    Qt, QSize, Signal, QPropertyAnimation, QEasingCurve, Property, QTimer,
)
from PySide6.QtGui import QIcon, QPainter, QPainterPath, QColor, QPaintEvent, QMouseEvent, QFont, QFontMetrics
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSizePolicy, QGraphicsOpacityEffect,
)


@dataclass
class NavItem:
    """Definition of a single navigation item."""
    icon: str          # Unicode icon character
    label: str         # Display text
    tooltip: str = ""  # Tooltip text


class _NavButton(QWidget):
    """A single navigation button with icon, label, and active indicator."""

    clicked = Signal()

    ICON_SIZE = 20
    ITEM_HEIGHT = 44
    EXPANDED_WIDTH = 180
    COLLAPSED_WIDTH = 52
    INDICATOR_WIDTH = 3
    INDICATOR_HEIGHT = 24

    def __init__(self, item: NavItem, parent: QWidget | None = None):
        super().__init__(parent)
        self._item = item
        self._active = False
        self._hovered = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(self.ITEM_HEIGHT)
        self.setToolTip(item.tooltip or item.label)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Active indicator bar (left edge)
        self._indicator = QWidget(self)
        self._indicator.setFixedSize(self.INDICATOR_WIDTH, self.INDICATOR_HEIGHT)
        self._indicator.setStyleSheet("background: transparent; border-radius: 1px;")

        # Icon label
        self._icon_label = QLabel(item.icon, self)
        self._icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._icon_label.setFixedSize(self.COLLAPSED_WIDTH, self.ITEM_HEIGHT)
        icon_font = self._icon_label.font()
        icon_font.setPixelSize(self.ICON_SIZE)
        self._icon_label.setFont(icon_font)

        # Text label
        self._text_label = QLabel(item.label, self)
        self._text_label.setStyleSheet("background: transparent;")

        layout.addWidget(self._indicator)
        layout.addWidget(self._icon_label)
        layout.addWidget(self._text_label, 1)
        layout.addSpacing(8)

    def set_active(self, active: bool) -> None:
        self._active = active
        if active:
            self._indicator.setStyleSheet(
                "background: #9146FF; border-radius: 1px;"
            )
        else:
            self._indicator.setStyleSheet(
                "background: transparent; border-radius: 1px;"
            )
        self.update()

    def set_collapsed(self, collapsed: bool) -> None:
        self._text_label.setVisible(not collapsed)

    def enterEvent(self, event) -> None:
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

    def paintEvent(self, event: QPaintEvent) -> None:
        if self._hovered or self._active:
            p = QPainter(self)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            if self._active:
                color = QColor("#9146FF")
                color.setAlpha(25)
            else:
                color = QColor(128, 128, 128, 20)
            from PySide6.QtCore import QRectF
            rect = QRectF(self.INDICATOR_WIDTH + 4, 2, self.width() - self.INDICATOR_WIDTH - 8, self.height() - 4)
            path = QPainterPath()
            path.addRoundedRect(rect, 6, 6)
            p.fillPath(path, color)
            p.end()
        super().paintEvent(event)


class NavSidebar(QWidget):
    """
    Collapsible sidebar navigation with icon + label items.

    Emits `tab_changed(int)` when the user clicks a different nav item.
    """

    tab_changed = Signal(int)

    EXPANDED_WIDTH = 180
    COLLAPSED_WIDTH = 52
    ANIMATION_DURATION = 250

    def __init__(self, items: list[NavItem], parent: QWidget | None = None):
        super().__init__(parent)
        self._collapsed = False
        self._buttons: list[_NavButton] = []
        self._current_index = 0

        self.setFixedWidth(self.EXPANDED_WIDTH)
        self.setStyleSheet("background: transparent;")

        # Width animation
        self._width_anim = QPropertyAnimation(self, b"maximumWidth", self)
        self._width_anim.setDuration(self.ANIMATION_DURATION)
        self._width_anim.setEasingCurve(QEasingCurve.Type.InOutCubic)

        self._min_width_anim = QPropertyAnimation(self, b"minimumWidth", self)
        self._min_width_anim.setDuration(self.ANIMATION_DURATION)
        self._min_width_anim.setEasingCurve(QEasingCurve.Type.InOutCubic)

        # Layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 8)
        layout.setSpacing(2)

        # App title area
        self._title_label = QLabel("TDM", self)
        title_font = self._title_label.font()
        title_font.setPixelSize(18)
        title_font.setWeight(QFont.Weight.Bold)
        self._title_label.setFont(title_font)
        self._title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._title_label.setFixedHeight(48)
        self._title_label.setStyleSheet("color: #9146FF; background: transparent;")
        layout.addWidget(self._title_label)

        layout.addSpacing(12)

        # Navigation buttons
        for i, item in enumerate(items):
            btn = _NavButton(item, self)
            btn.clicked.connect(lambda idx=i: self._on_clicked(idx))
            self._buttons.append(btn)
            layout.addWidget(btn)

        layout.addStretch(1)

        # Collapse toggle button
        self._collapse_btn = _NavButton(NavItem(icon="\u276E", label="Collapse"), self)
        self._collapse_btn.clicked.connect(self.toggle_collapsed)
        layout.addWidget(self._collapse_btn)

        # Set initial active
        if self._buttons:
            self._buttons[0].set_active(True)

    def _on_clicked(self, index: int) -> None:
        if index == self._current_index:
            return
        if 0 <= self._current_index < len(self._buttons):
            self._buttons[self._current_index].set_active(False)
        self._current_index = index
        self._buttons[index].set_active(True)
        self.tab_changed.emit(index)

    def current_index(self) -> int:
        return self._current_index

    def set_current_index(self, index: int) -> None:
        self._on_clicked(index)

    def toggle_collapsed(self) -> None:
        self._collapsed = not self._collapsed
        target_width = self.COLLAPSED_WIDTH if self._collapsed else self.EXPANDED_WIDTH

        self._width_anim.stop()
        self._width_anim.setStartValue(self.width())
        self._width_anim.setEndValue(target_width)
        self._width_anim.start()

        self._min_width_anim.stop()
        self._min_width_anim.setStartValue(self.minimumWidth())
        self._min_width_anim.setEndValue(target_width)
        self._min_width_anim.start()

        for btn in self._buttons:
            btn.set_collapsed(self._collapsed)
        self._collapse_btn.set_collapsed(self._collapsed)
        self._title_label.setVisible(not self._collapsed)
        # Update collapse icon
        icon = "\u276F" if self._collapsed else "\u276E"
        self._collapse_btn._item.icon = icon
        self._collapse_btn._icon_label.setText(icon)

    @property
    def is_collapsed(self) -> bool:
        return self._collapsed
