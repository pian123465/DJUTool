"""下载 aria2c + ffmpeg 的 Windows 二进制到 assets/bin/。

打包时 PyInstaller 会把这两个 exe 一并打进 .exe,用户双击运行不需要额外装。

用法:
    python tools/setup_binaries.py           # 下载 Windows x64 二进制(默认)
    python tools/setup_binaries.py --all      # 同时下 Windows + Linux(本地开发调试用)

下载源:
    aria2c:  https://github.com/aria2/aria2/releases(官方 release zip)
    ffmpeg:  https://www.gyan.dev/ffmpeg/builds/(release-essentials,只带 ffmpeg.exe,体积小)
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys
import zipfile
from pathlib import Path

import requests


REPO_ROOT = Path(__file__).resolve().parent.parent
TARGET_DIR = REPO_ROOT / "assets" / "bin"

# aria2c 官方 Win64 release(zip 内路径:aria2-1.37.0-win-64bit-build1/aria2c.exe)
ARIA2_VERSION = "1.37.0"
ARIA2_URL = (
    f"https://github.com/aria2/aria2/releases/download/release-{ARIA2_VERSION}/"
    f"aria2-{ARIA2_VERSION}-win-64bit-build1.zip"
)

# ffmpeg Gyan essentials(zip 内路径:ffmpeg-7.1-essentials_build/bin/ffmpeg.exe)
# 用 essentials 版,只带 ffmpeg.exe 没 ffprobe,体积 30MB 左右
FFMPEG_URL = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"


def _download(url: str, dst: Path, chunk: int = 1 << 20) -> None:
    """流式下载,带进度。"""
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        print(f"  ✓ 已存在 {dst.name}({dst.stat().st_size // 1024} KB),跳过")
        return

    print(f"  ↓ 下载 {url}")
    print(f"    → {dst}")
    with requests.get(url, stream=True, timeout=60, allow_redirects=True) as r:
        r.raise_for_status()
        total = int(r.headers.get("Content-Length", 0))
        done = 0
        with dst.open("wb") as f:
            for chunk_data in r.iter_content(chunk_size=chunk):
                f.write(chunk_data)
                done += len(chunk_data)
                if total:
                    pct = done * 100 // total
                    print(f"    {pct:3d}%  {done // 1024} / {total // 1024} KB", end="\r")
        if total:
            print()


def _extract_one(zip_path: Path, member_substring: str, dst: Path) -> None:
    """从 zip 里抽一个匹配的文件。"""
    print(f"  📦 解压 {zip_path.name} → {dst.name}")
    with zipfile.ZipFile(zip_path) as zf:
        for member in zf.namelist():
            if member_substring in member and member.endswith(dst.name):
                with zf.open(member) as src, dst.open("wb") as out:
                    shutil.copyfileobj(src, out)
                dst.chmod(0o755 if os.name != "nt" else 0o777)
                print(f"    ✓ {dst} ({dst.stat().st_size // 1024} KB)")
                return
        raise FileNotFoundError(
            f"在 {zip_path.name} 里找不到包含 {member_substring!r} 且以 {dst.name!r} 结尾的文件"
        )


def fetch_aria2() -> Path:
    """下载 aria2c.exe,返回目标路径。"""
    TARGET_DIR.mkdir(parents=True, exist_ok=True)
    is_win = os.name == "nt"
    dst = TARGET_DIR / ("aria2c.exe" if is_win else "aria2c")
    if dst.exists():
        print(f"  ✓ {dst.name} 已存在,跳过")
        return dst

    zip_path = TARGET_DIR / "_aria2.zip"
    _download(ARIA2_URL, zip_path)
    _extract_one(zip_path, "win-64bit" if is_win else "linux", dst)
    zip_path.unlink(missing_ok=True)
    return dst


def fetch_ffmpeg() -> Path:
    """下载 ffmpeg.exe,返回目标路径。"""
    TARGET_DIR.mkdir(parents=True, exist_ok=True)
    is_win = os.name == "nt"
    dst = TARGET_DIR / ("ffmpeg.exe" if is_win else "ffmpeg")
    if dst.exists():
        print(f"  ✓ {dst.name} 已存在,跳过")
        return dst

    zip_path = TARGET_DIR / "_ffmpeg.zip"
    _download(FFMPEG_URL, zip_path)
    # ffmpeg zip 里通常长这样:ffmpeg-7.1-essentials_build/bin/ffmpeg.exe
    _extract_one(zip_path, "/bin/", dst)
    zip_path.unlink(missing_ok=True)
    return dst


def main() -> int:
    parser = argparse.ArgumentParser(description="下载 aria2c + ffmpeg 二进制到 assets/bin/")
    parser.add_argument("--only-aria2", action="store_true", help="只下 aria2c")
    parser.add_argument("--only-ffmpeg", action="store_true", help="只下 ffmpeg")
    args = parser.parse_args()

    print("=========================================")
    print(" 下载 aria2c + ffmpeg 到 assets/bin/")
    print("=========================================")
    print(f"目标目录: {TARGET_DIR}")
    print(f"当前平台: {os.name} ({sys.platform})")
    print()

    do_aria2 = not args.only_ffmpeg
    do_ffmpeg = not args.only_aria2

    if do_aria2:
        print("▶ aria2c")
        p = fetch_aria2()
        print()
    if do_ffmpeg:
        print("▶ ffmpeg")
        p = fetch_ffmpeg()
        print()

    print("✅ 完成。打包时 PyInstaller 会自动把这俩打进 .exe:")
    print(f"   {list(TARGET_DIR.glob('*'))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())