from __future__ import annotations

from math import log10, ceil
from typing import TypedDict

from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGridLayout

from gui.widgets.animated_card import AnimatedCard
from translate import _
from constants import MAX_WEBSOCKETS, WS_TOPICS_LIMIT

DIGITS = ceil(log10(WS_TOPICS_LIMIT))


class _WSEntry(TypedDict):
    status: str
    topics: int


class WebsocketPanel(AnimatedCard):
    """
    Compact websocket status panel with click-to-expand detail grid.

    Default: shows a compact one-line summary "WS: 3/8 (150 topics)".
    Expanded: shows the full grid of websocket connections.
    """

    def __init__(self, parent=None):
        super().__init__(parent, padding=6, shadow=False)
        self._expanded = False

        # Remove card border for sidebar embedded look
        self.setProperty("class", "card-flat")

        # Compact summary (visible by default)
        self._summary_row = QHBoxLayout()
        self._summary_row.setContentsMargins(0, 0, 0, 0)

        title = QLabel(_("gui", "websocket", "name"), self)
        title.setProperty("class", "section-title")
        title.setStyleSheet("font-size: 10px; background: transparent;")
        self._summary_row.addWidget(title)

        self._summary_label = QLabel("", self)
        self._summary_label.setProperty("class", "monospace")
        self._summary_label.setStyleSheet("font-size: 10px; background: transparent;")
        self._summary_row.addWidget(self._summary_label)
        self._summary_row.addStretch(1)

        self._expand_indicator = QLabel("\u25BC", self)
        self._expand_indicator.setProperty("class", "muted")
        self._expand_indicator.setStyleSheet("font-size: 9px; background: transparent;")
        self._summary_row.addWidget(self._expand_indicator)

        self.card_layout.addLayout(self._summary_row)

        # Expandable detail grid (hidden by default)
        self._grid_widget = QWidget(self)
        grid = QGridLayout(self._grid_widget)
        grid.setSpacing(4)
        grid.setContentsMargins(0, 4, 0, 0)

        self._name_labels: list[QLabel] = []
        self._status_labels: list[QLabel] = []
        self._topic_labels: list[QLabel] = []

        _small_mono = "font-size: 10px; background: transparent;"
        for i in range(MAX_WEBSOCKETS):
            name_lbl = QLabel(
                _("gui", "websocket", "websocket").format(id=i + 1), self
            )
            name_lbl.setProperty("class", "monospace")
            name_lbl.setStyleSheet(_small_mono)
            grid.addWidget(name_lbl, i, 0)
            self._name_labels.append(name_lbl)

            status_lbl = QLabel("", self)
            status_lbl.setProperty("class", "monospace")
            status_lbl.setStyleSheet(_small_mono)
            grid.addWidget(status_lbl, i, 1)
            self._status_labels.append(status_lbl)

            topic_lbl = QLabel("", self)
            topic_lbl.setProperty("class", "monospace")
            topic_lbl.setStyleSheet(_small_mono)
            topic_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
            grid.addWidget(topic_lbl, i, 2)
            self._topic_labels.append(topic_lbl)

        self._grid_widget.setVisible(False)
        self.card_layout.addWidget(self._grid_widget)

        self._items: dict[int, _WSEntry | None] = {i: None for i in range(MAX_WEBSOCKETS)}
        self._refresh_display()

        # Make clickable
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._toggle_expanded()
        super().mousePressEvent(event)

    def _toggle_expanded(self) -> None:
        self._expanded = not self._expanded
        self._grid_widget.setVisible(self._expanded)
        self._expand_indicator.setText("\u25B2" if self._expanded else "\u25BC")

    def update(self, idx: int, status: str | None = None, topics: int | None = None) -> None:  # type: ignore[override]
        if status is None and topics is None:
            raise TypeError("You need to provide at least one of: status, topics")
        entry = self._items.get(idx)
        if entry is None:
            entry = self._items[idx] = _WSEntry(
                status=_("gui", "websocket", "disconnected"), topics=0
            )
        if status is not None:
            entry["status"] = status
        if topics is not None:
            entry["topics"] = topics
        self._refresh_display()

    def remove(self, idx: int) -> None:
        if idx in self._items:
            self._items[idx] = None
            self._refresh_display()

    def _refresh_display(self) -> None:
        active_count = 0
        total_topics = 0
        for i in range(MAX_WEBSOCKETS):
            item = self._items.get(i)
            if item is None:
                self._status_labels[i].setText("")
                self._topic_labels[i].setText("")
            else:
                active_count += 1
                total_topics += item["topics"]
                self._status_labels[i].setText(item["status"])
                self._topic_labels[i].setText(
                    f"{item['topics']:>{DIGITS}}/{WS_TOPICS_LIMIT}"
                )
        # Update compact summary
        self._summary_label.setText(
            f" {active_count}/{MAX_WEBSOCKETS} ({total_topics} topics)"
        )
