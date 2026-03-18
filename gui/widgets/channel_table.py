from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QModelIndex, QEvent
from PySide6.QtGui import QFont, QColor, QStandardItemModel, QStandardItem
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTreeView, QPushButton,
    QHeaderView, QAbstractItemView, QLabel,
)

from gui.widgets.animated_card import AnimatedCard
from translate import _
from constants import State

if TYPE_CHECKING:
    from channel import Channel


class ChannelTable(AnimatedCard):
    """
    Modern channel list using QTreeView with styled rows.

    Features:
    - Row hover highlight
    - 'Watching' row highlighted with accent colour
    - Switch button to change channel
    - Sortable columns
    """

    COLUMNS = ["channel", "status", "game", "drops", "viewers", "acl_base"]
    COLUMN_HEADERS = {
        "channel": "Channel",
        "status": "Status",
        "game": "Game",
        "drops": "\U0001f381",   # gift emoji
        "viewers": "Viewers",
        "acl_base": "\U0001f4cb",  # clipboard emoji
    }

    def __init__(self, manager, parent=None):
        super().__init__(parent, padding=0)
        self._manager = manager

        inner = QVBoxLayout()
        inner.setContentsMargins(12, 10, 12, 10)
        inner.setSpacing(8)

        # Header row
        header_row = QHBoxLayout()
        title = QLabel(_("gui", "channels", "name"), self)
        title.setProperty("class", "section-title")
        header_row.addWidget(title)
        header_row.addStretch(1)

        self._switch_btn = QPushButton(_("gui", "channels", "switch"), self)
        self._switch_btn.setEnabled(False)
        self._switch_btn.setFixedWidth(90)
        self._switch_btn.clicked.connect(self._on_switch)
        header_row.addWidget(self._switch_btn)
        inner.addLayout(header_row)

        # Model
        self._model = QStandardItemModel(self)
        # Initialize headers from translations
        headers = []
        for col in self.COLUMNS:
            if col in ("drops", "acl_base"):
                headers.append(self.COLUMN_HEADERS[col])
            elif col == "channel":
                headers.append(_("gui", "channels", "headings", "channel"))
            elif col == "status":
                headers.append(_("gui", "channels", "headings", "status"))
            elif col == "game":
                headers.append(_("gui", "channels", "headings", "game"))
            elif col == "viewers":
                headers.append(_("gui", "channels", "headings", "viewers"))
            else:
                headers.append(col)
        self._model.setHorizontalHeaderLabels(headers)

        # Tree view
        self._tree = QTreeView(self)
        self._tree.setModel(self._model)
        self._tree.setRootIsDecorated(False)
        self._tree.setAlternatingRowColors(True)
        self._tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._tree.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._tree.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._tree.setSortingEnabled(False)
        self._tree.setMinimumHeight(150)

        # Header sizing
        h = self._tree.header()
        h.setStretchLastSection(True)
        h.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        for i, col in enumerate(self.COLUMNS):
            if col == "channel":
                h.resizeSection(i, 120)
            elif col in ("drops", "acl_base"):
                h.resizeSection(i, 40)
                h.setSectionResizeMode(i, QHeaderView.ResizeMode.Fixed)
            elif col == "status":
                h.resizeSection(i, 100)
            elif col == "game":
                h.resizeSection(i, 130)
            elif col == "viewers":
                h.resizeSection(i, 80)

        self._tree.selectionModel().selectionChanged.connect(self._on_selection_changed)
        inner.addWidget(self._tree, 1)

        # Empty state overlay
        self._empty_label = QLabel(_("gui", "channels", "empty"), self._tree)
        self._empty_label.setProperty("class", "muted")
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setWordWrap(True)

        self.card_layout.addLayout(inner)

        # Install event filter to reposition empty label on resize
        self._tree.viewport().installEventFilter(self)

        self._channel_map: dict[int, Channel] = {}  # iid -> channel
        self._row_map: dict[int, int] = {}  # iid -> row index
        self._watching_iid: int | None = None

    def _update_empty_state(self) -> None:
        has_rows = self._model.rowCount() > 0
        self._empty_label.setVisible(not has_rows)
        if not has_rows:
            # Reposition label over the viewport area
            vp = self._tree.viewport()
            self._empty_label.setGeometry(vp.geometry())

    def eventFilter(self, obj, event):  # type: ignore[override]
        if obj is self._tree.viewport() and event.type() == QEvent.Type.Resize:
            if self._empty_label.isVisible():
                self._empty_label.setGeometry(self._tree.viewport().geometry())
        return super().eventFilter(obj, event)

    def _on_switch(self) -> None:
        self._manager._twitch.state_change(State.CHANNEL_SWITCH)()

    def _on_selection_changed(self) -> None:
        has_selection = bool(self._tree.selectionModel().selectedRows())
        self._switch_btn.setEnabled(has_selection)

    def _make_row(self, channel: Channel) -> list[QStandardItem]:
        # status
        if channel.online:
            status = _("gui", "channels", "online")
        elif channel.pending_online:
            status = _("gui", "channels", "pending")
        else:
            status = _("gui", "channels", "offline")
        game = str(channel.game or '')
        drops = "\u2714" if channel.drops_enabled else "\u274C"
        viewers = str(channel.viewers) if channel.viewers is not None else ''
        acl = "\u2714" if channel.acl_based else "\u274C"

        items = []
        for col, val in zip(self.COLUMNS, [channel.name, status, game, drops, viewers, acl]):
            item = QStandardItem(val)
            item.setData(channel.iid, Qt.ItemDataRole.UserRole)
            if col in ("drops", "acl_base", "viewers"):
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            items.append(item)
        return items

    def _highlight_watching_row(self, row: int, watching: bool) -> None:
        for col in range(self._model.columnCount()):
            item = self._model.item(row, col)
            if item is not None:
                if watching:
                    item.setBackground(QColor("#9146FF"))
                    item.setForeground(QColor("#FFFFFF"))
                else:
                    item.setData(None, Qt.ItemDataRole.BackgroundRole)
                    item.setData(None, Qt.ItemDataRole.ForegroundRole)

    # ---- Public API (matches original interface) ----
    def display(self, channel: Channel, *, add: bool = False) -> None:
        iid = channel.iid
        if not add and iid not in self._channel_map:
            return
        if iid in self._row_map:
            # Update existing row
            row = self._row_map[iid]
            new_items = self._make_row(channel)
            for col, item in enumerate(new_items):
                self._model.setItem(row, col, item)
            if self._watching_iid == iid:
                self._highlight_watching_row(row, True)
        elif add:
            self._channel_map[iid] = channel
            row = self._model.rowCount()
            self._row_map[iid] = row
            self._model.appendRow(self._make_row(channel))
            self._update_empty_state()

    def remove(self, channel: Channel) -> None:
        iid = channel.iid
        if iid in self._row_map:
            row = self._row_map[iid]
            self._model.removeRow(row)
            del self._channel_map[iid]
            del self._row_map[iid]
            # Rebuild row map after removal
            self._row_map = {}
            for r in range(self._model.rowCount()):
                item = self._model.item(r, 0)
                if item is not None:
                    r_iid = item.data(Qt.ItemDataRole.UserRole)
                    self._row_map[r_iid] = r
            self._update_empty_state()

    def clear(self) -> None:
        self._model.removeRows(0, self._model.rowCount())
        self._channel_map.clear()
        self._row_map.clear()
        self._watching_iid = None
        self._update_empty_state()

    def clear_watching(self) -> None:
        if self._watching_iid is not None and self._watching_iid in self._row_map:
            self._highlight_watching_row(self._row_map[self._watching_iid], False)
        self._watching_iid = None

    def set_watching(self, channel: Channel) -> None:
        self.clear_watching()
        iid = channel.iid
        if iid in self._row_map:
            self._watching_iid = iid
            row = self._row_map[iid]
            self._highlight_watching_row(row, True)
            self._tree.scrollTo(self._model.index(row, 0))

    def get_selection(self) -> Channel | None:
        indexes = self._tree.selectionModel().selectedRows()
        if not indexes:
            return None
        item = self._model.item(indexes[0].row(), 0)
        if item is None:
            return None
        iid = item.data(Qt.ItemDataRole.UserRole)
        return self._channel_map.get(iid)

    def clear_selection(self) -> None:
        self._tree.clearSelection()

    def shrink(self) -> None:
        # Qt handles column sizing automatically; this is a no-op compatibility method
        pass
