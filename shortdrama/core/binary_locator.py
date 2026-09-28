"""二进制路径定位 - 找 aria2c / ffmpeg 的可执行位置。

打包后(单文件 .exe):
    sys._MEIPASS 指向 PyInstaller 解压临时目录
    → bin/aria2c.exe / bin/ffmpeg.exe

源码运行时:
    优先 assets/bin/(本地下载的)
    fallback 到系统 PATH(用户自己装到 PATH 的)

也支持 dev/调试:开发时把二进制放到 assets/bin/ 就直接用,不用污染系统 PATH。
"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path


# 项目根 = shortdrama/core/binary_locator.py → 父目录的父目录的父目录
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
LOCAL_BIN = REPO_ROOT / "assets" / "bin"


def _bundled(name: str) -> Path | None:
    """PyInstaller 打包后的临时目录。"""
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        p = Path(meipass) / "bin" / name
        if p.exists():
            return p
    return None


def _local(name: str) -> Path | None:
    """本地开发:assets/bin/。"""
    p = LOCAL_BIN / name
    if p.exists():
        return p
    return None


def resolve_binary(name: str, *, fallback_to_path: bool = True) -> str | None:
    """按优先级查找二进制:打包临时目录 → 本地 assets/bin → 系统 PATH。

    Args:
        name: 如 "aria2c.exe" / "ffmpeg.exe"(Windows)或 "aria2c" / "ffmpeg"(POSIX)
        fallback_to_path: 找不到本地时是否走 PATH

    Returns:
        完整路径字符串或可执行文件名(给 subprocess 用),
        完全找不到时返回 None。
    """
    is_win = os.name == "nt"
    # 优先:打包后的临时目录
    p = _bundled(name)
    if p:
        return str(p)
    # 次之:本地 assets/bin
    p = _local(name)
    if p:
        return str(p)
    # fallback:系统 PATH
    if fallback_to_path:
        which = shutil.which(name) or shutil.which(name.removesuffix(".exe") if is_win else name)
        if which:
            return which
    return None


def aria2_path() -> str | None:
    """aria2c 可执行路径(.exe 后缀自动按 OS 判别)。"""
    is_win = os.name == "nt"
    for name in (("aria2c.exe", "aria2c") if is_win else ("aria2c", "aria2c.exe")):
        p = resolve_binary(name)
        if p:
            return p
    return None


def ffmpeg_path() -> str | None:
    """ffmpeg 可执行路径(.exe 后缀自动按 OS 判别)。"""
    is_win = os.name == "nt"
    for name in (("ffmpeg.exe", "ffmpeg") if is_win else ("ffmpeg", "ffmpeg.exe")):
        p = resolve_binary(name)
        if p:
            return p
    return None


def is_installed(binary_name: str) -> bool:
    """兼容旧 API:检查二进制是否可用。binary_name 不带 .exe。"""
    is_win = os.name == "nt"
    name = f"{binary_name}.exe" if is_win else binary_name
    return resolve_binary(name) is not None