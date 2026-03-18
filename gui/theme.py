from __future__ import annotations

import sys
import ctypes
from dataclasses import dataclass

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QPalette, QColor

if sys.platform == "darwin":
    try:
        import AppKit
    except ImportError:
        AppKit = None  # type: ignore


@dataclass(frozen=True)
class ColorPalette:
    """Immutable set of colours that defines a complete theme."""
    # Surfaces
    background: str        # Window / app background
    surface: str           # Card / elevated surface
    surface_hover: str     # Card hover state
    surface_alt: str       # Alternate surface (sidebar, header)
    # Foreground
    foreground: str        # Primary text
    foreground_muted: str  # Secondary / disabled text
    foreground_subtle: str # Placeholder / hint text
    # Selection
    selection_bg: str      # Selected item background
    selection_fg: str      # Selected item foreground
    # Borders
    border: str            # Default border colour
    border_light: str      # Lighter border (dividers)
    # Accent (Twitch purple)
    accent: str            # Primary accent
    accent_hover: str      # Accent hover state
    accent_light: str      # Light accent (backgrounds, badges)
    # Semantic
    success: str           # Green
    warning: str           # Amber/goldenrod
    error: str             # Red
    info: str              # Blue/cyan
    link: str              # Hyperlink colour
    # Scrollbar
    scrollbar_bg: str
    scrollbar_handle: str
    scrollbar_handle_hover: str
    # Shadow (CSS box-shadow colour)
    shadow: str
    # Background gradient (subtle radial gradient center)
    background_gradient_center: str


DARK_PALETTE = ColorPalette(
    background="#0E0E10",
    surface="#18181B",
    surface_hover="#1F1F23",
    surface_alt="#0E0E10",
    foreground="#EFEFF1",
    foreground_muted="#ADADB8",
    foreground_subtle="#636369",
    selection_bg="#9146FF",
    selection_fg="#FFFFFF",
    border="#2F2F35",
    border_light="#26262C",
    accent="#9146FF",
    accent_hover="#A970FF",
    accent_light="#2C2041",
    success="#00C853",
    warning="#E6A817",
    error="#EB0400",
    info="#1E90FF",
    link="#BF94FF",
    scrollbar_bg="#0E0E10",
    scrollbar_handle="#3A3A3D",
    scrollbar_handle_hover="#53535F",
    shadow="rgba(0, 0, 0, 0.45)",
    background_gradient_center="#131316",
)

LIGHT_PALETTE = ColorPalette(
    background="#F7F7F8",
    surface="#FFFFFF",
    surface_hover="#F0F0F2",
    surface_alt="#EFEFF1",
    foreground="#0E0E10",
    foreground_muted="#53535F",
    foreground_subtle="#ADADB8",
    selection_bg="#9146FF",
    selection_fg="#FFFFFF",
    border="#D2D2D7",
    border_light="#E5E5EA",
    accent="#9146FF",
    accent_hover="#772CE8",
    accent_light="#F0E6FF",
    success="#00875A",
    warning="#B8860B",
    error="#D10000",
    info="#0969DA",
    link="#6441A5",
    scrollbar_bg="#F7F7F8",
    scrollbar_handle="#C8C8D0",
    scrollbar_handle_hover="#A0A0AB",
    shadow="rgba(0, 0, 0, 0.10)",
    background_gradient_center="#FAFAFC",
)


class ThemeManager(QObject):
    """Generates and applies a comprehensive Qt stylesheet from a colour palette."""

    theme_changed = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._dark: bool = False
        self._palette: ColorPalette = LIGHT_PALETTE

    @property
    def is_dark(self) -> bool:
        return self._dark

    @property
    def palette(self) -> ColorPalette:
        return self._palette

    # ------------------------------------------------------------------ #
    #  Public API                                                         #
    # ------------------------------------------------------------------ #

    def apply(self, app: QApplication, dark: bool) -> None:
        """Apply the full theme to the application."""
        self._dark = dark
        self._palette = DARK_PALETTE if dark else LIGHT_PALETTE
        app.setStyleSheet(self._build_stylesheet())
        self._apply_platform_appearance(dark)
        self.theme_changed.emit()

    # ------------------------------------------------------------------ #
    #  Platform appearance (title bar / system theme)                     #
    # ------------------------------------------------------------------ #

    @staticmethod
    def set_title_bar_color(hwnd: int, dark: bool) -> None:
        """Set Windows title bar colour via DWM."""
        if sys.platform != "win32":
            return
        DWMWA_USE_IMMERSIVE_DARK_MODE = 20
        DWMWA_CAPTION_COLOR = 35
        try:
            value = ctypes.c_int(1 if dark else 0)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE,
                ctypes.byref(value), ctypes.sizeof(value),
            )
            color = ctypes.c_int(0x00100E0E if dark else 0x00FFFFFF)  # BGR
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, DWMWA_CAPTION_COLOR,
                ctypes.byref(color), ctypes.sizeof(color),
            )
        except Exception:
            pass

    @staticmethod
    def _apply_platform_appearance(dark: bool) -> None:
        if sys.platform == "darwin" and AppKit is not None:
            app = AppKit.NSApplication.sharedApplication()
            name = (
                AppKit.NSAppearanceNameDarkAqua if dark
                else AppKit.NSAppearanceNameAqua
            )
            app.setAppearance_(AppKit.NSAppearance.appearanceNamed_(name))

    # ------------------------------------------------------------------ #
    #  Stylesheet builder                                                 #
    # ------------------------------------------------------------------ #

    def _build_stylesheet(self) -> str:
        p = self._palette
        return f"""
        /* ===== GLOBAL ===== */
        * {{
            font-family: "Segoe UI", "SF Pro Display", "Helvetica Neue", Arial, sans-serif;
            font-size: 13px;
            outline: none;
        }}
        QMainWindow, QWidget#CentralWidget {{
            background-color: qradialgradient(
                cx: 0.5, cy: 0.3, radius: 0.9,
                fx: 0.5, fy: 0.3,
                stop: 0 {p.background_gradient_center},
                stop: 1 {p.background}
            );
        }}

        /* ===== LABELS ===== */
        QLabel {{
            color: {p.foreground};
            background: transparent;
            padding: 0px;
        }}
        QLabel[class="muted"] {{
            color: {p.foreground_muted};
        }}
        QLabel[class="heading"] {{
            font-size: 15px;
            font-weight: 600;
            color: {p.foreground};
        }}
        QLabel[class="section-title"] {{
            font-size: 12px;
            font-weight: 600;
            color: {p.foreground_muted};
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        QLabel[class="link"] {{
            color: {p.link};
        }}
        QLabel[class="link"]:hover {{
            text-decoration: underline;
        }}
        QLabel[class="monospace"] {{
            font-family: "Cascadia Code", "Consolas", "Courier New", monospace;
            font-size: 12px;
        }}
        QLabel[class="success"] {{ color: {p.success}; }}
        QLabel[class="warning"] {{ color: {p.warning}; }}
        QLabel[class="error"]   {{ color: {p.error}; }}

        /* ===== CARDS (QFrame with class) ===== */
        QFrame[class="card"] {{
            background-color: {p.surface};
            border: 1px solid {p.border_light};
            border-radius: 8px;
        }}
        QFrame[class="card-flat"] {{
            background-color: {p.surface};
            border: none;
            border-radius: 8px;
        }}

        /* ===== BUTTONS ===== */
        QPushButton {{
            background-color: {p.surface};
            color: {p.foreground};
            border: 1px solid {p.border};
            border-radius: 6px;
            padding: 6px 16px;
            font-weight: 500;
            min-height: 20px;
        }}
        QPushButton:hover {{
            background-color: {p.surface_hover};
            border-color: {p.foreground_muted};
        }}
        QPushButton:pressed {{
            background-color: {p.border};
        }}
        QPushButton:disabled {{
            color: {p.foreground_subtle};
            border-color: {p.border_light};
        }}
        QPushButton[class="accent"] {{
            background-color: {p.accent};
            color: #FFFFFF;
            border: none;
        }}
        QPushButton[class="accent"]:hover {{
            background-color: {p.accent_hover};
        }}
        QPushButton[class="accent"]:pressed {{
            background-color: {p.accent};
            opacity: 0.8;
        }}
        QPushButton[class="accent"]:disabled {{
            background-color: {p.foreground_subtle};
            color: {p.foreground_muted};
        }}
        QPushButton[class="icon-btn"] {{
            background: transparent;
            border: none;
            border-radius: 6px;
            padding: 4px 8px;
            font-size: 16px;
        }}
        QPushButton[class="icon-btn"]:hover {{
            background-color: {p.surface_hover};
        }}

        /* ===== LINE EDIT ===== */
        QLineEdit {{
            background-color: {p.surface};
            color: {p.foreground};
            border: 1px solid {p.border};
            border-radius: 6px;
            padding: 6px 10px;
            selection-background-color: {p.selection_bg};
            selection-color: {p.selection_fg};
        }}
        QLineEdit:focus {{
            border-color: {p.accent};
        }}
        QLineEdit:disabled {{
            color: {p.foreground_subtle};
            background-color: {p.surface_hover};
        }}
        QLineEdit[class="placeholder-active"] {{
            color: {p.foreground_subtle};
        }}
        QLineEdit[error="true"] {{
            border-color: {p.error};
        }}

        /* ===== COMBO BOX ===== */
        QComboBox {{
            background-color: {p.surface};
            color: {p.foreground};
            border: 1px solid {p.border};
            border-radius: 6px;
            padding: 6px 10px;
            padding-right: 28px;
            min-height: 20px;
        }}
        QComboBox:hover {{
            border-color: {p.foreground_muted};
        }}
        QComboBox:focus {{
            border-color: {p.accent};
        }}
        QComboBox::drop-down {{
            subcontrol-origin: padding;
            subcontrol-position: top right;
            width: 28px;
            border: none;
        }}
        QComboBox::down-arrow {{
            image: none;
            border-left: 4px solid transparent;
            border-right: 4px solid transparent;
            border-top: 5px solid {p.foreground_muted};
            margin-right: 8px;
        }}
        QComboBox QAbstractItemView {{
            background-color: {p.surface};
            color: {p.foreground};
            border: 1px solid {p.border};
            border-radius: 6px;
            selection-background-color: {p.accent_light};
            selection-color: {p.foreground};
            padding: 4px;
            outline: none;
        }}
        QComboBox QAbstractItemView::item {{
            padding: 6px 10px;
            border-radius: 4px;
            min-height: 22px;
        }}
        QComboBox QAbstractItemView::item:hover {{
            background-color: {p.surface_hover};
        }}
        QComboBox QAbstractItemView::item:selected {{
            background-color: {p.accent_light};
        }}

        /* ===== TEXT EDIT (console) ===== */
        QTextEdit, QPlainTextEdit {{
            background-color: {p.surface};
            color: {p.foreground};
            border: 1px solid {p.border_light};
            border-radius: 8px;
            padding: 8px;
            selection-background-color: {p.selection_bg};
            selection-color: {p.selection_fg};
            font-family: "Cascadia Code", "Consolas", "Courier New", monospace;
            font-size: 12px;
        }}

        /* ===== TREE VIEW (channel list) ===== */
        QTreeView {{
            background-color: {p.surface};
            color: {p.foreground};
            border: 1px solid {p.border_light};
            border-radius: 8px;
            alternate-background-color: {p.surface_hover};
            outline: none;
        }}
        QTreeView::item {{
            padding: 4px 8px;
            min-height: 28px;
            border: none;
        }}
        QTreeView::item:hover {{
            background-color: {p.surface_hover};
        }}
        QTreeView::item:selected {{
            background-color: {p.accent_light};
            color: {p.foreground};
        }}
        QHeaderView::section {{
            background-color: {p.surface_alt};
            color: {p.foreground_muted};
            border: none;
            border-bottom: 1px solid {p.border_light};
            padding: 6px 8px;
            font-weight: 600;
            font-size: 11px;
            text-transform: uppercase;
        }}

        /* ===== LIST WIDGET ===== */
        QListWidget {{
            background-color: {p.surface};
            color: {p.foreground};
            border: 1px solid {p.border_light};
            border-radius: 8px;
            padding: 4px;
            outline: none;
        }}
        QListWidget::item {{
            padding: 5px 8px;
            border-radius: 4px;
        }}
        QListWidget::item:hover {{
            background-color: {p.surface_hover};
        }}
        QListWidget::item:selected {{
            background-color: {p.accent_light};
            color: {p.foreground};
        }}

        /* ===== PROGRESS BAR ===== */
        QProgressBar {{
            background-color: {p.border_light};
            border: none;
            border-radius: 4px;
            height: 8px;
            text-align: center;
            color: transparent; /* hide text inside bar */
        }}
        QProgressBar::chunk {{
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 {p.accent}, stop:1 {p.accent_hover});
            border-radius: 4px;
        }}

        /* ===== SCROLL BARS ===== */
        QScrollBar:vertical {{
            background: {p.scrollbar_bg};
            width: 10px;
            margin: 0;
            border: none;
            border-radius: 5px;
        }}
        QScrollBar::handle:vertical {{
            background: {p.scrollbar_handle};
            min-height: 30px;
            border-radius: 5px;
            margin: 2px;
        }}
        QScrollBar::handle:vertical:hover {{
            background: {p.scrollbar_handle_hover};
        }}
        QScrollBar::add-line:vertical,
        QScrollBar::sub-line:vertical,
        QScrollBar::add-page:vertical,
        QScrollBar::sub-page:vertical {{
            height: 0; background: none; border: none;
        }}
        QScrollBar:horizontal {{
            background: {p.scrollbar_bg};
            height: 10px;
            margin: 0;
            border: none;
            border-radius: 5px;
        }}
        QScrollBar::handle:horizontal {{
            background: {p.scrollbar_handle};
            min-width: 30px;
            border-radius: 5px;
            margin: 2px;
        }}
        QScrollBar::handle:horizontal:hover {{
            background: {p.scrollbar_handle_hover};
        }}
        QScrollBar::add-line:horizontal,
        QScrollBar::sub-line:horizontal,
        QScrollBar::add-page:horizontal,
        QScrollBar::sub-page:horizontal {{
            width: 0; background: none; border: none;
        }}

        /* ===== SCROLL AREA ===== */
        QScrollArea {{
            background: transparent;
            border: none;
        }}
        QScrollArea > QWidget > QWidget {{
            background: transparent;
        }}

        /* ===== GROUP BOX ===== */
        QGroupBox {{
            background-color: {p.surface};
            border: 1px solid {p.border_light};
            border-radius: 8px;
            margin-top: 16px;
            padding: 16px 12px 12px 12px;
            font-weight: 600;
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            subcontrol-position: top left;
            padding: 2px 8px;
            color: {p.foreground_muted};
            font-size: 12px;
        }}

        /* ===== SEPARATOR ===== */
        QFrame[class="separator"] {{
            background-color: {p.border_light};
            max-height: 1px;
            min-height: 1px;
        }}

        /* ===== TOOLTIPS ===== */
        QToolTip {{
            background-color: {p.surface};
            color: {p.foreground};
            border: 1px solid {p.border};
            border-radius: 4px;
            padding: 6px 10px;
            font-size: 12px;
        }}

        /* ===== MENU (tray context menu) ===== */
        QMenu {{
            background-color: {p.surface};
            color: {p.foreground};
            border: 1px solid {p.border};
            border-radius: 8px;
            padding: 4px;
        }}
        QMenu::item {{
            padding: 6px 24px;
            border-radius: 4px;
        }}
        QMenu::item:selected {{
            background-color: {p.accent_light};
        }}
        QMenu::separator {{
            height: 1px;
            background-color: {p.border_light};
            margin: 4px 8px;
        }}

        /* ===== STACKED WIDGET ===== */
        QStackedWidget {{
            background: transparent;
        }}
        """
