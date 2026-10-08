"""设计 Token — 与 index.html 视觉稿一一对应。

单一定义深浅两套取值,`Tokens.for_mode()` 返回 dict,
`apply(app, mode)` 一次性注入 QSS 与 QPalette。
"""

from __future__ import annotations

from typing import Any

# ============================================================
#  间距 / 圆角 / 动效(两套主题共用)
# ============================================================
SP = {"sp1": 4, "sp2": 8, "sp3": 12, "sp4": 16, "sp6": 24, "sp10": 40}
RADIUS = {"r_sm": 6, "r_md": 10, "r_lg": 14, "r_xl": 20, "r_full": 999}
EASE_OUT = "cubic-bezier(.22,1,.36,1)"   # 快出慢收
EASE_SPRING = "cubic-bezier(.34,1.56,.64,1)"  # 过冲一点,有物理感

# ============================================================
#  两套主题值
# ============================================================
_LIGHT = {
    "desk": "#E4E4E9",           # 窗口外桌面
    "win_bg": "#F5F5F7",         # 窗口底色
    "sidebar": "rgba(238,238,241,.72)",   # 毛玻璃(Windows DWM 合成)
    "sidebar_line": "rgba(0,0,0,.08)",
    "content": "#FFFFFF",        # 主区
    "card": "#FFFFFF",           # 卡片
    "card_hover": "#FCFCFD",
    "grouped": "#F5F5F7",        # 分组底色
    "sep": "rgba(0,0,0,.09)",
    "sep_soft": "rgba(0,0,0,.055)",

    "text1": "#1D1D1F",
    "text2": "#6E6E73",
    "text3": "#AEAEB2",
    "text_inv": "#FFFFFF",

    "accent": "#007AFF",
    "accent_hover": "#006FE6",
    "accent_soft": "rgba(0,122,255,.10)",
    "green": "#34C759",
    "orange": "#FF9500",
    "red": "#FF3B30",
    "purple": "#AF52DE",

    "field": "rgba(0,0,0,.045)",      # 输入底 / 分段底
    "field_line": "rgba(0,0,0,.10)",
    "hover_fill": "rgba(0,0,0,.05)",
    "press_fill": "rgba(0,0,0,.085)",

    "sh1": "0 1px 2px rgba(0,0,0,.05), 0 0 0 .5px rgba(0,0,0,.045)",
    "sh2": "0 4px 14px -2px rgba(0,0,0,.10), 0 0 0 .5px rgba(0,0,0,.05)",
    "sh3": "0 18px 44px -10px rgba(0,0,0,.26), 0 0 0 .5px rgba(0,0,0,.08)",
    "sh_win": "0 42px 90px -24px rgba(0,0,0,.40), 0 0 0 .5px rgba(0,0,0,.10)",
}

_DARK = {
    "desk": "#0F0F11",
    "win_bg": "#1C1C1E",
    "sidebar": "rgba(40,40,43,.66)",
    "sidebar_line": "rgba(255,255,255,.09)",
    "content": "#1C1C1E",
    "card": "#2C2C2E",
    "card_hover": "#333336",
    "grouped": "#2C2C2E",
    "sep": "rgba(255,255,255,.11)",
    "sep_soft": "rgba(255,255,255,.06)",

    "text1": "#F5F5F7",
    "text2": "#98989D",
    "text3": "#6C6C70",
    "text_inv": "#FFFFFF",

    "accent": "#0A84FF",
    "accent_hover": "#3D9BFF",
    "accent_soft": "rgba(10,132,255,.18)",
    "green": "#32D74B",
    "orange": "#FF9F0A",
    "red": "#FF453A",
    "purple": "#BF5AF2",

    "field": "rgba(255,255,255,.07)",
    "field_line": "rgba(255,255,255,.11)",
    "hover_fill": "rgba(255,255,255,.07)",
    "press_fill": "rgba(255,255,255,.11)",

    "sh1": "0 1px 2px rgba(0,0,0,.30)",
    "sh2": "0 4px 14px -2px rgba(0,0,0,.40)",
    "sh3": "0 18px 44px -10px rgba(0,0,0,.60)",
    "sh_win": "0 42px 90px -24px rgba(0,0,0,.75), 0 0 0 .5px rgba(255,255,255,.09)",
}

_FONTS = (
    '"Segoe UI Variable Display", "Segoe UI", -apple-system, '
    '"Helvetica Neue", "PingFang SC", "Microsoft YaHei", Arial, sans-serif'
)
_MONO = '"SF Mono", "JetBrains Mono", ui-monospace, Menlo, Consolas, monospace'


class Tokens:
    """设计 token 访问入口。"""

    @staticmethod
    def for_mode(mode: str) -> dict[str, Any]:
        base = _LIGHT if mode == "light" else _DARK
        return {
            **SP,
            **RADIUS,
            **base,
            "font": _FONTS,
            "mono": _MONO,
            "ease_out": EASE_OUT,
            "ease_spring": EASE_SPRING,
            "mode": mode,
        }

    @staticmethod
    def qss(mode: str = "light") -> str:
        """由 token 生成完整 QSS(本文件只做占位,真正实现在 apple_style.py)。"""
        from .apple_style import build_qss  # noqa: PLC0415
        return build_qss(mode)


# 便捷引用(程序里直接写颜色)
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
