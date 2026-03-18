from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSizePolicy,
)

from gui.widgets.status_card import StatusCard
from gui.widgets.login_card import LoginCard
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
    │  [Progress Card - hero with ring + segments] │
    ├─────────────────────────────────────────────┤
    │  [Channel Table - full width]                │
    ├─────────────────────────────────────────────┤
    │  [Console Output]                            │
    └─────────────────────────────────────────────┘

    WebsocketPanel lives in the sidebar (set by GUIManager).
    """

    def __init__(self, manager, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Top row: Status + Login (compact)
        top_row = QHBoxLayout()
        top_row.setSpacing(12)

        self.status = StatusCard(manager, self)
        self.status.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        top_row.addWidget(self.status, 2)

        self.login = LoginCard(manager, self)
        self.login.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        top_row.addWidget(self.login, 1)

        layout.addLayout(top_row)

        # Hero: Campaign progress card (never squished)
        self.progress = ProgressCard(manager, self)
        self.progress.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout.addWidget(self.progress)

        # Channel table (takes remaining vertical space)
        self.channels = ChannelTable(manager, self)
        layout.addWidget(self.channels, 1)

        # Console output (fixed height at bottom)
        self.output = ConsoleOutput(self)
        self.output.setFixedHeight(180)
        layout.addWidget(self.output)
