"""内嵌 SVG 图标 → QIcon 工厂。

与 index.html 同一套 feather 风格线性图标,`currentColor` 在渲染前替换为目标色,
保证深浅主题下图标颜色跟随文本层级。
"""

from __future__ import annotations

from functools import lru_cache

from PyQt6.QtCore import QByteArray, Qt
from PyQt6.QtGui import QColor, QIcon, QImage, QPixmap

# feather 风格 24x24 线性图标(与参考稿 index.html 完全同源)
_SVG: dict[str, str] = {
    "search": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        'stroke="%COLOR%" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>'
    ),
    "link": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        'stroke="%COLOR%" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M10 13a5 5 0 0 0 7.5.5l3-3a5 5 0 0 0-7-7l-1.7 1.7"/>'
        '<path d="M14 11a5 5 0 0 0-7.5-.5l-3 3a5 5 0 0 0 7 7l1.7-1.7"/></svg>'
    ),
    "download": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        'stroke="%COLOR%" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M12 3v12"/><path d="m7 11 5 5 5-5"/><path d="M4 20h16"/></svg>'
    ),
    "check": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        'stroke="%COLOR%" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '<path d="m4 12.5 5 5L20 6.5"/></svg>'
    ),
    "gear": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        'stroke="%COLOR%" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '<circle cx="12" cy="12" r="3"/>'
        '<path d="M19.4 15a1.6 1.6 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1'
        'a1.6 1.6 0 0 0-2.7 1.1V21a2 2 0 1 1-4 0v-.1A1.6 1.6 0 0 0 7.5 19.4l-.1.1'
        'a2 2 0 1 1-2.8-2.8l.1-.1A1.6 1.6 0 0 0 4.6 15H4a2 2 0 1 1 0-4h.1'
        'A1.6 1.6 0 0 0 5.6 8.5l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1A1.6 1.6 0 0 0 11 4.6V4'
        'a2 2 0 1 1 4 0v.1a1.6 1.6 0 0 0 2.5 1.5l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1'
        'a1.6 1.6 0 0 0 1.1 2.7H21a2 2 0 1 1 0 4h-.1a1.6 1.6 0 0 0-1.5 1z"/></svg>'
    ),
    "moon": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        'stroke="%COLOR%" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/></svg>'
    ),
    "sun": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        'stroke="%COLOR%" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4'
        'M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>'
    ),
    "plus": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        'stroke="%COLOR%" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M12 5v14M5 12h14"/></svg>'
    ),
    "play": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="%COLOR%">'
        '<path d="M7 4.5v15l13-7.5z"/></svg>'
    ),
    "clipboard": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        'stroke="%COLOR%" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M12 3v12"/><path d="m7.5 10.5 4.5 4.5 4.5-4.5"/><path d="M4 20h16"/></svg>'
    ),
    "pause": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        'stroke="%COLOR%" stroke-width="2" stroke-linecap="round">'
        '<path d="M9 6v12M15 6v12"/></svg>'
    ),
    "trash": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        'stroke="%COLOR%" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M3 6h18M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2M19 6l-1 14a2 2 0 0 1-2 2H8'
        'a2 2 0 0 1-2-2L5 6"/></svg>'
    ),
    "folder": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        'stroke="%COLOR%" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M4 4h6l2 3h8a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2z"/>'
        '</svg>'
    ),
    "refresh": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        'stroke="%COLOR%" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M21 12a9 9 0 1 1-2.6-6.4"/><path d="M21 3v6h-6"/></svg>'
    ),
    "close": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        'stroke="%COLOR%" stroke-width="2" stroke-linecap="round">'
        '<path d="M18 6 6 18M6 6l12 12"/></svg>'
    ),
    "dots": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="%COLOR%">'
        '<circle cx="12" cy="5" r="1.6"/><circle cx="12" cy="12" r="1.6"/>'
        '<circle cx="12" cy="19" r="1.6"/></svg>'
    ),
}


@lru_cache(maxsize=256)
def _render(name: str, color: str, px: int = 22) -> QPixmap:
    raw = _SVG.get(name, _SVG["search"]).replace("%COLOR%", color)
    img = QImage.fromData(QByteArray(raw.encode("utf-8")), "svg")
    if img.isNull():
        img = QImage(px, px, QImage.Format.Format_ARGB32)
        img.fill(Qt.GlobalColor.transparent)
    pix = QPixmap.fromImage(img)
    if pix.width() != px:
        pix = pix.scaled(
            px, px,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
    return pix


def icon(name: str, color: str = "#1D1D1F", px: int = 22) -> QIcon:
    """按颜色渲染图标。color 传 hex(如 '#007AFF')或 'white'。"""
    q = QColor(color)
    return QIcon(_render(name, q.name(), px))
