"""苹果风格 QSS — 与 index.html 视觉稿同源的完整实现。

设计语言(与参考稿一一对应):
    - 侧边栏毛玻璃 rgba(238,238,241,.72), 0.5px 细线
    - 主区 #F5F5F7 / 深色 #1C1C1E
    - 卡片 #FFFFFF, 圆角 14px, 阴影走 QGraphicsDropShadowEffect(QSS 不支持 box-shadow)
    - 主色 #007AFF(iOS Blue) / 深色 #0A84FF
    - 文本层级 #1D1D1F / #6E6E73 / #AEAEB2(深色 #F5F5F7 / #98989D / #6C6C70)
    - 动效 120 / 200 / 320ms
"""

from __future__ import annotations

from PyQt6.QtGui import QColor, QFont, QPalette
from PyQt6.QtWidgets import QApplication

from .tokens import Tokens

_CHECK_B64 = (
    "data:image/svg+xml;base64,"
    "PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAxMiAxMiI+"
    "PHBvbHlnb24gcG9pbnRzPSIzLDYgOSwyIiBzdHJva2U9IndoaXRlIiBzdHJva2Utd2lkdGg9IjIi"
    "IGZpbGw9Im5vbmUiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIgc3Ryb2tlLWxpbmVqb2luPSJyb3VuZCIvPjwvc3ZnPg=="
)


def build_qss(mode: str = "light") -> str:
    """由 token 生成整套 QSS。"""
    t = Tokens.for_mode(mode)

    return f"""
/* ═════════════════ 全局 ═════════════════ */
QWidget {{
    font-family: {t['font']};
    font-size: 14px;
    color: {t['text1']};
}}
QMainWindow, #win {{
    background: {t['win_bg']};
}}

/* ═════════════════ 侧边栏 ═════════════════ */
QFrame#sidebar {{
    background: {t['sidebar']};
    border-right: 1px solid {t['sidebar_line']};
}}
QLabel#navSec {{
    font-size: 11px; font-weight: 600;
    color: {t['text3']};
    letter-spacing: .02em;
    padding: 14px 10px 6px;
    background: transparent;
}}
QFrame#navItem {{
    background: transparent;
    border: none;
    border-radius: 6px;
}}
QFrame#navItem:hover {{ background: {t['hover_fill']}; }}
QFrame#navItem:pressed {{ background: {t['press_fill']}; }}
QFrame#navItem[on="true"] {{ background: {t['accent']}; }}
QLabel#navLbl {{
    font-size: 13.5px; font-weight: 500;
    color: {t['text1']};
    background: transparent;
    border: none;
}}
QLabel#navLbl[on="true"] {{ color: {t['text_inv']}; }}
QLabel#navBadge {{
    font-size: 11px; font-weight: 600;
    color: #FFFFFF;
    background: {t['red']};
    border-radius: 9px;
    padding: 1px 6px;
    min-width: 8px;
    max-height: 16px;
}}
QLabel#navBadge[on="true"] {{ background: rgba(255,255,255,.28); }}
QFrame#brandMark {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #FF3B30, stop:.55 #FF9500, stop:1 #FFCC00);
    border-radius: 7px;
}}
QLabel#brandName {{
    font-size: 13px; font-weight: 600;
    color: {t['text1']}; background: transparent; border: none;
}}
QLabel#brandVer {{
    font-size: 11px; color: {t['text3']};
    font-family: {t['mono']}; background: transparent; border: none;
}}
QFrame#engineCard {{
    background: {t['field']};
    border: 1px solid {t['field_line']};
    border-radius: 10px;
}}
QLabel#engineName {{ font-size: 11.5px; font-weight: 500; color: {t['text1']}; background: transparent; border: none; }}
QLabel#engineVal {{ font-size: 11px; color: {t['text2']}; font-family: {t['mono']}; background: transparent; border: none; }}
QLabel#engineVal.zh {{ font-family: {t['font']}; font-size: 11px; }}
QLabel#engineDot {{ background: {t['text3']}; border-radius: 3px; }}
QLabel#engineDot[st="ok"] {{ background: {t['green']}; }}
QLabel#engineDot[st="warn"] {{ background: {t['orange']}; }}
QLabel#engineDot[st="off"] {{ background: {t['text3']}; }}

/* ═════════════════ 顶栏 ═════════════════ */
QFrame#topbar {{
    background: {t['sidebar']};
    border-bottom: 1px solid {t['sep']};
}}
QLabel#pageTitle {{ font-size: 15px; font-weight: 600; color: {t['text1']}; background: transparent; border: none; }}
QWidget#searchbar {{
    background: {t['field']};
    border: 1px solid transparent;
    border-radius: 10px;
}}
QWidget#searchbar[focus="true"] {{
    background: {t['card']};
    border: 1px solid {t['accent']};
}}
QLineEdit#topSearch {{
    background: transparent; border: none;
    color: {t['text1']}; font-size: 13.5px;
    padding: 0; selection-background-color: {t['accent']};
}}
QLineEdit#topSearch:focus {{ border: none; }}
QPushButton#iconBtn {{
    background: transparent; border: none;
    border-radius: 6px;
    color: {t['text2']};
}}
QPushButton#iconBtn:hover {{ background: {t['hover_fill']}; }}
QPushButton#iconBtn:pressed {{ background: {t['press_fill']}; }}

/* ═════════════════ 页面标题 ═════════════════ */
QLabel#h1 {{
    font-size: 28px; font-weight: 700;
    color: {t['text1']}; background: transparent; border: none;
    letter-spacing: -.02em;
}}
QLabel#sub {{
    font-size: 13.5px; color: {t['text2']}; background: transparent; border: none;
}}

/* ═════════════════ 卡片 ═════════════════ */
QFrame#card {{
    background: {t['card']};
    border-radius: 14px;
}}
QFrame#card.noShadow {{
    background: {t['card']};
    border-radius: 14px;
    border: 1px solid {t['sep_soft']};
}}
QLabel#cardTitle {{ font-size: 16px; font-weight: 600; color: {t['text1']}; background: transparent; border: none; }}
QLabel#cardMeta {{ font-size: 13px; color: {t['text2']}; background: transparent; border: none; }}
QLabel#cardDesc {{ font-size: 13px; color: {t['text2']}; background: transparent; border: none; }}
QLabel#secTitle {{ font-size: 17px; font-weight: 650; color: {t['text1']}; background: transparent; border: none; }}
QLabel#secCount {{ font-size: 12.5px; color: {t['text3']}; background: transparent; border: none; }}
QPushButton#secAct {{
    background: none; border: none; color: {t['accent']};
    font-size: 12.5px; font-weight: 500; padding: 0;
}}
QPushButton#secAct:hover {{ text-decoration: underline; }}

/* ═════════════════ 输入 ═════════════════ */
QLineEdit, QTextEdit {{
    background: {t['card']};
    border: 1px solid {t['field_line']};
    border-radius: 10px;
    padding: 8px 12px;
    color: {t['text1']};
    selection-background-color: {t['accent']};
    selection-color: {t['text_inv']};
}}
QLineEdit:hover, QTextEdit:hover {{ border-color: {t['text3']}; }}
QLineEdit:focus, QTextEdit:focus {{
    border: 2px solid {t['accent']};
    padding: 7px 11px;
}}
QLineEdit::placeholder, QTextEdit::placeholder {{ color: {t['text3']}; }}

/* ═════════════════ 按钮 ═════════════════ */
QPushButton#primaryBtn {{
    background: {t['accent']};
    color: {t['text_inv']};
    border: none; border-radius: 10px;
    padding: 8px 18px; font-size: 13.5px; font-weight: 590;
}}
QPushButton#primaryBtn:hover {{ background: {t['accent_hover']}; }}
QPushButton#primaryBtn:pressed {{ background: {t['accent']}; }}
QPushButton#primaryBtn:disabled {{ background: {t['text3']}; }}
QPushButton#secondaryBtn {{
    background: {t['hover_fill']};
    color: {t['text1']};
    border: none; border-radius: 10px;
    padding: 8px 15px; font-size: 13px; font-weight: 500;
}}
QPushButton#secondaryBtn:hover {{ background: {t['press_fill']}; }}
QPushButton#secondaryBtn:pressed {{ background: {t['press_fill']}; }}
QPushButton#ghostBtn {{
    background: transparent;
    color: {t['accent']};
    border: 1px solid {t['field_line']};
    border-radius: 10px;
    padding: 8px 16px; font-size: 13px; font-weight: 500;
}}
QPushButton#ghostBtn:hover {{ background: {t['accent_soft']}; }}

/* ═════════════════ 分类 Chips ═════════════════ */
QPushButton#chip {{
    background: {t['field']};
    color: {t['text1']};
    border: none; border-radius: 999px;
    padding: 5px 14px; font-size: 12.5px; font-weight: 500;
}}
QPushButton#chip:hover {{ background: {t['hover_fill']}; }}
QPushButton#chip:checked {{
    background: {t['accent']};
    color: {t['text_inv']};
}}

/* ═════════════════ 分段控件 ═════════════════ */
QFrame#segmented {{
    background: {t['field']};
    border-radius: 10px;
    padding: 2px;
}}
QPushButton#segBtn {{
    background: transparent; border: none; border-radius: 7.5px;
    color: {t['text2']};
    font-size: 12.5px; font-weight: 550;
    padding: 4px 14px;
}}
QPushButton#segBtn:hover {{ color: {t['text1']}; }}
QPushButton#segBtn:checked {{
    background: {t['card']};
    color: {t['text1']};
}}

/* ═════════════════ 下拉 / 数字 ═════════════════ */
QComboBox, QSpinBox {{
    background: {t['card']};
    border: 1px solid {t['field_line']};
    border-radius: 8px;
    padding: 4px 10px;
    color: {t['text1']};
    min-height: 20px;
}}
QComboBox:hover, QSpinBox:hover {{ border-color: {t['text3']}; }}
QComboBox:focus, QSpinBox:focus {{ border-color: {t['accent']}; }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox::down-arrow {{
    image: url(data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAxMiA4Ij48cGF0aCBkPSJNMSAxbDUgNSA1LTUiIGZpbGw9Im5vbmUiIHN0cm9rZT0iIztzdHJva2U9IiM2RTZFNzMiIHN0cm9rZS13aWR0aD0iMS44IiBzdHJva2UtbGluZWNhcD0icm91bmQiLz48L3N2Zz4=);
}}
QComboBox QAbstractItemView {{
    background: {t['card']};
    border: 1px solid {t['field_line']};
    border-radius: 8px;
    selection-background-color: {t['accent_soft']};
    selection-color: {t['accent']};
    padding: 4px;
    outline: none;
}}
QSpinBox::up-button, QSpinBox::down-button {{ border: none; background: transparent; width: 16px; }}
QSpinBox::up-arrow, QSpinBox::down-arrow {{ width: 0; height: 0; }}

/* ═════════════════ 复选框 ═════════════════ */
QCheckBox {{ spacing: 8px; color: {t['text1']}; background: transparent; }}
QCheckBox::indicator {{
    width: 18px; height: 18px;
    border-radius: 5px;
    border: 1.5px solid {t['field_line']};
    background: {t['card']};
}}
QCheckBox::indicator:hover {{ border-color: {t['text3']}; }}
QCheckBox::indicator:checked {{
    background: {t['accent']};
    border: 1.5px solid {t['accent']};
    image: url({_CHECK_B64});
}}

/* ═════════════════ 列表 ═════════════════ */
QListWidget {{
    background: transparent; border: none; outline: none;
}}
QListWidget::item {{
    background: {t['card']};
    border: 1px solid {t['sep_soft']};
    border-radius: 10px;
    padding: 6px;
    margin: 3px 0;
    color: {t['text1']};
}}
QListWidget::item:hover {{ background: {t['card_hover']}; }}
QListWidget::item:selected {{
    background: {t['accent_soft']};
    border: 1px solid {t['accent']};
    color: {t['text1']};
}}

/* ═════════════════ 表格 ═════════════════ */
QTableWidget {{
    background: {t['card']};
    border: 1px solid {t['sep_soft']};
    border-radius: 12px;
    gridline-color: {t['grouped']};
    selection-background-color: {t['accent_soft']};
    selection-color: {t['text1']};
}}
QHeaderView::section {{
    background: {t['grouped']};
    border: none;
    padding: 8px;
    color: {t['text2']};
    font-weight: 600; font-size: 12px;
}}

/* ═════════════════ 进度条 ═════════════════ */
QProgressBar {{
    background: {t['field']};
    border: none; border-radius: 4px;
    max-height: 6px;
    text-align: center;
}}
QProgressBar::chunk {{ background: {t['accent']}; border-radius: 4px; }}
QProgressBar[state="ok"]::chunk {{ background: {t['green']}; }}
QProgressBar[state="err"]::chunk {{ background: {t['red']}; }}
QProgressBar[state="wait"]::chunk {{ background: {t['text3']}; }}

/* ═════════════════ 任务标签 ═════════════════ */
QLabel#tag {{
    font-size: 10.5px; font-weight: 600;
    padding: 1.5px 7px; border-radius: 999px;
    background: {t['field']}; color: {t['text2']};
}}
QLabel#tag[st="run"] {{ background: {t['accent_soft']}; color: {t['accent']}; }}
QLabel#tag[st="ok"] {{ background: rgba(52,199,89,.14); color: {t['green']}; }}
QLabel#tag[st="err"] {{ background: rgba(255,59,48,.13); color: {t['red']}; }}
QLabel#tag[st="wait"] {{ background: {t['field']}; color: {t['text2']}; }}

/* ═════════════════ 拖放区 ═════════════════ */
QFrame#drop {{
    border: 1.5px dashed {t['field_line']};
    border-radius: 20px;
    background: {t['grouped']};
}}
QFrame#drop[hot="true"] {{
    border-color: {t['accent']};
    background: {t['accent_soft']};
}}
QLabel#dropT {{ font-size: 15px; font-weight: 600; color: {t['text1']}; background: transparent; border: none; }}
QLabel#dropS {{ font-size: 12.5px; color: {t['text2']}; background: transparent; border: none; }}
QFrame#dropIcon {{
    background: {t['card']};
    border-radius: 14px;
}}

/* ═════════════════ 任务行 / 设置行 ═════════════════ */
QFrame#taskCard {{
    background: {t['card']};
    border-radius: 10px;
    border: 1px solid transparent;
}}
QFrame#taskCard[st="err"] {{ border: 1px solid rgba(255,59,48,.35); }}
QLabel#tTitle {{ font-size: 13.5px; font-weight: 600; color: {t['text1']}; background: transparent; border: none; }}
QLabel#tSub {{ font-size: 11.5px; color: {t['text2']}; background: transparent; border: none; }}
QLabel#pct {{ font-size: 12px; font-weight: 600; color: {t['text2']}; background: transparent; border: none; }}

QLabel#groupT {{ font-size: 12px; font-weight: 600; color: {t['text2']}; background: transparent; border: none; padding: 0 8px 7px; }}
QFrame#groupBox {{
    background: {t['grouped']};
    border-radius: 14px;
    border: 1px solid {t['sep_soft']};
}}
QLabel#sLabel {{ font-size: 13.5px; color: {t['text1']}; background: transparent; border: none; }}
QLabel#sVal {{ font-size: 13px; color: {t['text2']}; font-family: {t['mono']}; background: transparent; border: none; }}
QLabel#sVal.zh {{ font-family: {t['font']}; font-size: 13px; }}

/* 开关 */
QFrame#tg {{ background: {t['field_line']}; border-radius: 999px; }}
QFrame#tg[on="true"] {{ background: {t['green']}; }}
QLabel#tgKnob {{ background: #FFFFFF; border-radius: 9px; }}

/* picker */
QFrame#picker {{ background: {t['field']}; border-radius: 6px; padding: 2px; }}
QPushButton#pkBtn {{
    background: transparent; border: none; border-radius: 5px;
    color: {t['text2']}; font-size: 12px; font-weight: 550;
    padding: 3px 11px;
}}
QPushButton#pkBtn:hover {{ color: {t['text1']}; }}
QPushButton#pkBtn:checked {{ background: {t['card']}; color: {t['text1']}; }}

/* ═════════════════ 空状态 ═════════════════ */
QLabel#emptyT {{ font-size: 15px; font-weight: 600; color: {t['text1']}; background: transparent; border: none; }}
QLabel#emptyS {{ font-size: 13px; color: {t['text2']}; background: transparent; border: none; }}

/* ═════════════════ 滚动条 ═════════════════ */
QScrollBar:vertical {{
    background: transparent; width: 9px; margin: 2px;
}}
QScrollBar::handle:vertical {{
    background: {t['field_line']};
    border-radius: 4px; min-height: 30px;
    margin: 0 2px;
}}
QScrollBar::handle:vertical:hover {{ background: {t['text3']}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{
    background: transparent; height: 9px; margin: 2px;
}}
QScrollBar::handle:horizontal {{
    background: {t['field_line']};
    border-radius: 4px; min-width: 30px;
    margin: 2px 0;
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

/* ═════════════════ 弹层 / 菜单 / 提示 ═════════════════ */
QMenu {{
    background: {t['card']};
    border: 1px solid {t['field_line']};
    border-radius: 10px;
    padding: 6px;
    color: {t['text1']};
}}
QMenu::item {{ padding: 6px 22px; border-radius: 6px; background: transparent; }}
QMenu::item:selected {{ background: {t['hover_fill']}; }}
QMenu::separator {{ height: 1px; background: {t['sep_soft']}; margin: 5px 8px; }}
QStatusBar {{ background: transparent; color: {t['text2']}; font-size: 12px; }}
QToolTip {{
    background: {t['text1']};
    color: {t['text_inv']};
    border: none; border-radius: 6px;
    padding: 6px 10px;
    font-size: 12px;
}}
QMessageBox {{ background: {t['win_bg']}; }}
QMessageBox QLabel {{ color: {t['text1']}; }}
QScrollArea {{ background: transparent; border: none; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QStackedWidget, QWidget#screen {{
    background: {t['content']};
}}
"""


def apply(app: QApplication, mode: str = "light") -> None:
    """一次性注入 QSS + QPalette。"""
    app.setStyleSheet(build_qss(mode))
    t = Tokens.for_mode(mode)

    pal = QPalette()
    pal.setColor(QPalette.ColorRole.Window, QColor(t["win_bg"]))
    pal.setColor(QPalette.ColorRole.Base, QColor(t["card"]))
    pal.setColor(QPalette.ColorRole.AlternateBase, QColor(t["grouped"]))
    pal.setColor(QPalette.ColorRole.Text, QColor(t["text1"]))
    pal.setColor(QPalette.ColorRole.WindowText, QColor(t["text1"]))
    pal.setColor(QPalette.ColorRole.ButtonText, QColor(t["text1"]))
    pal.setColor(QPalette.ColorRole.Button, QColor(t["card"]))
    pal.setColor(QPalette.ColorRole.Highlight, QColor(t["accent"]))
    pal.setColor(QPalette.ColorRole.HighlightedText, QColor(t["text_inv"]))
    pal.setColor(QPalette.ColorRole.PlaceholderText, QColor(t["text3"]))
    pal.setColor(QPalette.ColorRole.Link, QColor(t["accent"]))
    pal.setColor(QPalette.ColorRole.ToolTipBase, QColor(t["text1"]))
    pal.setColor(QPalette.ColorRole.ToolTipText, QColor(t["text_inv"]))
    app.setPalette(pal)
    # 字体
    f = QFont("Segoe UI Variable Display", 10)
    f.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
    app.setFont(f)


# 兼容旧引用(程序里其他地方)
class Colors:
    BG = "#F5F5F7"
    CARD = "#FFFFFF"
    BORDER = "#E5E5E7"
    BORDER_HOVER = "#D2D2D7"
    PRIMARY = "#007AFF"
    PRIMARY_HOVER = "#006FE6"
    TEXT_PRIMARY = "#1D1D1F"
    TEXT_SECONDARY = "#6E6E73"
    TEXT_TERTIARY = "#AEAEB2"
    SUCCESS = "#34C759"
    WARNING = "#FF9500"
    DANGER = "#FF3B30"


class Fonts:
    HUGE = 32
    LARGE = 24
    TITLE = 22
    BODY = 14
    SMALL = 12
    TINY = 11
