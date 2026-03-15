from __future__ import annotations

from math import log10, ceil
from typing import TypedDict

from PySide6.QtCore import Qt
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
    Compact websocket status panel displaying status and topic counts.

    Shows up to MAX_WEBSOCKETS (8) websocket connections in a compact grid.
    """

    def __init__(self, parent=None):
        super().__init__(parent, padding=10)

        title = QLabel(_("gui", "websocket", "name"), self)
        title.setProperty("class", "section-title")
        self.card_layout.addWidget(title)

        # Grid of websocket statuses
        grid = QGridLayout()
        grid.setSpacing(4)
        grid.setContentsMargins(0, 4, 0, 0)

        self._name_labels: list[QLabel] = []
        self._status_labels: list[QLabel] = []
        self._topic_labels: list[QLabel] = []

        for i in range(MAX_WEBSOCKETS):
            name_lbl = QLabel(
                _("gui", "websocket", "websocket").format(id=i + 1), self
            )
            name_lbl.setProperty("class", "monospace")
            grid.addWidget(name_lbl, i, 0)
            self._name_labels.append(name_lbl)

            status_lbl = QLabel("", self)
            status_lbl.setProperty("class", "monospace")
            status_lbl.setMinimumWidth(110)
            grid.addWidget(status_lbl, i, 1)
            self._status_labels.append(status_lbl)

            topic_lbl = QLabel("", self)
            topic_lbl.setProperty("class", "monospace")
            topic_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
            grid.addWidget(topic_lbl, i, 2)
            self._topic_labels.append(topic_lbl)

        self.card_layout.addLayout(grid)

        self._items: dict[int, _WSEntry | None] = {i: None for i in range(MAX_WEBSOCKETS)}
        self._refresh_display()

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
        for i in range(MAX_WEBSOCKETS):
            item = self._items.get(i)
            if item is None:
                self._status_labels[i].setText("")
                self._topic_labels[i].setText("")
            else:
                self._status_labels[i].setText(item["status"])
                self._topic_labels[i].setText(
                    f"{item['topics']:>{DIGITS}}/{WS_TOPICS_LIMIT}"
                )
