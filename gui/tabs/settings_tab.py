from __future__ import annotations

import os
import sys
import shlex
import plistlib
from pathlib import Path
from textwrap import dedent
from functools import partial, cached_property
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QPushButton, QComboBox, QListWidget, QScrollArea, QFrame,
    QSizePolicy,
)

from gui.widgets.animated_card import AnimatedCard
from gui.widgets.toggle_switch import ToggleSwitch
from gui.widgets.placeholder_input import PlaceholderLineEdit, PlaceholderComboBox
from translate import _
from constants import (
    MAX_INT, SELF_PATH, IS_PACKAGED, SCRIPTS_PATH,
    LOGGING_LEVELS, State, PriorityMode,
)

if sys.platform == "win32":
    from registry import RegistryKey, ValueType, ValueNotFound

if TYPE_CHECKING:
    from gui.manager import GUIManager
    from settings import Settings
    from utils import Game


def _proxy_validate(entry: PlaceholderLineEdit, settings: Settings) -> bool:
    from yarl import URL
    raw_url = entry.get().strip()
    entry.replace(raw_url)
    url = URL(raw_url)
    valid = url.host is not None and url.port is not None
    if not valid:
        entry.clear()
        url = URL()
    settings.proxy = url
    return valid


class SettingsTab(QWidget):
    """
    Settings panel with toggle switches, modern lists, and comboboxes.

    Sections: General, Advanced, Priority List, Exclude List, Reload.
    """

    AUTOSTART_NAME: str = "TwitchDropsMiner"
    AUTOSTART_KEY: str = "HKCU/Software/Microsoft/Windows/CurrentVersion/Run"

    @cached_property
    def PRIORITY_MODES(self) -> dict[PriorityMode, str]:
        return {
            PriorityMode.PRIORITY_ONLY: _("gui", "settings", "priority_modes", "priority_only"),
            PriorityMode.ENDING_SOONEST: _("gui", "settings", "priority_modes", "ending_soonest"),
            PriorityMode.LOW_AVBL_FIRST: _(
                "gui", "settings", "priority_modes", "low_availability"
            ),
        }

    def __init__(self, manager: GUIManager, parent=None):
        super().__init__(parent)
        self._manager = manager
        self._settings: Settings = manager._twitch.settings
        self._game_names: set[str] = set()

        priority_mode = self._settings.priority_mode
        if priority_mode not in self.PRIORITY_MODES:
            priority_mode = PriorityMode.PRIORITY_ONLY
            self._settings.priority_mode = priority_mode

        # Scroll area for the whole settings page
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        container = QWidget()
        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(16)

        # ---- General Section ----
        general_card = AnimatedCard(container, padding=16)
        gen_layout = general_card.card_layout
        gen_title = QLabel(_("gui", "settings", "general", "name"), general_card)
        gen_title.setProperty("class", "heading")
        gen_layout.addWidget(gen_title)

        gen_grid = QGridLayout()
        gen_grid.setSpacing(10)
        gen_grid.setColumnStretch(1, 1)
        row = 0

        # Language
        gen_grid.addWidget(QLabel("Language (requires restart):", general_card), row, 0)
        self._language_combo = QComboBox(general_card)
        self._language_combo.addItems(list(_.languages))
        self._language_combo.setCurrentText(_.current)
        self._language_combo.currentTextChanged.connect(
            lambda t: setattr(self._settings, "language", t)
        )
        gen_grid.addWidget(self._language_combo, row, 1)
        row += 1

        # Autostart
        gen_grid.addWidget(
            QLabel(_("gui", "settings", "general", "autostart"), general_card), row, 0
        )
        self._autostart_toggle = ToggleSwitch(general_card, checked=False)
        self._autostart_toggle.toggled.connect(lambda _: self.update_autostart())
        gen_grid.addWidget(self._autostart_toggle, row, 1)
        row += 1

        # Tray options (hidden on macOS)
        if sys.platform != "darwin":
            gen_grid.addWidget(
                QLabel(_("gui", "settings", "general", "tray"), general_card), row, 0
            )
            self._tray_toggle = ToggleSwitch(
                general_card, checked=self._settings.autostart_tray
            )
            self._tray_toggle.toggled.connect(lambda _: self.update_autostart())
            gen_grid.addWidget(self._tray_toggle, row, 1)
            row += 1

            gen_grid.addWidget(
                QLabel(_("gui", "settings", "general", "tray_notifications"), general_card), row, 0
            )
            self._notif_toggle = ToggleSwitch(
                general_card, checked=self._settings.tray_notifications
            )
            self._notif_toggle.toggled.connect(
                lambda v: setattr(self._settings, "tray_notifications", v)
            )
            gen_grid.addWidget(self._notif_toggle, row, 1)
            row += 1
        else:
            self._tray_toggle = None
            self._notif_toggle = None

        # Dark mode
        gen_grid.addWidget(
            QLabel(_("gui", "settings", "general", "dark_mode"), general_card), row, 0
        )
        self._dark_toggle = ToggleSwitch(
            general_card, checked=self._settings.dark_mode
        )
        self._dark_toggle.toggled.connect(self._on_dark_mode_toggled)
        gen_grid.addWidget(self._dark_toggle, row, 1)
        row += 1

        # Priority mode
        gen_grid.addWidget(
            QLabel(_("gui", "settings", "general", "priority_mode"), general_card), row, 0
        )
        self._priority_mode_combo = QComboBox(general_card)
        self._priority_mode_combo.addItems(list(self.PRIORITY_MODES.values()))
        self._priority_mode_combo.setCurrentText(self.PRIORITY_MODES[priority_mode])
        self._priority_mode_combo.currentTextChanged.connect(self._on_priority_mode)
        gen_grid.addWidget(self._priority_mode_combo, row, 1)
        row += 1

        # Proxy
        gen_grid.addWidget(
            QLabel(_("gui", "settings", "general", "proxy"), general_card), row, 0
        )
        self._proxy_entry = PlaceholderLineEdit(
            general_card,
            placeholder="http://username:password@address:port",
            prefill="http://",
        )
        self._proxy_entry.setText(str(self._settings.proxy))
        self._proxy_entry.editingFinished.connect(self._on_proxy_validate)
        gen_grid.addWidget(self._proxy_entry, row, 1)
        row += 1

        # Proxy error label (hidden by default)
        self._proxy_error = QLabel(_("gui", "settings", "proxy_error"), general_card)
        self._proxy_error.setProperty("class", "error")
        self._proxy_error.setVisible(False)
        gen_grid.addWidget(self._proxy_error, row, 1)
        row += 1

        gen_layout.addLayout(gen_grid)
        main_layout.addWidget(general_card)

        # ---- Advanced Section ----
        adv_card = AnimatedCard(container, padding=16)
        adv_layout = adv_card.card_layout
        adv_title = QLabel(_("gui", "settings", "advanced", "name"), adv_card)
        adv_title.setProperty("class", "heading")
        adv_layout.addWidget(adv_title)

        warn_label = QLabel(_("gui", "settings", "advanced", "warning"), adv_card)
        warn_label.setProperty("class", "error")
        adv_layout.addWidget(warn_label)
        warn_text = QLabel(_("gui", "settings", "advanced", "warning_text"), adv_card)
        warn_text.setProperty("class", "warning")
        warn_text.setWordWrap(True)
        adv_layout.addWidget(warn_text)

        adv_grid = QGridLayout()
        adv_grid.setSpacing(10)
        arow = 0

        adv_grid.addWidget(
            QLabel(_("gui", "settings", "advanced", "enable_badges_emotes"), adv_card), arow, 0
        )
        self._badges_toggle = ToggleSwitch(
            adv_card, checked=self._settings.enable_badges_emotes
        )
        self._badges_toggle.toggled.connect(
            lambda v: setattr(self._settings, "enable_badges_emotes", v)
        )
        adv_grid.addWidget(self._badges_toggle, arow, 1)
        arow += 1

        adv_grid.addWidget(
            QLabel(_("gui", "settings", "advanced", "available_drops_check"), adv_card), arow, 0
        )
        self._drops_check_toggle = ToggleSwitch(
            adv_card, checked=self._settings.available_drops_check
        )
        self._drops_check_toggle.toggled.connect(
            lambda v: setattr(self._settings, "available_drops_check", v)
        )
        adv_grid.addWidget(self._drops_check_toggle, arow, 1)
        arow += 1

        adv_layout.addLayout(adv_grid)
        main_layout.addWidget(adv_card)

        # ---- Priority & Exclude in side-by-side layout ----
        lists_row = QHBoxLayout()
        lists_row.setSpacing(16)

        # Priority list
        prio_card = AnimatedCard(container, padding=16)
        prio_layout = prio_card.card_layout
        prio_title = QLabel(_("gui", "settings", "priority"), prio_card)
        prio_title.setProperty("class", "heading")
        prio_layout.addWidget(prio_title)

        prio_input_row = QHBoxLayout()
        self._priority_entry = PlaceholderComboBox(
            prio_card, placeholder=_("gui", "settings", "game_name"), width=200
        )
        prio_input_row.addWidget(self._priority_entry, 1)
        prio_add_btn = QPushButton("+", prio_card)
        prio_add_btn.setFixedWidth(36)
        prio_add_btn.setProperty("class", "accent")
        prio_add_btn.clicked.connect(self.priority_add)
        prio_input_row.addWidget(prio_add_btn)
        prio_layout.addLayout(prio_input_row)

        prio_list_row = QHBoxLayout()
        self._priority_list = QListWidget(prio_card)
        self._priority_list.setMinimumHeight(200)
        self._priority_list.addItems(self._settings.priority)

        # Empty state overlay for priority list
        self._priority_empty = QLabel(
            _("gui", "settings", "priority_empty"), self._priority_list
        )
        self._priority_empty.setProperty("class", "muted")
        self._priority_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._priority_empty.setWordWrap(True)
        self._priority_empty.setVisible(self._priority_list.count() == 0)

        prio_list_row.addWidget(self._priority_list, 1)

        # Move/delete buttons
        btn_col = QVBoxLayout()
        btn_col.setSpacing(4)
        for text, amount in [("\u21C8", MAX_INT), ("\u2191", 1), ("\u2193", -1), ("\u21CA", -MAX_INT)]:
            btn = QPushButton(text, prio_card)
            btn.setFixedSize(36, 36)
            btn.setProperty("class", "icon-btn")
            btn.clicked.connect(partial(self.priority_move, amount))
            btn_col.addWidget(btn)
        del_btn = QPushButton("\u274C", prio_card)
        del_btn.setFixedSize(36, 36)
        del_btn.setProperty("class", "icon-btn")
        del_btn.clicked.connect(self.priority_delete)
        btn_col.addWidget(del_btn)
        btn_col.addStretch(1)
        prio_list_row.addLayout(btn_col)
        prio_layout.addLayout(prio_list_row)
        lists_row.addWidget(prio_card, 1)

        # Exclude list
        excl_card = AnimatedCard(container, padding=16)
        excl_layout = excl_card.card_layout
        excl_title = QLabel(_("gui", "settings", "exclude"), excl_card)
        excl_title.setProperty("class", "heading")
        excl_layout.addWidget(excl_title)

        excl_input_row = QHBoxLayout()
        self._exclude_entry = PlaceholderComboBox(
            excl_card, placeholder=_("gui", "settings", "game_name"), width=200
        )
        excl_input_row.addWidget(self._exclude_entry, 1)
        excl_add_btn = QPushButton("+", excl_card)
        excl_add_btn.setFixedWidth(36)
        excl_add_btn.setProperty("class", "accent")
        excl_add_btn.clicked.connect(self.exclude_add)
        excl_input_row.addWidget(excl_add_btn)
        excl_layout.addLayout(excl_input_row)

        self._exclude_list = QListWidget(excl_card)
        self._exclude_list.setMinimumHeight(200)
        self._exclude_list.addItems(sorted(self._settings.exclude))

        # Empty state overlay for exclude list
        self._exclude_empty = QLabel(
            _("gui", "settings", "exclude_empty"), self._exclude_list
        )
        self._exclude_empty.setProperty("class", "muted")
        self._exclude_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._exclude_empty.setWordWrap(True)
        self._exclude_empty.setVisible(self._exclude_list.count() == 0)

        excl_layout.addWidget(self._exclude_list)

        excl_del_btn = QPushButton("\u274C  Remove Selected", excl_card)
        excl_del_btn.clicked.connect(self.exclude_delete)
        excl_layout.addWidget(excl_del_btn)
        lists_row.addWidget(excl_card, 1)

        main_layout.addLayout(lists_row)

        # ---- Reload Button ----
        reload_row = QHBoxLayout()
        reload_row.addStretch(1)
        reload_label = QLabel(_("gui", "settings", "reload_text"), container)
        reload_label.setProperty("class", "muted")
        reload_row.addWidget(reload_label)
        reload_btn = QPushButton(_("gui", "settings", "reload"), container)
        reload_btn.setProperty("class", "accent")
        reload_btn.clicked.connect(
            self._manager._twitch.state_change(State.INVENTORY_FETCH)
        )
        reload_row.addWidget(reload_btn)
        reload_row.addStretch(1)
        main_layout.addLayout(reload_row)

        main_layout.addStretch(1)

        scroll.setWidget(container)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

        # Initialize autostart state
        self._autostart_toggle.setChecked(self._query_autostart(), animated=False)

    # ---- Proxy validation ----
    def _on_proxy_validate(self) -> None:
        valid = _proxy_validate(self._proxy_entry, self._settings)
        self._proxy_error.setVisible(not valid)
        self._proxy_entry.setProperty("error", "true" if not valid else "false")
        # Force style refresh after dynamic property change
        self._proxy_entry.style().unpolish(self._proxy_entry)
        self._proxy_entry.style().polish(self._proxy_entry)

    # ---- Dark mode ----
    def _on_dark_mode_toggled(self, checked: bool) -> None:
        self._settings.dark_mode = checked
        self._manager.apply_theme(checked)

    def update_dark_mode(self) -> None:
        self._settings.dark_mode = self._dark_toggle.isChecked()
        self._manager.apply_theme(self._settings.dark_mode)

    # ---- Priority mode ----
    def _on_priority_mode(self, mode_name: str) -> None:
        for value, name in self.PRIORITY_MODES.items():
            if mode_name == name:
                self._settings.priority_mode = value
                break

    # ---- Selection clearing ----
    def clear_selection(self) -> None:
        self._priority_list.clearSelection()
        self._exclude_list.clearSelection()

    # ---- Game names ----
    def update_excluded_choices(self) -> None:
        self._exclude_entry.set_items(
            sorted(self._game_names.difference(self._settings.exclude))
        )

    def update_priority_choices(self) -> None:
        self._priority_entry.set_items(
            sorted(self._game_names.difference(self._settings.priority))
        )

    def set_games(self, games: set[Game]) -> None:
        self._game_names.update(game.name for game in games)
        self.update_excluded_choices()
        self.update_priority_choices()

    # ---- Priority list operations ----
    def priority_add(self) -> None:
        game_name = self._priority_entry.get()
        if not game_name:
            return
        self._priority_entry.clear()
        try:
            existing_idx = self._settings.priority.index(game_name)
        except ValueError:
            self._priority_list.addItem(game_name)
            self._priority_list.scrollToBottom()
            self._settings.priority.append(game_name)
            self._settings.alter()
            self.update_priority_choices()
            self._priority_empty.setVisible(False)
        else:
            self._priority_list.setCurrentRow(existing_idx)

    def priority_move(self, amount: int) -> None:
        idx = self._priority_list.currentRow()
        max_idx = self._priority_list.count() - 1
        if idx < 0 or amount == 0:
            return
        if amount > 0 and idx == 0:
            return
        if amount < 0 and idx == max_idx:
            return
        insert_idx = idx - amount
        insert_idx = max(0, min(insert_idx, max_idx))

        item = self._priority_list.takeItem(idx)
        self._priority_list.insertItem(insert_idx, item)
        self._priority_list.setCurrentRow(insert_idx)
        self._settings.priority.pop(idx)
        self._settings.priority.insert(insert_idx, item.text())
        self._settings.alter()

    def priority_delete(self) -> None:
        idx = self._priority_list.currentRow()
        if idx < 0:
            return
        self._priority_list.takeItem(idx)
        del self._settings.priority[idx]
        self._settings.alter()
        self.update_priority_choices()
        self._priority_empty.setVisible(self._priority_list.count() == 0)

    # ---- Exclude list operations ----
    def exclude_add(self) -> None:
        game_name = self._exclude_entry.get()
        if not game_name:
            return
        self._exclude_entry.clear()
        if game_name not in self._settings.exclude:
            self._settings.exclude.add(game_name)
            self._settings.alter()
            self.update_excluded_choices()
            # Insert alphabetically
            items = [self._exclude_list.item(i).text() for i in range(self._exclude_list.count())]
            items.append(game_name)
            items.sort()
            insert_idx = items.index(game_name)
            self._exclude_list.insertItem(insert_idx, game_name)
            self._exclude_list.setCurrentRow(insert_idx)
            self._exclude_empty.setVisible(False)
        else:
            for i in range(self._exclude_list.count()):
                if self._exclude_list.item(i).text() == game_name:
                    self._exclude_list.setCurrentRow(i)
                    break

    def exclude_delete(self) -> None:
        idx = self._exclude_list.currentRow()
        if idx < 0:
            return
        item = self._exclude_list.takeItem(idx)
        if item and item.text() in self._settings.exclude:
            self._settings.exclude.discard(item.text())
            self._settings.alter()
            self.update_excluded_choices()
        self._exclude_empty.setVisible(self._exclude_list.count() == 0)

    # ---- Autostart (full platform support from original) ----
    def _get_self_path(self) -> str:
        return f'"{SELF_PATH.resolve()!s}"'

    def _get_autostart_path(self) -> str:
        flags: list[str] = []
        for lvl_idx, lvl_value in LOGGING_LEVELS.items():
            if lvl_value == self._settings.logging_level:
                if lvl_idx > 0:
                    flags.append(f"-{'v' * lvl_idx}")
                break
        if self._tray_toggle is not None and self._tray_toggle.isChecked():
            flags.append("--tray")
        if not IS_PACKAGED:
            return f"\"{SCRIPTS_PATH / 'pythonw'!s}\" {self._get_self_path()} {' '.join(flags)}"
        return f"{self._get_self_path()} {' '.join(flags)}"

    def _get_linux_autostart_filepath(self) -> Path:
        autostart_folder = Path("~/.config/autostart").expanduser()
        if (config_home := os.environ.get("XDG_CONFIG_HOME")) is not None:
            config_autostart = Path(config_home, "autostart").expanduser()
            if config_autostart.exists():
                autostart_folder = config_autostart
        return autostart_folder / f"{self.AUTOSTART_NAME}.desktop"

    def _get_mac_autostart_filepath(self) -> Path:
        return Path(
            Path.home(),
            f"Library/LaunchAgents/com.devilxd.{self.AUTOSTART_NAME.lower()}.plist"
        )

    def _query_autostart(self) -> bool:
        if sys.platform == "win32":
            with RegistryKey(self.AUTOSTART_KEY, read_only=True) as key:
                try:
                    value_type, value = key.get(self.AUTOSTART_NAME)
                except ValueNotFound:
                    return False
                return value_type is ValueType.REG_SZ and self._get_self_path() in value
        elif sys.platform == "linux":
            autostart_file = self._get_linux_autostart_filepath()
            if not autostart_file.exists():
                return False
            with autostart_file.open('r', encoding="utf8") as file:
                return self._get_self_path() in file.read()
        elif sys.platform == "darwin":
            plist_file = self._get_mac_autostart_filepath()
            if not plist_file.exists():
                return False
            with plist_file.open('r', encoding="utf8") as file:
                return str(SELF_PATH.resolve()) in file.read()
        return False

    def update_autostart(self) -> None:
        enabled = self._autostart_toggle.isChecked()
        if self._tray_toggle is not None:
            self._settings.autostart_tray = self._tray_toggle.isChecked()
        if sys.platform == "win32":
            if enabled:
                with RegistryKey(self.AUTOSTART_KEY) as key:
                    key.set(self.AUTOSTART_NAME, ValueType.REG_SZ, self._get_autostart_path())
            else:
                with RegistryKey(self.AUTOSTART_KEY) as key:
                    key.delete(self.AUTOSTART_NAME, silent=True)
        elif sys.platform == "linux":
            autostart_file = self._get_linux_autostart_filepath()
            if enabled:
                file_contents = dedent(f"""
                    [Desktop Entry]
                    Type=Application
                    Name=Twitch Drops Miner
                    Description=Mine timed drops on Twitch
                    Exec=sh -c '{self._get_autostart_path()}'
                """)
                with autostart_file.open('w', encoding="utf8") as file:
                    file.write(file_contents)
            else:
                autostart_file.unlink(missing_ok=True)
        elif sys.platform == "darwin":
            plist_file = self._get_mac_autostart_filepath()
            if enabled:
                command_parts = shlex.split(self._get_autostart_path())
                plist_data = {
                    "Label": f"com.devilxd.{self.AUTOSTART_NAME.lower()}",
                    "ProgramArguments": command_parts,
                    "RunAtLoad": True,
                }
                plist_file.parent.mkdir(parents=True, exist_ok=True)
                with plist_file.open("wb") as file:
                    plistlib.dump(plist_data, file)
            else:
                plist_file.unlink(missing_ok=True)
