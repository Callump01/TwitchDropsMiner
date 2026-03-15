from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QSizePolicy,
)

from gui.widgets.status_card import StatusCard
from gui.widgets.login_card import LoginCard
from gui.widgets.websocket_panel import WebsocketPanel
from gui.widgets.progress_card import ProgressCard
from gui.widgets.console_output import ConsoleOutput
from gui.widgets.channel_table import ChannelTable


class MainTab(QWidget):
    """
    Dashboard / Main tab.

    Layout (top to bottom):
    ┌─────────────────────────────────────────────┐
    │  [Status Card]            [Login Card]       │
    ├─────────────────────────────────────────────┤
    │  [Campaign Progress Card]                    │
    ├──────────────────┬──────────────────────────┤
    │  [Websocket]     │  [Channel Table]          │
    │  [Console]       │                           │
    └──────────────────┴──────────────────────────┘
    """

    def __init__(self, manager, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Top row: Status + Login
        top_row = QHBoxLayout()
        top_row.setSpacing(12)

        self.status = StatusCard(self)
        self.status.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        top_row.addWidget(self.status, 2)

        self.login = LoginCard(manager, self)
        self.login.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        top_row.addWidget(self.login, 1)

        layout.addLayout(top_row)

        # Campaign progress
        self.progress = ProgressCard(manager, self)
        layout.addWidget(self.progress)

        # Bottom split: Left (websocket + console) / Right (channels)
        bottom_splitter = QSplitter(Qt.Orientation.Horizontal, self)
        bottom_splitter.setChildrenCollapsible(False)

        # Left column
        left_widget = QWidget(self)
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(12)

        self.websockets = WebsocketPanel(self)
        left_layout.addWidget(self.websockets)

        self.output = ConsoleOutput(self)
        left_layout.addWidget(self.output, 1)

        bottom_splitter.addWidget(left_widget)

        # Right column
        self.channels = ChannelTable(manager, self)
        bottom_splitter.addWidget(self.channels)

        # Set initial split ratio (40% left, 60% right)
        bottom_splitter.setStretchFactor(0, 2)
        bottom_splitter.setStretchFactor(1, 3)

        layout.addWidget(bottom_splitter, 1)
