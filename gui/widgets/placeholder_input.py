from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFocusEvent
from PySide6.QtWidgets import QLineEdit, QComboBox


class PlaceholderLineEdit(QLineEdit):
    """
    QLineEdit with custom placeholder behaviour matching the original tkinter PlaceholderEntry.

    Features:
    - Placeholder text shown in muted color when empty and unfocused
    - Optional prefill text inserted when focused
    - Compatible with password masking (echoMode)
    """

    def __init__(
        self,
        parent=None,
        *,
        placeholder: str = "",
        prefill: str = "",
        password: bool = False,
    ):
        super().__init__(parent)
        self._ph_text = placeholder
        self._prefill = prefill
        self._password = password
        self._normal_echo = QLineEdit.EchoMode.Password if password else QLineEdit.EchoMode.Normal
        self._ph_active = False

        self.setPlaceholderText(placeholder)
        if password:
            self.setEchoMode(self._normal_echo)

    def get(self) -> str:
        """Return text, or empty string if only placeholder is showing."""
        return self.text().strip()

    def clear(self) -> None:
        """Clear the field."""
        super().clear()

    def replace(self, content: str) -> None:
        """Replace the entire content."""
        self.setText(content)

    def focusInEvent(self, event: QFocusEvent) -> None:
        super().focusInEvent(event)
        if not self.text() and self._prefill:
            self.setText(self._prefill)

    def focusOutEvent(self, event: QFocusEvent) -> None:
        if self.text() == self._prefill:
            self.clear()
        super().focusOutEvent(event)


class PlaceholderComboBox(QComboBox):
    """
    QComboBox with placeholder-like behaviour.

    When editable, shows placeholder text when empty.
    Provides a `get()` method to retrieve the current text.
    """

    def __init__(self, parent=None, *, placeholder: str = "", width: int = 200):
        super().__init__(parent)
        self.setEditable(True)
        self.setMinimumWidth(width)
        self.lineEdit().setPlaceholderText(placeholder)
        self.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)

    def get(self) -> str:
        return self.currentText().strip()

    def clear(self) -> None:
        self.setCurrentText("")
        self.lineEdit().clear()

    def set_items(self, items: list[str]) -> None:
        current = self.currentText()
        self.blockSignals(True)
        super().clear()
        self.addItems(items)
        self.setCurrentText(current)
        self.blockSignals(False)
