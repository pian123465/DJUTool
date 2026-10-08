"""PyQt6 主窗口 — 苹果风重写版(与 index.html 视觉稿同源)。

布局(参考稿一一对应):
    ┌─ Sidebar(208px 毛玻璃) ─┬─ Main ──────────────────────────┐
    │ ● ● ●                   │ 页面标题        [搜索] [🌙] [⋯]  │
    │ ▣ 短剧下载器    0.8.0    │ ──────────────────────────────  │
    │ 浏览                     │  发现短剧 / 链接解析 / 任务队列   │
    │   ⌕ 搜索                 │  / 已完成 / 设置                 │
    │   ⛓ 链接解析             │                                  │
    │ 下载                     │                                  │
    │   ⇣ 任务队列   (badge)   │                                  │
    │   ✓ 已完成               │                                  │
    │ 系统                     │                                  │
    │   ⚙ 设置                 │                                  │
    │ ─────────────────────    │                                  │
    │ aria2c  ● 1.37.0        │                                  │
    └──────────────────────────┴──────────────────────────────────┘
"""
from __future__ import annotations

import asyncio
import importlib.util
import json
import shutil
from pathlib import Path

from loguru import logger
from PyQt6.QtCore import (
    QEasingCurve, QPointF, QPropertyAnimation, QRectF, QSettings, QSize, Qt,
    QThread, QTimer, pyqtSignal,
)
from PyQt6.QtGui import (
    QAction, QColor, QDesktopServices, QFont, QLinearGradient, QPainter,
    QPainterPath, QPen,
)
from PyQt6.QtWidgets import (
    QApplication, QButtonGroup, QFileDialog, QFrame, QGraphicsDropShadowEffect,
    QGraphicsOpacityEffect, QGridLayout, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QMainWindow, QMenu, QMessageBox, QProgressBar,
    QPushButton, QScrollArea, QSpinBox, QStackedWidget, QTextEdit,
    QVBoxLayout, QWidget,
)

from .apple_style import apply as apply_theme
from .core.aria2_client import Aria2Client
from .core.base import Drama, Episode
from .core.downloader import DownloadEngine
from .core.orchestrator import SearchOrchestrator
from .core.share_resolver import ShareResolver
from .core.task_store import Task, TaskStore
from .icons import icon
from .platforms._template import HemaPlatform, HongguoPlatform

try:
    from .plugins import signatures  # noqa: F401
except ImportError:
    logger.warning("未加载用户签名插件")

SETTINGS = QSettings("Shortdrama", "Shortdrama")


def _repolish(w: QWidget) -> None:
    w.style().unpolish(w)
    w.style().polish(w)


# ====================================================================
#  工作线程
# ====================================================================
class SearchWorker(QThread):
    result = pyqtSignal(object)
    finished_ok = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, orchestrator: SearchOrchestrator, keyword: str):
        super().__init__()
        self.orchestrator = orchestrator
        self.keyword = keyword

    def run(self):
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            async def _collect():
                buf = []
                async for d in self.orchestrator.search_all(self.keyword):
                    buf.append(d)
                return buf

            results = loop.run_until_complete(_collect())
            for r in results:
                self.result.emit(r)
            self.finished_ok.emit()
        except Exception as e:  # noqa: BLE001
            self.error.emit(str(e))


class DownloadWorker(QThread):
    progress = pyqtSignal(int, int, str, int)
    done = pyqtSignal(int, str)
    failed = pyqtSignal(int, str)

    def __init__(self, engine, episode, url, save_dir, store, task_id):
        super().__init__()
        self.engine = engine
        self.episode = episode
        self.url = url
        self.save_dir = save_dir
        self.store = store
        self.task_id = task_id

    def run(self):
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            def on_prog(d, t, s):
                self.progress.emit(d, t, s, self.task_id)

            result = loop.run_until_complete(
                self.engine.download(self.episode, self.url, on_prog)
            )
            if result.success:
                size = result.path.stat().st_size if result.path else 0
                self.store.mark_done(self.task_id, size)
                self.done.emit(self.task_id, str(result.path))
            else:
                self.store.mark_failed(self.task_id, result.error)
                self.failed.emit(self.task_id, result.error)
        except Exception as e:  # noqa: BLE001
            self.store.mark_failed(self.task_id, str(e))
            self.failed.emit(self.task_id, str(e))


# ====================================================================
#  基础组件
# ====================================================================
def _shadow(blur: float = 18, dy: float = 6, alpha: int = 64) -> QGraphicsDropShadowEffect:
    eff = QGraphicsDropShadowEffect()
    eff.setBlurRadius(blur)
    eff.setOffset(0, dy)
    eff.setColor(QColor(0, 0, 0, alpha))
    return eff


def make_card(radius: int = 14) -> QFrame:
    f = QFrame()
    f.setObjectName("card")
    f.setFrameShape(QFrame.Shape.NoFrame)
    f.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    return f


def make_h1(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setObjectName("h1")
    return lbl


def make_sub(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setObjectName("sub")
    lbl.setWordWrap(True)
    return lbl


def make_sec_title(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setObjectName("secTitle")
    return lbl


def make_sec_count(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setObjectName("secCount")
    return lbl


def make_sec_act(text: str) -> QPushButton:
    btn = QPushButton(text)
    btn.setObjectName("secAct")
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    return btn


def make_primary(text: str) -> QPushButton:
    btn = QPushButton(text)
    btn.setObjectName("primaryBtn")
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    return btn


def make_secondary(text: str) -> QPushButton:
    btn = QPushButton(text)
    btn.setObjectName("secondaryBtn")
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    return btn


def make_tag(text: str, st: str = "") -> QLabel:
    lbl = QLabel(text)
    lbl.setObjectName("tag")
    if st:
        lbl.setProperty("st", st)
        _repolish(lbl)
    return lbl


# ------------------------------------------------------------------
#  侧边栏导航项(图标 + 文字 + 可选角标)
# ------------------------------------------------------------------
class NavItem(QFrame):
    clicked = pyqtSignal()

    def __init__(self, icon_name: str, text: str, badge: int = 0, parent=None):
        super().__init__(parent)
        self.setObjectName("navItem")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(34)
        self._icon_name = icon_name
        self._on = False
        self._badge_n = badge

        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 0, 8, 0)
        lay.setSpacing(10)
        self.icon_lbl = QLabel()
        self.icon_lbl.setFixedSize(17, 17)
        lay.addWidget(self.icon_lbl)
        self.lbl = QLabel(text)
        self.lbl.setObjectName("navLbl")
        lay.addWidget(self.lbl)
        lay.addStretch(1)
        self.badge = QLabel()
        self.badge.setObjectName("navBadge")
        self.badge.setVisible(badge > 0)
        if badge > 0:
            self.badge.setText(str(badge))
        lay.addWidget(self.badge)
        self._paint()

    def mouseReleaseEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(ev)

    def set_on(self, on: bool):
        self._on = on
        self.setProperty("on", "true" if on else "false")
        self.lbl.setProperty("on", "true" if on else "false")
        self.badge.setProperty("on", "true" if on else "false")
        self._paint()
        _repolish(self)
        _repolish(self.lbl)
        _repolish(self.badge)

    def _paint(self):
        color = "#FFFFFF" if self._on else "#6E6E73"
        pix = icon(self._icon_name, color, 17).pixmap(17, 17)
        self.icon_lbl.setPixmap(pix)


class Toggle(QFrame):
    """iOS 风格开关。"""
    toggled = pyqtSignal(bool)

    def __init__(self, on: bool = False, parent=None):
        super().__init__(parent)
        self.setObjectName("tg")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedSize(40, 24)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._on = on
        self._knob = QLabel(self)
        self._knob.setObjectName("tgKnob")
        self._knob.setFixedSize(20, 20)
        self._knob.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._apply()
        self._anim = QPropertyAnimation(self._knob, b"pos", self)
        self._anim.setDuration(200)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    def _apply(self):
        self.setProperty("on", "true" if self._on else "false")
        _repolish(self)
        self._knob.move(2 if not self._on else 18, 2)

    def mouseReleaseEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton:
            self._on = not self._on
            self._apply()
            self._anim.stop()
            self._anim.setStartValue(QPointF(self._knob.pos()))
            self._anim.setEndValue(QPointF(2 if not self._on else 18, 2))
            self._anim.start()
            self.toggled.emit(self._on)
        super().mouseReleaseEvent(ev)

    def set_on(self, on: bool):
        if on != self._on:
            self._on = on
            self._apply()


class Segmented(QFrame):
    changed = pyqtSignal(int)

    def __init__(self, items: list[str], index: int = 0, parent=None):
        super().__init__(parent)
        self.setObjectName("segmented")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(2, 2, 2, 2)
        lay.setSpacing(2)
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        for i, it in enumerate(items):
            b = QPushButton(it)
            b.setObjectName("segBtn")
            b.setCheckable(True)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setProperty("idx", i)
            b.clicked.connect(lambda _, k=i: self.changed.emit(k))
            self._group.addButton(b)
            lay.addWidget(b)
            if i == index:
                b.setChecked(True)

    def set_index(self, i: int):
        for b in self._group.buttons():
            if b.property("idx") == i:
                b.setChecked(True)
                return


class Picker(QFrame):
    changed = pyqtSignal(int)

    def __init__(self, items: list[str], index: int = 0, parent=None):
        super().__init__(parent)
        self.setObjectName("picker")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(2, 2, 2, 2)
        lay.setSpacing(2)
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        for i, it in enumerate(items):
            b = QPushButton(it)
            b.setObjectName("pkBtn")
            b.setCheckable(True)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setProperty("idx", i)
            b.clicked.connect(lambda _, k=i: self.changed.emit(k))
            self._group.addButton(b)
            lay.addWidget(b)
            if i == index:
                b.setChecked(True)

    def set_index(self, i: int):
        for b in self._group.buttons():
            if b.property("idx") == i:
                b.setChecked(True)
                return


class CoverArt(QWidget):
    """手绘海报封面:渐变 + 标签 + 标题 + 悬停加号。"""

    def __init__(self, title: str, tag: str = "", sub: str = "",
                 colors: tuple[str, str] = ("#B3271E", "#5A1109"),
                 radius: int = 14, hover_plus: bool = False, parent=None):
        super().__init__(parent)
        self.title = title
        self.tag = tag
        self.sub = sub
        self.colors = colors
        self.radius = radius
        self.hover_plus = hover_plus
        self._hovered = False
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setMinimumSize(1, 1)

    def enterEvent(self, ev):
        if self.hover_plus:
            self._hovered = True
            self.update()
        super().enterEvent(ev)

    def leaveEvent(self, ev):
        if self.hover_plus:
            self._hovered = False
            self.update()
        super().leaveEvent(ev)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        r = min(self.radius, w // 3, h // 3)
        path = QPainterPath()
        path.addRoundedRect(QRectF(0, 0, w, h), r, r)
        p.setClipPath(path)

        grad = QLinearGradient(0, 0, w, h)
        grad.setColorAt(0, QColor(self.colors[0]))
        grad.setColorAt(1, QColor(self.colors[1]))
        p.fillRect(0, 0, w, h, grad)

        # 底部压暗,文字可读
        shade = QLinearGradient(0, h * 0.45, 0, h)
        shade.setColorAt(0, QColor(0, 0, 0, 0))
        shade.setColorAt(1, QColor(0, 0, 0, 130))
        p.fillRect(0, 0, w, h, shade)

        # 标签
        if self.tag:
            f = QFont()
            f.setPointSizeF(max(8.0, w * 0.063))
            f.setWeight(QFont.Weight.DemiBold)
            p.setFont(f)
            tw = p.fontMetrics().horizontalAdvance(self.tag) + 14
            th = p.fontMetrics().height() + 5
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(0, 0, 0, 120))
            p.drawRoundedRect(QRectF(8, 8, tw, th), th / 2, th / 2)
            p.setPen(QColor(255, 255, 255))
            p.drawText(QRectF(8, 8, tw, th), Qt.AlignmentFlag.AlignCenter, self.tag)

        # 标题 + 副标题(中文在上,英文小字在下,与参考稿一致)
        f2 = QFont()
        f2.setPointSizeF(max(9.5, w * 0.085))
        f2.setWeight(QFont.Weight.Bold)
        p.setFont(f2)
        p.setPen(QColor(255, 255, 255))
        title_rect = QRectF(10, h * 0.52, w - 20, h * 0.34)
        p.drawText(title_rect, Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignLeft, self.title)

        if self.sub:
            f3 = QFont()
            f3.setPointSizeF(max(6.5, w * 0.055))
            f3.setWeight(QFont.Weight.Medium)
            p.setFont(f3)
            p.setPen(QColor(255, 255, 255, 200))
            p.drawText(QRectF(10, h * 0.88, w - 20, h * 0.08),
                       Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft,
                       self.sub.upper())

        # 悬停加号
        if self.hover_plus and self._hovered:
            s = w * 0.16
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(255, 255, 255, 56))
            p.drawEllipse(QRectF(w - s - 8, 8, s, s))
            p.setPen(QPen(QColor(255, 255, 255), max(1.6, w * 0.02),
                          Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            cx, cy = w - s - 8 + s / 2, 8 + s / 2
            p.drawLine(QPointF(cx - s * 0.28, cy), QPointF(cx + s * 0.28, cy))
            p.drawLine(QPointF(cx, cy - s * 0.28), QPointF(cx, cy + s * 0.28))


class PosterCard(QWidget):
    """海报卡片:封面 + 元信息,悬停浮起。"""
    clicked = pyqtSignal()

    def __init__(self, title: str, tag: str, sub: str,
                 colors: tuple[str, str], en: str = "", parent=None):
        super().__init__(parent)
        self.setFixedWidth(150)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._hover = False
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(7)
        self.art = CoverArt(title, tag, en or "", colors, radius=14, hover_plus=True)
        self.art.setFixedHeight(225)
        lay.addWidget(self.art)
        meta = QVBoxLayout()
        meta.setSpacing(1)
        t = QLabel(title)
        t.setObjectName("cardTitle")
        t.setStyleSheet("font-size:13px;")
        meta.addWidget(t)
        s = QLabel(sub)
        s.setObjectName("cardMeta")
        s.setStyleSheet("font-size:11.5px;")
        meta.addWidget(s)
        lay.addLayout(meta)
        lay.addStretch(1)

        self._eff = _shadow(0, 0, 0)
        self.setGraphicsEffect(self._eff)

    def enterEvent(self, ev):
        self._hover = True
        self._animate(16, 5, 60)
        super().enterEvent(ev)

    def leaveEvent(self, ev):
        self._hover = False
        self._animate(0, 0, 0)
        super().leaveEvent(ev)

    def _animate(self, blur: float, dy: float, alpha: int):
        self._eff.setBlurRadius(blur)
        self._eff.setOffset(0, dy)
        self._eff.setColor(QColor(0, 0, 0, alpha))

    def mouseReleaseEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(ev)


class Thumb(QWidget):
    """任务行小封面。"""

    def __init__(self, title: str, colors: tuple[str, str], parent=None):
        super().__init__(parent)
        self.title = title
        self.colors = colors
        self.setFixedSize(38, 56)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(QRectF(0, 0, 38, 56), 6, 6)
        p.setClipPath(path)
        grad = QLinearGradient(0, 0, 38, 56)
        grad.setColorAt(0, QColor(self.colors[0]))
        grad.setColorAt(1, QColor(self.colors[1]))
        p.fillRect(0, 0, 38, 56, grad)
        f = QFont()
        f.setPointSize(10)
        f.setWeight(QFont.Weight.Bold)
        p.setFont(f)
        p.setPen(QColor(255, 255, 255))
        p.drawText(QRectF(0, 16, 38, 24), Qt.AlignmentFlag.AlignCenter, self.title[:1])


def _palette_pair(key: str) -> tuple[str, str]:
    """根据文本生成稳定的双色渐变。"""
    import hashlib
    h = hashlib.md5(key.encode("utf-8")).hexdigest()
    pal = [
        ("#B3271E", "#5A1109"), ("#C97B3F", "#4A2410"), ("#1F4E5F", "#0A1F2A"),
        ("#7A2E3E", "#2A0E16"), ("#3A3A44", "#141418"), ("#8E5A2E", "#2E1B0C"),
        ("#1E6B52", "#0A241C"), ("#4A5568", "#161A21"), ("#A8324B", "#340D16"),
        ("#2D5016", "#0C1A08"), ("#6B2D5B", "#200C1C"), ("#C46A1E", "#3A1A05"),
    ]
    return pal[int(h, 16) % len(pal)]


# ====================================================================
#  示例剧库(UI 演示用,接入平台后显示真实内容)
# ====================================================================
DEMO_DRAMAS = [
    {"t": "重回1998", "en": "BACK TO 1998", "g": ("#B3271E", "#5A1109"), "tag": "80集", "m": "2025 · 逆袭", "cat": "逆袭"},
    {"t": "契约新娘", "en": "THE CONTRACT BRIDE", "g": ("#C97B3F", "#4A2410"), "tag": "72集", "m": "2025 · 甜宠", "cat": "甜宠"},
    {"t": "深夜食堂", "en": "MIDNIGHT DINER", "g": ("#1F4E5F", "#0A1F2A"), "tag": "64集", "m": "2024 · 都市", "cat": "都市"},
    {"t": "长安十二时辰", "en": "CHANG'AN", "g": ("#7A2E3E", "#2A0E16"), "tag": "95集", "m": "2024 · 古装", "cat": "古装"},
    {"t": "消失的第九集", "en": "THE MISSING EP", "g": ("#3A3A44", "#141418"), "tag": "48集", "m": "2025 · 悬疑", "cat": "悬疑"},
    {"t": "我的房东是巨星", "en": "MY LANDLORD", "g": ("#8E5A2E", "#2E1B0C"), "tag": "56集", "m": "2025 · 喜剧", "cat": "都市"},
    {"t": "重生之我要暴富", "en": "REBORN RICH", "g": ("#1E6B52", "#0A241C"), "tag": "100集", "m": "2024 · 爽剧", "cat": "爽剧"},
    {"t": "雾中迷城", "en": "FOG CITY", "g": ("#4A5568", "#161A21"), "tag": "60集", "m": "2025 · 悬疑", "cat": "悬疑"},
    {"t": "总裁的隐婚妻子", "en": "HIDDEN WIFE", "g": ("#A8324B", "#340D16"), "tag": "88集", "m": "2025 · 甜宠", "cat": "甜宠"},
    {"t": "铁血军医", "en": "IRON MEDIC", "g": ("#2D5016", "#0C1A08"), "tag": "76集", "m": "2024 · 军事", "cat": "爽剧"},
    {"t": "画皮新娘", "en": "PAINTED SKIN", "g": ("#6B2D5B", "#200C1C"), "tag": "52集", "m": "2025 · 惊悚", "cat": "悬疑"},
    {"t": "外卖骑手封神", "en": "THE COURIER", "g": ("#C46A1E", "#3A1A05"), "tag": "68集", "m": "2025 · 现实", "cat": "现实"},
]
CATS = ["全部", "都市", "甜宠", "逆袭", "古装", "悬疑", "爽剧", "现实"]


# ====================================================================
#  搜索页
# ====================================================================
class SearchPage(QWidget):
    drama_selected = pyqtSignal(object)  # Drama | dict

    def __init__(self, orchestrator: SearchOrchestrator, parent=None):
        super().__init__(parent)
        self.orchestrator = orchestrator
        self.current_cat = "全部"
        self._mode = "demo"  # demo | search
        self._build()

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        outer.addWidget(self.scroll)

        self.content = QWidget()
        self.scroll.setWidget(self.content)
        self.lay = QVBoxLayout(self.content)
        self.lay.setContentsMargins(24, 24, 24, 32)
        self.lay.setSpacing(0)

        self.lbl_h1 = make_h1("发现短剧")
        self.lay.addWidget(self.lbl_h1)
        self.lbl_sub = make_sub("示例剧库 · 演示 UI,接入平台适配后显示真实搜索结果")
        self.lay.addWidget(self.lbl_sub)

        # 分类 chips
        self.chips_wrap = QWidget()
        ch = QHBoxLayout(self.chips_wrap)
        ch.setContentsMargins(0, 16, 0, 0)
        ch.setSpacing(7)
        self._chip_group = QButtonGroup(self)
        self._chip_group.setExclusive(True)
        for i, c in enumerate(CATS):
            b = QPushButton(c)
            b.setObjectName("chip")
            b.setCheckable(True)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setProperty("cat", c)
            b.clicked.connect(lambda _, k=c: self._on_cat(k))
            self._chip_group.addButton(b)
            ch.addWidget(b)
            if i == 0:
                b.setChecked(True)
        ch.addStretch(1)
        self.lay.addWidget(self.chips_wrap)

        # 区块头
        self.sec = QWidget()
        sh = QHBoxLayout(self.sec)
        sh.setContentsMargins(0, 22, 0, 0)
        sh.setSpacing(10)
        self.sec_title = make_sec_title("为你推荐")
        sh.addWidget(self.sec_title)
        self.sec_count = make_sec_count("12 部")
        sh.addWidget(self.sec_count)
        sh.addStretch(1)
        self.sec_act = make_sec_act("回到示例剧库")
        self.sec_act.setVisible(False)
        self.sec_act.clicked.connect(self._back_to_demo)
        sh.addWidget(self.sec_act)
        self.lay.addWidget(self.sec)

        self.grid_wrap = QWidget()
        self.grid = QGridLayout(self.grid_wrap)
        self.grid.setContentsMargins(0, 16, 0, 0)
        self.grid.setHorizontalSpacing(16)
        self.grid.setVerticalSpacing(24)
        self.grid.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.lay.addWidget(self.grid_wrap)
        self.lay.addStretch(1)

        self.scroll.viewport().installEventFilter(self)
        self._show_demo()

    def eventFilter(self, obj, ev):
        from PyQt6.QtCore import QEvent
        if obj is self.scroll.viewport() and ev.type() == QEvent.Type.Resize:
            self._relayout()
        return super().eventFilter(obj, ev)

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        QTimer.singleShot(0, self._relayout)

    def showEvent(self, ev):
        super().showEvent(ev)
        QTimer.singleShot(0, self._relayout)

    # ---- 数据 ----
    def _show_demo(self):
        self._mode = "demo"
        self.lbl_h1.setText("发现短剧")
        self.lbl_sub.setText("示例剧库 · 演示 UI,接入平台适配后显示真实搜索结果")
        self.sec_title.setText("为你推荐")
        self.sec_act.setVisible(False)
        self.chips_wrap.setVisible(True)
        self._fill_demo()

    def _back_to_demo(self):
        self._show_demo()

    def _fill_demo(self):
        items = [d for d in DEMO_DRAMAS
                 if self.current_cat == "全部" or d["cat"] == self.current_cat]
        self.sec_count.setText(f"{len(items)} 部")
        self._render_panels([
            (d["t"], d["tag"], d["m"], d["g"], d["en"], d) for d in items
        ])

    def _show_results(self, results: list[Drama]):
        self._mode = "search"
        self.lbl_h1.setText("搜索结果")
        self.lbl_sub.setText(f"跨平台并发搜索 · 共 {len(results)} 条(红果/河马适配器未接入时为空)")
        self.sec_title.setText("搜索到的短剧")
        self.sec_act.setVisible(True)
        self.chips_wrap.setVisible(False)
        if results:
            self._render_panels([
                (d.title, f"{d.episode_count}集", d.platform, _palette_pair(d.drama_id or d.title),
                 d.platform, d) for d in results
            ])
        else:
            self._render_empty(
                "未找到结果",
                "红果 / 河马平台适配器尚未接入(签名待逆向),"
                "当前只能搜索到已实现 search 接口的平台。\n可点击右上角「回到示例剧库」查看 UI 演示。",
            )

    def _render_panels(self, panels):
        while self.grid.count():
            it = self.grid.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        self._panels = []
        for i, (t, tag, m, g, en, data) in enumerate(panels):
            card = PosterCard(t, tag, m, g, en)
            card.clicked.connect(lambda _, d=data: self._on_pick(d))
            self._panels.append(card)
        QTimer.singleShot(0, self._relayout)

    def _relayout(self):
        if not hasattr(self, "_panels"):
            return
        w = self.scroll.viewport().width() - 48  # 页面左右内边距
        cols = max(2, (w + 16) // (150 + 16))
        for i, card in enumerate(self._panels):
            r, c = divmod(i, cols)
            self.grid.addWidget(card, r, c)

    def _render_empty(self, title: str, sub: str):
        while self.grid.count():
            it = self.grid.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        box = QWidget()
        bl = QVBoxLayout(box)
        bl.setContentsMargins(0, 60, 0, 60)
        bl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tl = QLabel(title)
        tl.setObjectName("emptyT")
        tl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sl = QLabel(sub)
        sl.setObjectName("emptyS")
        sl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sl.setWordWrap(True)
        sl.setMaximumWidth(460)
        bl.addWidget(tl)
        bl.addWidget(sl)
        self.grid.addWidget(box, 0, 0, Qt.AlignmentFlag.AlignCenter)

    # ---- 交互 ----
    def _on_cat(self, cat: str):
        self.current_cat = cat
        if self._mode == "demo":
            self._fill_demo()

    def _on_pick(self, data):
        self.drama_selected.emit(data)

    def do_search(self, keyword: str):
        kw = keyword.strip()
        if not kw:
            return
        self.lbl_h1.setText("搜索中…")
        self.lbl_sub.setText(f"正在跨平台搜索「{kw}」…")
        self.sec_act.setVisible(False)
        self.chips_wrap.setVisible(False)
        self._render_empty("搜索中…", "正在并发请求各平台,请稍候")
        self._worker = SearchWorker(self.orchestrator, kw)
        buf = []

        def _on_result(d):
            buf.append(d)

        def _on_done():
            self._show_results(buf)

        def _on_err(msg):
            self.lbl_sub.setText(f"搜索出错:{msg}")
            self._render_empty("搜索出错", msg)
            self.sec_act.setVisible(True)

        self._worker.result.connect(_on_result)
        self._worker.finished_ok.connect(_on_done)
        self._worker.error.connect(_on_err)
        self._worker.start()


# ====================================================================
#  链接解析页
# ====================================================================
class LinkPage(QWidget):
    drama_loaded = pyqtSignal(object, object)  # Drama, list[Episode]

    def __init__(self, resolver: ShareResolver, parent=None):
        super().__init__(parent)
        self.resolver = resolver
        self.current_drama: Drama | None = None
        self.current_eps: list[Episode] = []
        self._build()

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        outer.addWidget(self.scroll)
        content = QWidget()
        self.scroll.setWidget(content)
        lay = QVBoxLayout(content)
        lay.setContentsMargins(24, 24, 24, 32)
        lay.setSpacing(0)

        lay.addWidget(make_h1("链接解析"))
        lay.addWidget(make_sub("支持分享链接、口令文本,粘贴后自动识别来源 · 自动跟随短链重定向 · 提取剧集 ID"))

        # 拖放区
        self.drop = QFrame()
        self.drop.setObjectName("drop")
        self.drop.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.drop.setAcceptDrops(True)
        self.drop.setMinimumHeight(170)
        dl = QVBoxLayout(self.drop)
        dl.setContentsMargins(24, 32, 24, 32)
        dl.setSpacing(0)
        ic_box = QFrame()
        ic_box.setObjectName("dropIcon")
        ic_box.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        ic_box.setFixedSize(48, 48)
        ic_lay = QVBoxLayout(ic_box)
        ic_lay.setContentsMargins(0, 0, 0, 0)
        ic_lbl = QLabel()
        ic_lbl.setPixmap(icon("clipboard", "#007AFF", 22).pixmap(22, 22))
        ic_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ic_lay.addWidget(ic_lbl)
        dl.addWidget(ic_box, alignment=Qt.AlignmentFlag.AlignHCenter)
        self.drop_t = QLabel("拖入文件,或粘贴分享口令")
        self.drop_t.setObjectName("dropT")
        self.drop_t.setAlignment(Qt.AlignmentFlag.AlignCenter)
        dl.addWidget(self.drop_t)
        self.drop_s = QLabel("支持 v.douyin.com / iesdouyin / hongguo / hema 短链")
        self.drop_s.setObjectName("dropS")
        self.drop_s.setAlignment(Qt.AlignmentFlag.AlignCenter)
        dl.addWidget(self.drop_s)
        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(0, 16, 0, 0)
        btn_row.setSpacing(8)
        self.btn_paste = make_primary("📋 粘贴链接")
        self.btn_paste.clicked.connect(self._paste_and_parse)
        btn_row.addStretch(1)
        btn_row.addWidget(self.btn_paste)
        self.btn_manual = make_secondary("手动输入")
        self.btn_manual.clicked.connect(self._toggle_manual)
        btn_row.addWidget(self.btn_manual)
        btn_row.addStretch(1)
        dl.addLayout(btn_row)
        lay.addWidget(self.drop)

        # 手动输入区
        self.manual_box = QWidget()
        mb = QVBoxLayout(self.manual_box)
        mb.setContentsMargins(0, 16, 0, 0)
        mb.setSpacing(10)
        self.input_share = QTextEdit()
        self.input_share.setPlaceholderText(
            "把抖音 / 红果 / 河马的分享文案整段贴进来,自动识别链接。\n"
            "示例:[红果短剧] 龙王驾到 https://v.douyin.com/abc123/"
        )
        self.input_share.setMaximumHeight(96)
        mb.addWidget(self.input_share)
        row = QHBoxLayout()
        row.setSpacing(8)
        row.addStretch(1)
        self.btn_parse = make_primary("🔍 解析")
        self.btn_parse.clicked.connect(self.do_parse)
        row.addWidget(self.btn_parse)
        mb.addLayout(row)
        self.manual_box.setVisible(False)
        lay.addWidget(self.manual_box)

        # 解析结果
        sec = QWidget()
        sh = QHBoxLayout(sec)
        sh.setContentsMargins(0, 26, 0, 0)
        sh.setSpacing(10)
        sh.addWidget(make_sec_title("解析结果"))
        self.sec_count = make_sec_count("0 条")
        sh.addWidget(self.sec_count)
        sh.addStretch(1)
        lay.addWidget(sec)

        self.result_card = make_card()
        rc = QVBoxLayout(self.result_card)
        rc.setContentsMargins(0, 0, 0, 0)
        rc.setSpacing(0)
        self.result_row = QWidget()
        rr = QHBoxLayout(self.result_row)
        rr.setContentsMargins(16, 14, 16, 14)
        rr.setSpacing(14)
        self.result_thumb = Thumb("?", ("#8E8E93", "#48484A"))
        rr.addWidget(self.result_thumb)
        info = QVBoxLayout()
        info.setSpacing(3)
        self.result_title = QLabel("等待解析…")
        self.result_title.setObjectName("tTitle")
        info.addWidget(self.result_title)
        self.result_meta = QLabel("粘贴分享链接后自动识别")
        self.result_meta.setObjectName("tSub")
        info.addWidget(self.result_meta)
        rr.addLayout(info, 1)
        self.btn_sel_all = make_secondary("全选")
        self.btn_sel_all.setVisible(False)
        self.btn_sel_all.clicked.connect(self._select_all)
        rr.addWidget(self.btn_sel_all)
        self.btn_enqueue = make_primary("加入队列")
        self.btn_enqueue.setVisible(False)
        self.btn_enqueue.clicked.connect(self._enqueue)
        rr.addWidget(self.btn_enqueue)
        rc.addWidget(self.result_row)
        self.ep_list = QListWidget()
        self.ep_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        self.ep_list.setMaximumHeight(160)
        self.ep_list.setVisible(False)
        rc.addWidget(self.ep_list)
        self.result_card.setVisible(False)
        lay.addWidget(self.result_card)

        # 最近解析
        sec2 = QWidget()
        sh2 = QHBoxLayout(sec2)
        sh2.setContentsMargins(0, 26, 0, 0)
        sh2.setSpacing(10)
        sh2.addWidget(make_sec_title("最近解析"))
        self.recent_count = make_sec_count("0 条")
        sh2.addWidget(self.recent_count)
        sh2.addStretch(1)
        self.btn_clear_recent = make_sec_act("清空")
        self.btn_clear_recent.clicked.connect(self._clear_recent)
        sh2.addWidget(self.btn_clear_recent)
        lay.addWidget(sec2)

        self.recent_card = make_card()
        self.recent_lay = QVBoxLayout(self.recent_card)
        self.recent_lay.setContentsMargins(0, 0, 0, 0)
        self.recent_lay.setSpacing(0)
        lay.addWidget(self.recent_card)
        lay.addStretch(1)

        self._recent = json.loads(SETTINGS.value("recent_parses", "[]"))
        self._render_recent()

    # ---- 拖放 ----
    def dragEnterEvent(self, ev):
        if ev.mimeData().hasUrls() or ev.mimeData().hasText():
            self.drop.setProperty("hot", "true")
            _repolish(self.drop)
            ev.acceptProposedAction()
        super().dragEnterEvent(ev)

    def dragLeaveEvent(self, ev):
        self.drop.setProperty("hot", "false")
        _repolish(self.drop)
        super().dragLeaveEvent(ev)

    def dropEvent(self, ev):
        self.drop.setProperty("hot", "false")
        _repolish(self.drop)
        texts = []
        if ev.mimeData().hasUrls():
            for u in ev.mimeData().urls():
                if u.isLocalFile():
                    texts.append(Path(u.toLocalFile()).read_text(encoding="utf-8", errors="ignore"))
                else:
                    texts.append(u.toString())
        if ev.mimeData().hasText():
            texts.append(ev.mimeData().text())
        text = "\n".join(texts)
        if text.strip():
            self._parse(text)
        ev.acceptProposedAction()
        super().dropEvent(ev)

    def _toggle_manual(self):
        self.manual_box.setVisible(not self.manual_box.isVisible())

    def _paste_and_parse(self):
        cb = QApplication.clipboard().text()
        if cb and cb.strip():
            self._parse(cb)
        else:
            self._toggle_manual()

    def _select_all(self):
        if self.ep_list.count() == 0:
            return
        if all(self.ep_list.item(i).isSelected() for i in range(self.ep_list.count())):
            self.ep_list.clearSelection()
        else:
            self.ep_list.selectAll()

    def do_parse(self):
        text = self.input_share.toPlainText().strip()
        if not text:
            QMessageBox.information(self, "提示", "先粘贴分享文本")
            return
        self._parse(text)

    def _parse(self, text: str):
        self.result_card.setVisible(True)
        self.result_title.setText("解析中…")
        self.result_meta.setText("正在跟随重定向并提取剧集 ID…")

        async def _do():
            return await self.resolver.resolve(text)

        try:
            loop = asyncio.new_event_loop()
            try:
                parsed, drama = loop.run_until_complete(_do())
            finally:
                loop.close()
        except Exception as e:  # noqa: BLE001
            self.result_title.setText("解析出错")
            self.result_meta.setText(str(e))
            self.btn_enqueue.setVisible(False)
            self.btn_sel_all.setVisible(False)
            self.ep_list.setVisible(False)
            return

        self.ep_list.clear()
        self.current_drama = drama
        self.current_eps = []

        if not parsed or not parsed.url:
            self.result_title.setText("未识别到链接")
            self.result_meta.setText("文本里没找到支持的分享链接(v.douyin / iesdouyin / hongguo / hema)")
            self.btn_enqueue.setVisible(False)
            self.btn_sel_all.setVisible(False)
            self.ep_list.setVisible(False)
            return

        # 记录最近
        self._recent.insert(0, {
            "text": parsed.url[:48], "time": "刚刚",
            "final": parsed.final_url[:60], "platform": parsed.platform,
        })
        self._recent = self._recent[:6]
        SETTINGS.setValue("recent_parses", json.dumps(self._recent, ensure_ascii=False))
        self._render_recent()

        if drama:
            self.result_title.setText(drama.title)
            self.result_meta.setText(
                f"已识别 · {drama.platform} · {drama.episode_count} 集 · 链接已跟随重定向"
            )
            self.result_thumb = None  # 保持占位
            try:
                loop2 = asyncio.new_event_loop()
                try:
                    platform = next(
                        (p for p in self.resolver.platforms
                         if any(d in parsed.platform or d in parsed.domain for d in p.url_domains)),
                        None,
                    )
                    if platform:
                        eps = loop2.run_until_complete(platform.get_episodes(drama))
                        self.current_eps = eps
                        for ep in eps:
                            item = QListWidgetItem(f"第{ep.index}集 · {ep.title}")
                            item.setSizeHint(item.sizeHint())
                            item.setData(Qt.ItemDataRole.UserRole, ep)
                            self.ep_list.addItem(item)
                        self.ep_list.setVisible(True)
                        self.sec_count.setText(f"{len(eps)} 集")
                        self.btn_sel_all.setVisible(True)
                        self.btn_enqueue.setVisible(True)
                        self.btn_enqueue.setText(f"加入队列({len(eps)} 集)")
                finally:
                    loop2.close()
            except Exception as e:  # noqa: BLE001
                self.result_meta.setText(f"已识别链接,但拉剧集失败:{e}")
        else:
            self.result_title.setText("已识别链接(平台适配器未接入)")
            self.result_meta.setText(
                f"{parsed.platform} · 剧 ID:{parsed.drama_id}\n"
                "红果/河马需要先逆向签名才能拉到剧集列表与真实播放地址。"
            )
            self.btn_enqueue.setVisible(False)
            self.btn_sel_all.setVisible(False)

        self.drama_loaded.emit(drama, self.current_eps)

    def _enqueue(self):
        from .core.task_store import TaskStore
        from .core.downloader import DownloadEngine
        store = TaskStore()
        engine = DownloadEngine()
        sel = [self.ep_list.item(i).data(Qt.ItemDataRole.UserRole)
               for i in range(self.ep_list.count()) if self.ep_list.item(i).isSelected()]
        targets = sel or self.current_eps
        if not targets:
            QMessageBox.information(self, "提示", "先选中要下载的集数")
            return
        real = [e for e in targets if e.play_url]
        if not real:
            QMessageBox.information(
                self, "已加入待办",
                "平台适配器未接入,剧集暂无真实播放地址。\n"
                "待接入签名后,真实 URL 解析出来即可自动开始下载。",
            )
            return
        # 真实 URL 才真正入队
        for ep in real:
            t = store.add_task(
                platform=self.current_drama.platform if self.current_drama else "",
                drama_title=self.current_drama.title if self.current_drama else "",
                episode_title=ep.title,
                episode_index=ep.index,
                url=ep.play_url,
                save_path="./downloads",
                engine="native",
            )
            worker = DownloadWorker(engine, ep, ep.play_url, "./downloads", store, t.id)
            worker.done.connect(lambda _, path: QMessageBox.information(self, "下载完成", str(path)))
            worker.failed.connect(lambda _, err: QMessageBox.warning(self, "下载失败", err))
            worker.start()
        self.drama_loaded.emit(self.current_drama, self.current_eps)

    def _render_recent(self):
        while self.recent_lay.count():
            it = self.recent_lay.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        self.recent_count.setText(f"{len(self._recent)} 条")
        if not self._recent:
            self.recent_card.setVisible(False)
            return
        self.recent_card.setVisible(True)
        for r in self._recent:
            row = QWidget()
            rh = QHBoxLayout(row)
            rh.setContentsMargins(16, 10, 16, 10)
            rh.setSpacing(10)
            ic = QLabel()
            ic.setPixmap(icon("search", "#AEAEB2", 15).pixmap(15, 15))
            rh.addWidget(ic)
            txt = QLabel(r["text"])
            txt.setStyleSheet("font-size:13px;")
            txt.setObjectName("cardMeta")
            rh.addWidget(txt, 1)
            tm = QLabel(r["time"])
            tm.setObjectName("cardMeta")
            tm.setStyleSheet("font-size:11.5px;")
            rh.addWidget(tm)
            self.recent_lay.addWidget(row)
            if r is not self._recent[-1]:
                line = QFrame()
                line.setFrameShape(QFrame.Shape.HLine)
                line.setStyleSheet("color:rgba(0,0,0,.06);background:rgba(0,0,0,.06);max-height:1px;")
                self.recent_lay.addWidget(line)

    def _clear_recent(self):
        self._recent = []
        SETTINGS.setValue("recent_parses", "[]")
        self._render_recent()


# ====================================================================
#  任务队列页
# ====================================================================
class TasksPage(QWidget):
    def __init__(self, store: TaskStore, parent=None):
        super().__init__(parent)
        self.store = store
        self.filter = "全部"
        self._build()

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        outer.addWidget(self.scroll)
        content = QWidget()
        self.scroll.setWidget(content)
        lay = QVBoxLayout(content)
        lay.setContentsMargins(24, 24, 24, 32)
        lay.setSpacing(0)

        head = QWidget()
        hh = QHBoxLayout(head)
        hh.setContentsMargins(0, 0, 0, 0)
        hh.setSpacing(12)
        left = QVBoxLayout()
        left.setSpacing(0)
        self.lbl_h1 = make_h1("任务队列")
        left.addWidget(self.lbl_h1)
        self.lbl_sub = make_sub("加载中…")
        left.addWidget(self.lbl_sub)
        hh.addLayout(left, 1)
        self.seg = Segmented(["全部", "进行中", "已完成", "失败"], 0)
        self.seg.changed.connect(self._on_filter)
        hh.addWidget(self.seg)
        self.btn_pause_all = make_secondary("全部暂停")
        self.btn_pause_all.clicked.connect(self._toggle_pause_all)
        hh.addWidget(self.btn_pause_all)
        lay.addWidget(head)

        self.tasks_box = QWidget()
        self.tasks_lay = QVBoxLayout(self.tasks_box)
        self.tasks_lay.setContentsMargins(0, 18, 0, 0)
        self.tasks_lay.setSpacing(8)
        self.tasks_lay.addStretch(1)
        lay.addWidget(self.tasks_box)

        # 存储卡
        sec = QWidget()
        sh = QHBoxLayout(sec)
        sh.setContentsMargins(0, 22, 0, 0)
        sh.addWidget(make_sec_title("存储"))
        lay.addWidget(sec)
        self.storage_card = make_card()
        sr = QHBoxLayout(self.storage_card)
        sr.setContentsMargins(16, 14, 16, 14)
        sr.setSpacing(14)
        self.storage_info = QVBoxLayout()
        self.storage_info.setSpacing(3)
        self.storage_dir = QLabel(SETTINGS.value("save_dir", "./downloads"))
        self.storage_dir.setObjectName("tTitle")
        self.storage_info.addWidget(self.storage_dir)
        self.storage_meta = QLabel("—")
        self.storage_meta.setObjectName("tSub")
        self.storage_info.addWidget(self.storage_meta)
        sr.addLayout(self.storage_info, 1)
        self.storage_bar = QProgressBar()
        self.storage_bar.setFixedWidth(220)
        self.storage_bar.setRange(0, 100)
        sr.addWidget(self.storage_bar)
        self.btn_change = make_secondary("更改位置")
        self.btn_change.clicked.connect(self._change_dir)
        sr.addWidget(self.btn_change)
        lay.addWidget(self.storage_card)
        lay.addStretch(1)

        self.refresh()

    def _on_filter(self, i: int):
        self.filter = ["全部", "进行中", "已完成", "失败"][i]
        self.refresh()

    def refresh(self):
        tasks = self.store.list_tasks(limit=200)
        active = sum(1 for t in tasks if t.status == "downloading")
        done_n = sum(1 for t in tasks if t.status == "done")
        failed_n = sum(1 for t in tasks if t.status == "failed")
        self.lbl_sub.setText(
            f"{active} 个进行中 · {failed_n} 个失败 · 累计 {done_n} 个已完成"
        )
        shown = tasks
        if self.filter == "进行中":
            shown = [t for t in tasks if t.status in ("downloading", "pending")]
        elif self.filter == "已完成":
            shown = [t for t in tasks if t.status == "done"]
        elif self.filter == "失败":
            shown = [t for t in tasks if t.status == "failed"]

        while self.tasks_lay.count():
            it = self.tasks_lay.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        self.tasks_lay.addStretch(1)

        if not shown:
            empty = QLabel("暂无任务\n\n去「搜索」或「链接解析」添加下载任务")
            empty.setObjectName("emptyS")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setWordWrap(True)
            self.tasks_lay.insertWidget(0, empty)
            return

        for i, t in enumerate(shown):
            self.tasks_lay.insertWidget(i, self._make_task_card(t))

        self._refresh_storage()

    def _make_task_card(self, t: Task) -> QWidget:
        card = QFrame()
        card.setObjectName("taskCard")
        card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        st_map = {"done": "ok", "failed": "err", "downloading": "run",
                  "paused": "wait", "pending": "wait", "queued": "wait"}
        card.setProperty("st", st_map.get(t.status, "wait"))
        _repolish(card)
        row = QHBoxLayout(card)
        row.setContentsMargins(12, 12, 12, 12)
        row.setSpacing(12)

        thumb = Thumb(t.drama_title or "剧", _palette_pair(t.drama_title or t.episode_title))
        row.addWidget(thumb)

        body = QVBoxLayout()
        body.setSpacing(3)
        title = QLabel(f"{t.drama_title or '未知剧集'} · {t.episode_title}")
        title.setObjectName("tTitle")
        body.addWidget(title)
        sub_row = QHBoxLayout()
        sub_row.setSpacing(8)
        tag_text = {"done": "已完成", "failed": "失败", "downloading": "下载中",
                    "paused": "已暂停", "pending": "等待中", "queued": "排队中"}[t.status]
        tag_st = {"done": "ok", "failed": "err", "downloading": "run",
                  "paused": "wait", "pending": "wait", "queued": "wait"}[t.status]
        sub_row.addWidget(make_tag(tag_text, tag_st))
        if t.total_size:
            sub_row.addWidget(QLabel(f"{t.done_size/1048576:.1f} / {t.total_size/1048576:.1f} MB"))
        sub_row.addStretch(1)
        body.addLayout(sub_row)
        bar = QProgressBar()
        bar.setObjectName("bar")
        bar.setRange(0, 1000)
        pct = int((t.done_size / t.total_size * 1000)) if t.total_size else 0
        bar.setValue(pct)
        bar.setProperty("state", st_map.get(t.status, "wait"))
        _repolish(bar)
        bar.setTextVisible(False)
        bar.setFixedHeight(6)
        body.addWidget(bar)
        row.addLayout(body, 1)

        right = QVBoxLayout()
        right.setSpacing(2)
        pct_lbl = QLabel(f"{pct/10:.1f}%")
        pct_lbl.setObjectName("pct")
        pct_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        right.addWidget(pct_lbl)
        eng = QLabel(t.engine)
        eng.setObjectName("cardMeta")
        eng.setStyleSheet("font-size:11px;")
        eng.setAlignment(Qt.AlignmentFlag.AlignRight)
        right.addWidget(eng)
        row.addLayout(right)

        act = QVBoxLayout()
        act.setSpacing(4)
        if t.status == "failed":
            b = make_secondary("重试")
            b.clicked.connect(lambda _, tt=t: QMessageBox.information(
                self, "重试", "需要平台适配器提供真实播放 URL 才能重试,当前未接入。"))
            act.addWidget(b)
        if t.status in ("done", "failed", "paused", "pending"):
            d = QPushButton()
            d.setObjectName("iconBtn")
            d.setIcon(icon("trash", "#AEAEB2", 14))
            d.setIconSize(d.iconSize())
            d.setFixedSize(26, 26)
            d.setCursor(Qt.CursorShape.PointingHandCursor)
            d.setToolTip("删除记录")
            d.clicked.connect(lambda _, tt=t: self._remove_task(tt))
            act.addWidget(d)
        row.addLayout(act)
        return card

    def _remove_task(self, t: Task):
        self.store.delete_task(t.id)
        self.refresh()

    def _toggle_pause_all(self):
        tasks = self.store.list_tasks(limit=200)
        running = [t for t in tasks if t.status == "downloading"]
        if running:
            for t in running:
                self.store.update_status(t.id, "paused")
            self.btn_pause_all.setText("全部继续")
        else:
            paused = [t for t in tasks if t.status == "paused"]
            for t in paused:
                self.store.update_status(t.id, "downloading")
            self.btn_pause_all.setText("全部暂停")
        self.refresh()

    def _change_dir(self):
        d = QFileDialog.getExistingDirectory(self, "选择保存位置", SETTINGS.value("save_dir", "./downloads"))
        if d:
            SETTINGS.setValue("save_dir", d)
            self.storage_dir.setText(d)
            self._refresh_storage()

    def _refresh_storage(self):
        import shutil
        save = SETTINGS.value("save_dir", "./downloads")
        p = Path(save)
        used = sum(f.stat().st_size for f in p.rglob("*") if f.is_file()) if p.exists() else 0
        self.storage_meta.setText(f"已用 {used/1073741824:.1f} GB")
        try:
            total = shutil.disk_usage(p if p.exists() else Path.home())
            self.storage_bar.setValue(min(100, int(used / max(total.total, 1) * 100)))
        except OSError:
            self.storage_bar.setValue(0)


# ====================================================================
#  已完成页
# ====================================================================
class DonePage(QWidget):
    def __init__(self, store: TaskStore, parent=None):
        super().__init__(parent)
        self.store = store
        self._build()

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        outer.addWidget(self.scroll)
        content = QWidget()
        self.scroll.setWidget(content)
        lay = QVBoxLayout(content)
        lay.setContentsMargins(24, 24, 24, 32)
        lay.setSpacing(0)
        lay.addWidget(make_h1("已完成"))
        self.lbl_sub = make_sub("—")
        lay.addWidget(self.lbl_sub)

        sec = QWidget()
        sh = QHBoxLayout(sec)
        sh.setContentsMargins(0, 22, 0, 0)
        sh.addWidget(make_sec_title("下载完成"))
        self.sec_count = make_sec_count("—")
        sh.addWidget(self.sec_count)
        sh.addStretch(1)
        self.btn_clear = make_sec_act("全部删除")
        self.btn_clear.clicked.connect(self._clear_all)
        sh.addWidget(self.btn_clear)
        lay.addWidget(sec)

        self.grid_wrap = QWidget()
        self.grid = QGridLayout(self.grid_wrap)
        self.grid.setContentsMargins(0, 16, 0, 0)
        self.grid.setHorizontalSpacing(16)
        self.grid.setVerticalSpacing(24)
        self.grid.setAlignment(Qt.AlignmentFlag.AlignTop)
        lay.addWidget(self.grid_wrap)
        lay.addStretch(1)
        self.scroll.viewport().installEventFilter(self)

    def eventFilter(self, obj, ev):
        from PyQt6.QtCore import QEvent
        if obj is self.scroll.viewport() and ev.type() == QEvent.Type.Resize:
            self._relayout()
        return super().eventFilter(obj, ev)

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        QTimer.singleShot(0, self._relayout)

    def showEvent(self, ev):
        super().showEvent(ev)
        QTimer.singleShot(0, self._relayout)

    def refresh(self):
        tasks = self.store.list_tasks(limit=1000)
        done = [t for t in tasks if t.status == "done"]
        by_drama: dict[str, list[Task]] = {}
        for t in done:
            by_drama.setdefault(t.drama_title or "未命名", []).append(t)
        total_size = sum(t.done_size for t in done)
        self.lbl_sub.setText(f"{len(by_drama)} 部短剧 · 共 {total_size/1073741824:.1f} GB")
        self.sec_count.setText(f"{len(by_drama)} 部")

        while self.grid.count():
            it = self.grid.takeAt(0)
            if it.widget():
                it.widget().deleteLater()

        self._cards = []
        for title, eps in by_drama.items():
            colors = _palette_pair(title)
            sub = f"{len(eps)} 集 · {sum(e.done_size for e in eps)/1073741824:.2f} GB"
            card = PosterCard(title, f"{len(eps)}集", sub, colors, en="COMPLETED")
            card.clicked.connect(lambda _, t=title: self._open_folder(t))
            self._cards.append(card)
        self._relayout()

    def _open_folder(self, title: str):
        save = SETTINGS.value("save_dir", "./downloads")
        p = Path(save)
        candidates = list(p.glob(f"*{title}*")) if p.exists() else []
        if candidates:
            QDesktopServices.openUrl(candidates[0].as_uri() if candidates[0].is_dir()
                                     else p.as_uri())
        else:
            QMessageBox.information(self, "提示", f"未找到《{title}》的保存目录")

    def _clear_all(self):
        self.store.clear_finished(keep_days=0)
        self.refresh()

    def _relayout(self):
        if not hasattr(self, "_cards"):
            return
        w = self.scroll.viewport().width() - 48
        cols = max(2, (w + 16) // (150 + 16))
        for i, card in enumerate(self._cards):
            r, c = divmod(i, cols)
            self.grid.addWidget(card, r, c)


# ====================================================================
#  设置页
# ====================================================================
class SettingsPage(QWidget):
    theme_changed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build()

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        outer.addWidget(self.scroll)
        content = QWidget()
        self.scroll.setWidget(content)
        lay = QVBoxLayout(content)
        lay.setContentsMargins(24, 24, 24, 32)
        lay.setSpacing(0)
        lay.addWidget(make_h1("设置"))
        lay.addWidget(make_sub("配置保存到 QSettings,重启自动生效"))
        lay.addSpacing(20)

        # ---- 下载 ----
        lay.addWidget(self._group_title("下载"))
        self.dl_box = QFrame()
        self.dl_box.setObjectName("groupBox")
        self.dl_box.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        dll = QVBoxLayout(self.dl_box)
        dll.setContentsMargins(0, 0, 0, 0)
        dll.setSpacing(0)
        dll.addWidget(self._row(
            "默认画质",
            Picker(["720P", "1080P", "4K", "最佳"],
                   index=max(0, ["720P", "1080P", "4K", "最佳"].index(SETTINGS.value("quality", "1080P")))),
        ))
        self.spin_conc = QSpinBox()
        self.spin_conc.setRange(1, 16)
        self.spin_conc.setValue(int(SETTINGS.value("concurrency", 4)))
        dll.addWidget(self._row("并发任务数", self.spin_conc))
        self.spin_seg = QSpinBox()
        self.spin_seg.setRange(1, 32)
        self.spin_seg.setValue(int(SETTINGS.value("segments", 8)))
        dll.addWidget(self._row("单任务分片", self.spin_seg))
        save_val = QLabel(str(SETTINGS.value("save_dir", "./downloads")))
        save_row = self._row("保存位置", save_val)
        btn_change = make_secondary("更改")
        btn_change.clicked.connect(self._pick_dir)
        save_row.layout().addWidget(btn_change)
        dll.addWidget(save_row)
        lay.addWidget(self.dl_box)

        # ---- 下载引擎 ----
        lay.addSpacing(18)
        lay.addWidget(self._group_title("下载引擎"))
        eng_box = QFrame()
        eng_box.setObjectName("groupBox")
        eng_box.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        el = QVBoxLayout(eng_box)
        el.setContentsMargins(0, 0, 0, 0)
        el.setSpacing(0)
        aria2_ok = Aria2Client.is_installed()
        el.addWidget(self._engine_row("aria2c", "✓ 已安装" if aria2_ok else "✗ 未安装", "ok" if aria2_ok else "warn"))
        yt_ok = importlib.util.find_spec("yt_dlp") is not None
        el.addWidget(self._engine_row("yt-dlp", "✓ 可用" if yt_ok else "✗ 未安装", "ok" if yt_ok else "warn"))
        ff_ok = shutil.which("ffmpeg") is not None
        el.addWidget(self._engine_row("ffmpeg", "✓ 已安装" if ff_ok else "✗ 未安装", "ok" if ff_ok else "warn"))
        el.addWidget(self._row("优先引擎", Picker(["自动", "aria2", "yt-dlp"], index=0)))
        lay.addWidget(eng_box)

        # ---- 平台适配 ----
        lay.addSpacing(18)
        lay.addWidget(self._group_title("平台适配"))
        pf_box = QFrame()
        pf_box.setObjectName("groupBox")
        pf_box.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        pl = QVBoxLayout(pf_box)
        pl.setContentsMargins(0, 0, 0, 0)
        pl.setSpacing(0)
        pl.addWidget(self._engine_row("红果短剧", "未配置", "off"))
        pl.addWidget(self._engine_row("河马短剧", "未配置", "off"))
        pl.addWidget(self._engine_row("公开视频源", "yt-dlp 内置 · 可用", "ok"))
        lay.addWidget(pf_box)

        # ---- 外观 ----
        lay.addSpacing(18)
        lay.addWidget(self._group_title("外观"))
        ap_box = QFrame()
        ap_box.setObjectName("groupBox")
        ap_box.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        al = QVBoxLayout(ap_box)
        al.setContentsMargins(0, 0, 0, 0)
        al.setSpacing(0)
        self.theme_picker = Picker(["浅色", "深色"],
                                   index=0 if SETTINGS.value("theme", "light") == "light" else 1)
        self.theme_picker.changed.connect(self._on_theme_pick)
        al.addWidget(self._row("主题", self.theme_picker))
        self.tg_anim = Toggle(True)
        al.addWidget(self._row("界面动画", self.tg_anim))
        self.tg_update = Toggle(True)
        al.addWidget(self._row("启动时检查更新", self.tg_update))
        lay.addWidget(ap_box)

        # ---- 关于 ----
        lay.addSpacing(18)
        lay.addWidget(self._group_title("关于"))
        ab_box = QFrame()
        ab_box.setObjectName("groupBox")
        ab_box.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        abl = QVBoxLayout(ab_box)
        abl.setContentsMargins(0, 0, 0, 0)
        abl.setSpacing(0)
        abl.addWidget(self._row("版本", QLabel("0.8.0")))
        abl.addWidget(self._row("许可证", QLabel("仅供个人学习与备份使用"), zh=True))
        note = QLabel("技术栈:PyQt6 · aiohttp · aria2 · yt-dlp · ffmpeg · SQLite\n"
                      "本工具仅供技术研究与个人学习,各平台视频版权归平台与版权方所有。")
        note.setObjectName("cardDesc")
        note.setWordWrap(True)
        note.setContentsMargins(16, 8, 16, 14)
        abl.addWidget(note)
        lay.addWidget(ab_box)
        lay.addStretch(1)

    # ---- 辅助 ----
    def _group_title(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("groupT")
        return lbl

    def _row(self, label, widget, zh=False):
        row = QWidget()
        rl = QHBoxLayout(row)
        rl.setContentsMargins(16, 10, 16, 10)
        rl.setSpacing(12)
        lab = QLabel(label)
        lab.setObjectName("sLabel")
        rl.addWidget(lab)
        rl.addStretch(1)
        if isinstance(widget, QLabel):
            widget.setObjectName("sVal")
            if zh:
                widget.setProperty("class", "zh")
                _repolish(widget)
        rl.addWidget(widget)
        row.setFixedHeight(42)
        return row

    def _engine_row(self, name: str, val: str, st: str):
        row = QWidget()
        rl = QHBoxLayout(row)
        rl.setContentsMargins(16, 10, 16, 10)
        rl.setSpacing(12)
        dot = QLabel()
        dot.setObjectName("engineDot")
        dot.setProperty("st", st)
        dot.setFixedSize(8, 8)
        _repolish(dot)
        rl.addWidget(dot)
        lab = QLabel(name)
        lab.setObjectName("sLabel")
        rl.addWidget(lab)
        rl.addStretch(1)
        v = QLabel(val)
        v.setObjectName("sVal")
        v.setProperty("class", "zh")
        _repolish(v)
        rl.addWidget(v)
        row.setFixedHeight(42)
        return row

    def _pick_dir(self):
        d = QFileDialog.getExistingDirectory(self, "选择保存位置", SETTINGS.value("save_dir", "./downloads"))
        if d:
            SETTINGS.setValue("save_dir", d)

    def _on_theme_pick(self, i: int):
        self.theme_changed.emit("light" if i == 0 else "dark")

    def set_theme(self, mode: str):
        self.theme_picker.set_index(0 if mode == "light" else 1)


# ====================================================================
#  主窗口
# ====================================================================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("短剧下载器")
        self.resize(1240, 800)
        self.mode = SETTINGS.value("theme", "light")

        self.platforms = [HongguoPlatform(), HemaPlatform()]
        self.orchestrator = SearchOrchestrator(self.platforms)
        self.share_resolver = ShareResolver(self.platforms)
        self.task_store = TaskStore()

        self.search_page = SearchPage(self.orchestrator)
        self.link_page = LinkPage(self.share_resolver)
        self.tasks_page = TasksPage(self.task_store)
        self.done_page = DonePage(self.task_store)
        self.settings_page = SettingsPage()

        self.search_page.drama_selected.connect(self._on_drama_selected)
        self.link_page.drama_loaded.connect(self._on_drama_selected)
        self.settings_page.theme_changed.connect(self._set_theme)

        self._build_ui()
        apply_theme(QApplication.instance(), self.mode)
        self._recolor_all()
        self._switch_page(0)
        self.status.showMessage("就绪")

    # ---------------- UI 构建 ----------------
    def _build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        h = QHBoxLayout(root)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)

        # ---- 侧边栏 ----
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        sidebar.setFixedWidth(208)
        sv = QVBoxLayout(sidebar)
        sv.setContentsMargins(0, 0, 0, 12)
        sv.setSpacing(0)

        # 交通灯(装饰)
        traffic = QWidget()
        tl = QHBoxLayout(traffic)
        tl.setContentsMargins(18, 16, 18, 6)
        tl.setSpacing(8)
        for c in ("#FF5F57", "#FEBC2E", "#28C840"):
            dot = QLabel()
            dot.setFixedSize(12, 12)
            dot.setStyleSheet(f"background:{c};border-radius:6px;")
            tl.addWidget(dot)
        tl.addStretch(1)
        sv.addWidget(traffic)

        # 品牌
        brand = QWidget()
        bl = QHBoxLayout(brand)
        bl.setContentsMargins(18, 4, 18, 16)
        bl.setSpacing(9)
        mark = QFrame()
        mark.setObjectName("brandMark")
        mark.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        mark.setFixedSize(26, 26)
        ml = QVBoxLayout(mark)
        ml.setContentsMargins(0, 0, 0, 0)
        ml.setAlignment(Qt.AlignmentFlag.AlignCenter)
        micon = QLabel()
        micon.setPixmap(icon("plus", "#FFFFFF", 14).pixmap(14, 14))
        ml.addWidget(micon)
        bl.addWidget(mark)
        name = QLabel("短剧下载器")
        name.setObjectName("brandName")
        bl.addWidget(name)
        ver = QLabel("0.8.0")
        ver.setObjectName("brandVer")
        bl.addWidget(ver)
        sv.addWidget(brand)

        # 导航
        self.nav_items: list[NavItem] = []
        nav_defs = [
            ("浏览", [
                ("search", "搜索", 0, 0),
                ("link", "链接解析", 0, 1),
            ]),
            ("下载", [
                ("download", "任务队列", 0, 2),
                ("check", "已完成", 0, 3),
            ]),
            ("系统", [
                ("gear", "设置", 0, 4),
            ]),
        ]
        for sec, items in nav_defs:
            sec_lbl = QLabel(sec)
            sec_lbl.setObjectName("navSec")
            sv.addWidget(sec_lbl)
            for ico, text, badge, idx in items:
                item = NavItem(ico, text, badge)
                item.clicked.connect(lambda _, k=idx: self._switch_page(k))
                sv.addWidget(item)
                self.nav_items.append(item)
        sv.addStretch(1)

        # 引擎状态卡
        engine_card = QFrame()
        engine_card.setObjectName("engineCard")
        engine_card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        el = QVBoxLayout(engine_card)
        el.setContentsMargins(11, 10, 11, 10)
        el.setSpacing(3)
        aria2_ok = Aria2Client.is_installed()
        self._engine_rows: list[tuple[QLabel, QLabel]] = []
        for name, val, st in [
            ("aria2c", "1.37.0", "ok" if aria2_ok else "warn"),
            ("yt-dlp", "2025.09", "ok"),
            ("ffmpeg", "7.1", "ok"),
            ("平台适配", "0 / 2", "warn"),
        ]:
            row = QWidget()
            rl = QHBoxLayout(row)
            rl.setContentsMargins(0, 2, 0, 2)
            rl.setSpacing(6)
            dot = QLabel()
            dot.setObjectName("engineDot")
            dot.setProperty("st", st)
            dot.setFixedSize(6, 6)
            _repolish(dot)
            rl.addWidget(dot)
            nm = QLabel(name)
            nm.setObjectName("engineName")
            rl.addWidget(nm)
            rl.addStretch(1)
            v = QLabel(val)
            v.setObjectName("engineVal")
            if name == "平台适配":
                v.setProperty("class", "zh")
                _repolish(v)
            rl.addWidget(v)
            el.addWidget(row)
            self._engine_rows.append((dot, nm))
        sv.addWidget(engine_card)
        h.addWidget(sidebar)

        # ---- 主区 ----
        main = QWidget()
        mv = QVBoxLayout(main)
        mv.setContentsMargins(0, 0, 0, 0)
        mv.setSpacing(0)

        # 顶栏
        topbar = QFrame()
        topbar.setObjectName("topbar")
        topbar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        topbar.setFixedHeight(52)
        tv = QHBoxLayout(topbar)
        tv.setContentsMargins(24, 0, 16, 0)
        tv.setSpacing(12)
        self.lbl_page = QLabel("搜索")
        self.lbl_page.setObjectName("pageTitle")
        tv.addWidget(self.lbl_page)
        tv.addStretch(1)

        # 搜索栏
        self.searchbar = QWidget()
        self.searchbar.setObjectName("searchbar")
        self.searchbar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.searchbar.setFixedHeight(34)
        self.searchbar.setMaximumWidth(320)
        sb = QHBoxLayout(self.searchbar)
        sb.setContentsMargins(11, 0, 11, 0)
        sb.setSpacing(8)
        sic = QLabel()
        sic.setPixmap(icon("search", "#AEAEB2", 15).pixmap(15, 15))
        sb.addWidget(sic)
        self.top_search = QLineEdit()
        self.top_search.setObjectName("topSearch")
        self.top_search.setPlaceholderText("搜索短剧、主演")
        self.top_search.returnPressed.connect(self._on_top_search)
        self.top_search.focusInEvent = self._wrap(self.top_search.focusInEvent, self._searchbar_focus)
        self.top_search.focusOutEvent = self._wrap(self.top_search.focusOutEvent, self._searchbar_focus)
        sb.addWidget(self.top_search, 1)
        tv.addWidget(self.searchbar)

        # 主题切换
        self.btn_theme = QPushButton()
        self.btn_theme.setObjectName("iconBtn")
        self.btn_theme.setFixedSize(28, 28)
        self.btn_theme.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_theme.setToolTip("切换主题")
        self.btn_theme.clicked.connect(lambda: self._set_theme("dark" if self.mode == "light" else "light"))
        tv.addWidget(self.btn_theme)

        # 更多
        self.btn_more = QPushButton()
        self.btn_more.setObjectName("iconBtn")
        self.btn_more.setFixedSize(28, 28)
        self.btn_more.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_more.setToolTip("更多")
        self.btn_more.clicked.connect(self._show_more_menu)
        tv.addWidget(self.btn_more)
        mv.addWidget(topbar)

        # 页面栈
        self.stack = QStackedWidget()
        self.stack.setObjectName("screen")
        self.stack.addWidget(self.search_page)
        self.stack.addWidget(self.link_page)
        self.stack.addWidget(self.tasks_page)
        self.stack.addWidget(self.done_page)
        self.stack.addWidget(self.settings_page)
        mv.addWidget(self.stack, 1)
        h.addWidget(main, 1)

        self.setStatusBar(self.statusBar())
        self.status = self.statusBar()

    def _wrap(self, orig, hook):
        def _h(ev):
            orig(ev)
            hook(ev)
        return _h

    def _searchbar_focus(self, _ev):
        focused = self.top_search.hasFocus()
        self.searchbar.setProperty("focus", "true" if focused else "false")
        _repolish(self.searchbar)

    def _on_top_search(self):
        kw = self.top_search.text().strip()
        if kw:
            self._switch_page(0)
            self.search_page.do_search(kw)

    def _show_more_menu(self):
        m = QMenu(self)
        a_about = QAction("关于", self)
        a_about.triggered.connect(self._show_about)
        a_quit = QAction("退出", self)
        a_quit.triggered.connect(self.close)
        m.addAction(a_about)
        m.addSeparator()
        m.addAction(a_quit)
        m.exec(self.btn_more.mapToGlobal(self.btn_more.rect().bottomLeft()))

    def _show_about(self):
        QMessageBox.about(
            self, "关于",
            "短剧下载器 v0.8.0\n\n"
            "技术栈:PyQt6 · aiohttp · aria2 · yt-dlp · ffmpeg · SQLite\n"
            "仅供技术研究与个人学习,各平台视频版权归平台与版权方所有。",
        )

    # ---------------- 页面切换 ----------------
    def _switch_page(self, idx: int):
        self.stack.setCurrentIndex(idx)
        titles = ["搜索", "链接解析", "任务队列", "已完成", "设置"]
        self.lbl_page.setText(titles[idx])
        self.searchbar.setVisible(idx == 0)
        for i, item in enumerate(self.nav_items):
            item.set_on(i == idx)
        if idx == 2:
            self.tasks_page.refresh()
        if idx == 3:
            self.done_page.refresh()
        # 淡入
        self._fade_in(self.stack.currentWidget())

    def _fade_in(self, w: QWidget):
        from PyQt6.QtWidgets import QGraphicsOpacityEffect
        eff = QGraphicsOpacityEffect(w)
        w.setGraphicsEffect(eff)
        anim = QPropertyAnimation(eff, b"opacity", self)
        anim.setDuration(240)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.finished.connect(lambda: w.setGraphicsEffect(None))
        anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)

    def _on_drama_selected(self, drama, *_):
        # 选中剧后跳到链接页,预填剧名并展开手动输入
        self._switch_page(1)
        if isinstance(drama, dict):
            self.link_page.input_share.setPlainText(drama.get("t", ""))
        elif drama is not None:
            self.link_page.input_share.setPlainText(drama.title)
        if not self.link_page.manual_box.isVisible():
            self.link_page._toggle_manual()

    # ---------------- 主题 ----------------
    def _set_theme(self, mode: str):
        if mode == self.mode:
            return
        self.mode = mode
        SETTINGS.setValue("theme", mode)
        apply_theme(QApplication.instance(), mode)
        self.settings_page.set_theme(mode)
        self._recolor_all()

    def _recolor_all(self):
        # 顶栏图标
        t2 = "#98989D" if self.mode == "dark" else "#6E6E73"
        self.btn_theme.setIcon(icon("sun" if self.mode == "dark" else "moon", t2, 16))
        self.btn_theme.setIconSize(QSize(16, 16))
        self.btn_more.setIcon(icon("dots", t2, 16))
        self.btn_more.setIconSize(QSize(16, 16))


def main():
    app = QApplication([])
    apply_theme(app, SETTINGS.value("theme", "light"))
    w = MainWindow()
    w.show()
    app.exec()


if __name__ == "__main__":
    main()
