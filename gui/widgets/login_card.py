from __future__ import annotations

import re
import asyncio
from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
)

from gui.widgets.animated_card import AnimatedCard
from gui.widgets.placeholder_input import PlaceholderLineEdit

from translate import _


@dataclass
class LoginData:
    username: str
    password: str
    token: str


class LoginCard(AnimatedCard):
    """
    Login card matching the original tkinter LoginForm interface exactly.

    Default state: shows status + user ID labels and a Login button.
    The entry fields (username/password/2FA) are hidden by default and only
    shown when the password-based fallback flow is triggered via ask_login().
    The primary login flow is device-code based via ask_enter_code().
    """

    COMPACT_HEIGHT = 64  # matches StatusCard

    def __init__(self, manager, parent=None):
        super().__init__(parent, padding=12)
        self._manager = manager

        # ---- Status row: labels showing "Status:" / "User ID:" ----
        status_row = QHBoxLayout()
        status_row.setSpacing(8)

        title = QLabel("Twitch Account", self)
        title.setProperty("class", "section-title")
        status_row.addWidget(title)
        status_row.addStretch(1)

        # Labels column (matches original: "Status:\nUser ID:")
        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)
        info_layout.setContentsMargins(0, 0, 0, 0)

        self._status_label = QLabel("", self)
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info_layout.addWidget(self._status_label)

        self._user_id_label = QLabel("", self)
        self._user_id_label.setProperty("class", "muted")
        self._user_id_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info_layout.addWidget(self._user_id_label)

        status_row.addLayout(info_layout)
        self.card_layout.addLayout(status_row)

        # ---- Hidden form fields (only shown in password fallback flow) ----
        self._form_widget = QWidget(self)
        form_layout = QVBoxLayout(self._form_widget)
        form_layout.setContentsMargins(0, 8, 0, 0)
        form_layout.setSpacing(8)

        self._login_entry = PlaceholderLineEdit(
            self._form_widget, placeholder=_("gui", "login", "username")
        )
        form_layout.addWidget(self._login_entry)
        self._login_error = QLabel(self._form_widget)
        self._login_error.setProperty("class", "error")
        self._login_error.setVisible(False)
        form_layout.addWidget(self._login_error)

        self._pass_entry = PlaceholderLineEdit(
            self._form_widget, placeholder=_("gui", "login", "password"), password=True
        )
        form_layout.addWidget(self._pass_entry)
        self._pass_error = QLabel(self._form_widget)
        self._pass_error.setProperty("class", "error")
        self._pass_error.setVisible(False)
        form_layout.addWidget(self._pass_error)

        self._token_entry = PlaceholderLineEdit(
            self._form_widget, placeholder=_("gui", "login", "twofa_code")
        )
        form_layout.addWidget(self._token_entry)
        self._token_error = QLabel(self._form_widget)
        self._token_error.setProperty("class", "error")
        self._token_error.setVisible(False)
        form_layout.addWidget(self._token_error)

        self.card_layout.addWidget(self._form_widget)
        # Hidden by default - matches original where entry.grid() calls are commented out
        self._form_widget.setVisible(False)

        # ---- Login button (always visible) ----
        self._confirm = asyncio.Event()
        self._button = QPushButton(_("gui", "login", "button"), self)
        self._button.setProperty("class", "accent")
        self._button.setEnabled(False)
        self._button.clicked.connect(self._confirm.set)
        self.card_layout.addWidget(self._button)

        self.update(_("gui", "login", "logged_out"), None)

    # ---- Public API (matches original tkinter LoginForm exactly) ----

    def clear(self, login: bool = False, password: bool = False, token: bool = False) -> None:
        clear_all = not login and not password and not token
        if login or clear_all:
            self._login_entry.clear()
        if password or clear_all:
            self._pass_entry.clear()
        if token or clear_all:
            self._token_entry.clear()

    async def wait_for_login_press(self) -> None:
        self._confirm.clear()
        try:
            self._button.setEnabled(True)
            await self._manager.coro_unless_closed(self._confirm.wait())
        finally:
            self._button.setEnabled(False)

    async def ask_login(self) -> LoginData:
        """Password-based login fallback. Shows form fields and waits for input."""
        self.update(_("gui", "login", "required"), None)
        # Show the form fields for this flow
        self._form_widget.setVisible(True)
        self._manager.grab_attention(sound=False)
        while True:
            self._manager.print(_("gui", "login", "request"))
            await self.wait_for_login_press()
            login_data = LoginData(
                self._login_entry.get().strip(),
                self._pass_entry.get(),
                self._token_entry.get().strip(),
            )
            # Hide previous error messages
            self._login_error.setVisible(False)
            self._pass_error.setVisible(False)
            self._token_error.setVisible(False)
            # Basic input validation
            if not (
                3 <= len(login_data.username) <= 25
                and re.match(r'^[a-zA-Z0-9_]+$', login_data.username)
            ):
                self._login_error.setText(_("gui", "login", "error_username"))
                self._login_error.setVisible(True)
                self.clear(login=True)
                continue
            if len(login_data.password) < 8:
                self._pass_error.setText(_("gui", "login", "error_password"))
                self._pass_error.setVisible(True)
                self.clear(password=True)
                continue
            if login_data.token and len(login_data.token) < 6:
                self._token_error.setText(_("gui", "login", "error_token"))
                self._token_error.setVisible(True)
                self.clear(token=True)
                continue
            return login_data

    async def ask_enter_code(self, page_url, user_code: str) -> None:
        """Device-code login flow (primary). Shows code, opens browser."""
        from utils import webopen
        self.update(_("gui", "login", "required"), None)
        # Do NOT show form fields - this is the device code flow
        self._manager.grab_attention(sound=False)
        self._manager.print(_("gui", "login", "request"))
        await self.wait_for_login_press()
        self._manager.print(f"Enter this code on the Twitch's device activation page: {user_code}")
        await asyncio.sleep(4)
        webopen(page_url)

    def update(self, status: str, user_id: int | None) -> None:  # type: ignore[override]
        """Update the status and user ID display."""
        self._status_label.setText(status)
        if user_id is not None:
            self._user_id_label.setText(f"ID: {user_id}")
            # Compact mode when logged in - match StatusCard height
            self._form_widget.setVisible(False)
            self._button.setVisible(False)
            self.setFixedHeight(self.COMPACT_HEIGHT)
        else:
            self._user_id_label.setText("ID: -")
            self._button.setVisible(True)
            self.setMinimumHeight(0)
            self.setMaximumHeight(16777215)  # QWIDGETSIZE_MAX
