"""Colours, fonts and the Qt style sheet of the desktop app (one light theme, so the app
looks the same in macOS dark mode and on Windows)."""
import sys

from PySide6.QtGui import QColor, QFont, QPalette

NAVY = "#14213d"
NAVY_2 = "#1f3157"
PAGE = "#eef1f5"
PANEL = "#ffffff"
BORDER = "#dde2ea"
INK = "#111827"
INK_2 = "#4b5563"
MUTED = "#9aa3b2"
ACCENT = "#2563eb"
ACCENT_DARK = "#1d4ed8"
ACCENT_SOFT = "#e8f0fe"
OK = "#15803d"
OK_SOFT = "#e7f6ec"
WARN = "#b45309"
WARN_SOFT = "#fff3dd"
ERR = "#c62828"
ERR_SOFT = "#fdecec"
ADDER = "#2a78d6"
MULT = "#eb6834"
SUB = "#1baf7a"
FU_COLOUR = {"adder": ADDER, "multiplier": MULT, "subtractor": SUB}

MONO = "Menlo" if sys.platform == "darwin" else "Consolas"
BASE_PX = 13


def palette():
    p = QPalette()
    roles = {
        QPalette.ColorRole.Window: PAGE, QPalette.ColorRole.WindowText: INK,
        QPalette.ColorRole.Base: PANEL, QPalette.ColorRole.AlternateBase: "#f6f8fb",
        QPalette.ColorRole.Text: INK, QPalette.ColorRole.Button: PANEL,
        QPalette.ColorRole.ButtonText: INK, QPalette.ColorRole.ToolTipBase: "#ffffff",
        QPalette.ColorRole.ToolTipText: INK, QPalette.ColorRole.Highlight: ACCENT,
        QPalette.ColorRole.HighlightedText: "#ffffff", QPalette.ColorRole.PlaceholderText: MUTED,
        QPalette.ColorRole.BrightText: "#ffffff", QPalette.ColorRole.Link: ACCENT,
    }
    for role, colour in roles.items():
        p.setColor(role, QColor(colour))
    for role in (QPalette.ColorRole.Text, QPalette.ColorRole.WindowText, QPalette.ColorRole.ButtonText):
        p.setColor(QPalette.ColorGroup.Disabled, role, QColor(MUTED))
    return p


def base_font():
    f = QFont()
    f.setPixelSize(BASE_PX)
    return f


STYLESHEET = f"""
* {{ font-size: {BASE_PX}px; color: {INK}; }}
QMainWindow, QWidget#Root, QWidget#WinRoot {{ background: {PAGE}; }}
QToolTip {{ background: #ffffff; color: {INK}; border: 1px solid {BORDER}; padding: 6px 8px; border-radius: 6px; }}

/* header / footer */
QFrame#Header {{ background: {NAVY}; }}
QFrame#Header QLabel {{ color: #ffffff; }}
QLabel#AppTitle {{ font-size: 19px; font-weight: 700; color: #ffffff; }}
QLabel#AppSub {{ font-size: 12px; color: #b9c6e4; }}
QFrame#Footer {{ background: {NAVY}; }}
QLabel#FooterText {{ color: #dfe6f5; font-size: 12px; }}
QPushButton#HeaderBtn {{ background: {NAVY_2}; color: #ffffff; border: 1px solid #34497a; border-radius: 8px;
    padding: 7px 14px; font-weight: 600; }}
QPushButton#HeaderBtn:hover {{ background: #2a4170; }}
QPushButton#ReadMe {{ background: #16a34a; color: #ffffff; border: 0; border-radius: 8px; padding: 7px 14px; font-weight: 700; }}
QPushButton#ReadMe:hover {{ background: #15803d; }}

/* "next step" banner */
QFrame#NextBar {{ background: {ACCENT_SOFT}; border: 1px solid #c4d7fb; border-radius: 10px; }}
QFrame#NextBar[done="true"] {{ background: {OK_SOFT}; border: 1px solid #b7e2c4; }}
QLabel#NextText {{ font-size: 14px; color: {INK}; }}

/* panels */
QFrame#Panel {{ background: {PANEL}; border: 1px solid {BORDER}; border-radius: 14px; }}
QLabel#PanelTitle {{ font-size: 15px; font-weight: 800; color: {NAVY}; letter-spacing: 1px; }}
QLabel#PanelHint {{ font-size: 12px; color: {INK_2}; }}
QLabel#GroupLabel {{ font-size: 11px; font-weight: 700; color: {MUTED}; letter-spacing: 1px; padding-top: 6px; }}
QScrollArea#PanelScroll, QScrollArea#PanelScroll > QWidget > QWidget {{ background: transparent; border: 0; }}

/* step cards (input panel) */
QFrame#StepCard {{ background: #ffffff; border: 1px solid {BORDER}; border-radius: 12px; }}
QFrame#StepCard[state="locked"] {{ background: #f5f6f8; border: 1px dashed #d3d8e0; }}
QFrame#StepCard[state="active"] {{ background: #ffffff; border: 2px solid {ACCENT}; }}
QFrame#StepCard[state="done"] {{ background: #ffffff; border: 1px solid #b7e2c4; }}
QLabel#StepNum {{ min-width: 26px; max-width: 26px; min-height: 26px; max-height: 26px; border-radius: 13px;
    background: #d9dee6; color: #ffffff; font-weight: 800; qproperty-alignment: AlignCenter; }}
QLabel#StepNum[state="active"] {{ background: {ACCENT}; }}
QLabel#StepNum[state="done"] {{ background: {OK}; }}
QLabel#StepTitle {{ font-size: 14px; font-weight: 700; }}
QLabel#StepTitle[state="locked"] {{ color: {MUTED}; }}
QLabel#StepDesc {{ font-size: 12px; color: {INK_2}; }}
QLabel#StepDesc[state="locked"] {{ color: #b3bac6; }}
QLabel#StepResult {{ font-size: 12px; color: {OK}; font-weight: 600; }}
QLabel#StepLock {{ font-size: 12px; color: {MUTED}; }}
QLabel#FieldLabel {{ font-size: 12px; color: {INK_2}; }}

/* buttons */
QPushButton#Primary {{ background: {ACCENT}; color: #ffffff; border: 0; border-radius: 8px; padding: 8px 16px; font-weight: 700; }}
QPushButton#Primary:hover {{ background: {ACCENT_DARK}; }}
QPushButton#Primary:disabled {{ background: #cfd6e1; color: #f4f6f9; }}
QPushButton#Secondary {{ background: #ffffff; color: {INK}; border: 1px solid #cbd3df; border-radius: 8px; padding: 7px 14px; font-weight: 600; }}
QPushButton#Secondary:hover {{ background: {ACCENT_SOFT}; border-color: {ACCENT}; }}
QPushButton#Secondary:disabled {{ color: {MUTED}; background: #f5f6f8; border-color: #e1e5eb; }}
QPushButton#Chip {{ background: #f3f5f9; color: {INK}; border: 1px solid #d9dfe8; border-radius: 9px; padding: 4px 11px; font-size: 12px; font-weight: 600; }}
QPushButton#Chip:hover {{ background: {ACCENT_SOFT}; border-color: {ACCENT}; }}
QPushButton#Chip:checked {{ background: {ACCENT}; color: #ffffff; border-color: {ACCENT}; }}
QPushButton#Chip:disabled {{ color: {MUTED}; background: #eef0f4; border-color: #e1e5eb; }}
QPushButton#Chip:checked:disabled {{ background: #c9d2e0; color: #f4f6f9; border-color: #c9d2e0; }}
QPushButton#LinkBtn {{ background: transparent; border: 0; color: {ACCENT}; font-weight: 600; padding: 2px 0; text-align: left; }}
QPushButton#LinkBtn:disabled {{ color: {MUTED}; }}

/* status panel */
QFrame#StatusTile {{ border-radius: 12px; border: 1px solid #e3e7ee; background: #f4f6f9; }}
QFrame#StatusTile[state="next"] {{ background: {ACCENT_SOFT}; border: 2px solid {ACCENT}; }}
QFrame#StatusTile[state="running"] {{ background: {WARN_SOFT}; border: 2px solid #f0b252; }}
QFrame#StatusTile[state="done"] {{ background: {OK_SOFT}; border: 1px solid #9fd6b0; }}
QFrame#StatusTile[state="error"] {{ background: {ERR_SOFT}; border: 2px solid #ef9a9a; }}
QLabel#TileTitle {{ font-size: 13px; font-weight: 700; color: {INK}; }}
QLabel#TileTitle[state="waiting"] {{ color: {MUTED}; }}
QLabel#TileState {{ font-size: 11px; font-weight: 800; letter-spacing: 1px; color: {MUTED}; }}
QLabel#TileState[state="next"] {{ color: {ACCENT}; }}
QLabel#TileState[state="running"] {{ color: {WARN}; }}
QLabel#TileState[state="done"] {{ color: {OK}; }}
QLabel#TileState[state="error"] {{ color: {ERR}; }}
QLabel#TileDetail {{ font-size: 12px; color: {INK_2}; }}

/* output panel */
QPushButton#OutBtn {{ background: #ffffff; color: {INK}; border: 1px solid #cbd3df; border-radius: 9px;
    padding: 6px 12px; min-height: 24px; font-weight: 600; text-align: left; }}
QPushButton#OutBtn:hover {{ background: {ACCENT_SOFT}; border-color: {ACCENT}; color: {ACCENT_DARK}; }}
QPushButton#OutBtn:disabled {{ background: #f4f6f9; color: #aab2bf; border: 1px solid #e4e8ee; }}
QPushButton#OutBtn[fresh="true"] {{ border: 2px solid {ACCENT}; }}

/* log */
QPlainTextEdit#Log {{ background: #ffffff; border: 1px solid {BORDER}; border-radius: 10px; padding: 6px;
    font-family: {MONO}; font-size: 12px; color: {INK_2}; }}

/* inputs */
QSpinBox, QDoubleSpinBox, QComboBox, QLineEdit {{ background: #ffffff; border: 1px solid #cbd3df; border-radius: 6px; padding: 4px 6px; min-height: 20px; }}
QSpinBox:disabled, QDoubleSpinBox:disabled, QComboBox:disabled, QLineEdit:disabled {{ background: #f3f5f8; color: {MUTED}; }}
QCheckBox {{ spacing: 6px; }}
QCheckBox:disabled {{ color: {MUTED}; }}

/* output windows */
QLabel#WinTitle {{ font-size: 20px; font-weight: 800; color: {NAVY}; }}
QLabel#WinExplain {{ font-size: 13px; color: {INK_2}; }}
QFrame#Card {{ background: #ffffff; border: 1px solid {BORDER}; border-radius: 12px; }}
QLabel#CardTitle {{ font-size: 14px; font-weight: 700; }}
QFrame#Kpi {{ background: #ffffff; border: 1px solid {BORDER}; border-radius: 12px; }}
QFrame#Kpi[hero="true"] {{ background: {ACCENT}; border: 1px solid {ACCENT}; }}
QLabel#KpiLabel {{ font-size: 12px; color: {INK_2}; font-weight: 600; }}
QLabel#KpiValue {{ font-size: 24px; font-weight: 800; }}
QLabel#KpiSub {{ font-size: 11px; color: {MUTED}; }}
QFrame#Kpi[hero="true"] QLabel {{ color: #ffffff; }}
QLabel#PhaseBadge {{ background: {ACCENT_SOFT}; color: {ACCENT}; border-radius: 10px; padding: 3px 10px; font-weight: 700; font-size: 12px; }}
QLabel#IterLine {{ font-size: 22px; font-weight: 800; }}
QLabel#Narration {{ font-size: 13px; color: {INK_2}; }}
QLabel#ReplayNote {{ background: #f3f5f9; border-radius: 8px; padding: 7px 9px; font-size: 12px; color: {INK_2}; }}
QFrame#GBest {{ background: #fff7f1; border: 1px solid #f6cdb2; border-radius: 10px; }}

QTableWidget {{ background: #ffffff; border: 1px solid {BORDER}; border-radius: 8px; gridline-color: #e6e9ef;
    selection-background-color: {ACCENT_SOFT}; selection-color: {INK}; }}
QHeaderView::section {{ background: #f3f5f8; color: {INK_2}; border: 0; border-right: 1px solid #e6e9ef;
    border-bottom: 1px solid #e6e9ef; padding: 5px 6px; font-weight: 700; font-size: 12px; }}
QTableCornerButton::section {{ background: #f3f5f8; border: 0; }}
QSlider::groove:horizontal {{ height: 6px; background: #dfe4ec; border-radius: 3px; }}
QSlider::sub-page:horizontal {{ background: {ACCENT}; border-radius: 3px; }}
QSlider::handle:horizontal {{ background: #ffffff; border: 2px solid {ACCENT}; width: 14px; height: 14px; margin: -6px 0; border-radius: 9px; }}
QPushButton#Round {{ background: #ffffff; border: 1px solid #cbd3df; border-radius: 17px; min-width: 34px; max-width: 34px; min-height: 34px; max-height: 34px; font-size: 14px; }}
QPushButton#Round:hover {{ background: {ACCENT_SOFT}; border-color: {ACCENT}; }}
QPushButton#Play {{ background: {ACCENT}; color: #ffffff; border: 0; border-radius: 21px; min-width: 42px; max-width: 42px; min-height: 42px; max-height: 42px; font-size: 16px; }}
QPushButton#Play:hover {{ background: {ACCENT_DARK}; }}
QPushButton#Seg {{ background: #ffffff; border: 1px solid #cbd3df; border-radius: 8px; padding: 6px 14px; font-weight: 600; }}
QPushButton#Seg:checked {{ background: {ACCENT_SOFT}; border: 2px solid {ACCENT}; color: {ACCENT_DARK}; }}
QSplitter::handle {{ background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: #c7ced9; border-radius: 4px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: #a9b3c2; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: #c7ced9; border-radius: 4px; min-width: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
"""
