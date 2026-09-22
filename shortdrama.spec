# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec 文件 - 在 Windows 11 上构建 .exe

构建命令:
    pip install pyinstaller
    pyinstaller shortdrama.spec --clean --noconfirm

输出:
    dist/shortdrama-dl.exe  (单文件,自带 Python 运行时)
"""

import os
import sys
from pathlib import Path

block_cipher = None

# 跨平台定位图标(Windows / Linux / macOS 都能找到)
ICON_PATH = os.path.join('assets', 'icon.ico')
ICON_PATH = ICON_PATH if Path(ICON_PATH).exists() else None

# 添加所有第三方库(避免运行时缺包)
EXCLUDES = [
    "tkinter", "matplotlib", "numpy.tests", "pytest",
    "scipy", "pandas", "PIL.ImageQt",
]

# 资源文件
datas = [
    ("shortdrama/plugins", "shortdrama/plugins"),  # 用户签名插件
]

# 隐藏导入(动态加载的模块)
hiddenimports = [
    "shortdrama.core.aria2_client",
    "shortdrama.core.base",
    "shortdrama.core.downloader",
    "shortdrama.core.link_parser",
    "shortdrama.core.orchestrator",
    "shortdrama.core.share_resolver",
    "shortdrama.core.signature",
    "shortdrama.core.task_store",
    "shortdrama.platforms._template",
    "shortdrama.plugins.signatures",
    "shortdrama.apple_style",
    # PyQt6 子模块(防止部分版本 hook 漏抓)
    "PyQt6.QtCore",
    "PyQt6.QtGui",
    "PyQt6.QtWidgets",
    "PyQt6.sip",
    # yt-dlp 异步支持
    "yt_dlp",
    "yt_dlp.extractor",
    "yt_dlp.downloader",
]

a = Analysis(
    ['shortdrama/__main__.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=EXCLUDES,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='shortdrama-dl',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,  # 压缩可执行文件
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,           # GUI 模式(无黑窗口)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=ICON_PATH,
)