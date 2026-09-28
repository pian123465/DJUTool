"""下载 aria2c + ffmpeg 的 Windows 二进制到 assets/bin/。

打包时 PyInstaller 会把这两个 exe 一并打进 .exe,用户双击运行不需要额外装。

用法:
    python tools/setup_binaries.py                # 下载 Windows x64 二进制(默认)
    python tools/setup_binaries.py --only-aria2    # 只下 aria2c
    python tools/setup_binaries.py --only-ffmpeg   # 只下 ffmpeg

下载源(都基于 GitHub CDN 或稳定 mirror):
    aria2c: github.com/aria2/aria2/releases(官方 release zip)
    ffmpeg: github.com/BtbN/FFmpeg-Builds(主) + gyan.dev(备)
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys
import time
import zipfile
from pathlib import Path

import requests


REPO_ROOT = Path(__file__).resolve().parent.parent
TARGET_DIR = REPO_ROOT / "assets" / "bin"

# aria2c 官方 Win64 release
# zip 内唯一路径:aria2-1.37.0-win-64bit-build1/aria2c.exe
ARIA2_VERSION = "1.37.0"
ARIA2_URL = (
    f"https://github.com/aria2/aria2/releases/download/release-{ARIA2_VERSION}/"
    f"aria2-{ARIA2_VERSION}-win-64bit-build1.zip"
)

# ffmpeg 主源(BtbN,GitHub CDN 极稳)+ 备用(Gyan,URL 偶尔变但体积小)
# 两种 zip 都有 .../bin/ffmpeg.exe
FFMPEG_URLS = [
    "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip",
    "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip",
]


def _download(url: str, dst: Path, chunk: int = 1 << 20, retries: int = 3) -> None:
    """流式下载,带进度 + 重试 + 指数退避。"""
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        print(f"  ✓ 已存在 {dst.name}({dst.stat().st_size // 1024} KB),跳过")
        return

    print(f"  ↓ 下载 {url}")
    print(f"    → {dst}")
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            with requests.get(url, stream=True, timeout=120, allow_redirects=True) as r:
                r.raise_for_status()
                total = int(r.headers.get("Content-Length", 0))
                done = 0
                with dst.open("wb") as f:
                    for chunk_data in r.iter_content(chunk_size=chunk):
                        f.write(chunk_data)
                        done += len(chunk_data)
                        if total:
                            pct = done * 100 // total
                            print(f"    [尝试 {attempt}/{retries}] {pct:3d}%  {done // 1024} / {total // 1024} KB", end="\r")
                if total:
                    print()
                if total and dst.stat().st_size != total:
                    raise RuntimeError(f"下载大小不匹配:期望 {total},实际 {dst.stat().st_size}")
                return
        except Exception as e:
            last_err = e
            print(f"\n    ⚠️  尝试 {attempt}/{retries} 失败: {e}")
            if dst.exists():
                dst.unlink()
            if attempt < retries:
                time.sleep(2 ** attempt)
    raise RuntimeError(f"下载失败({retries} 次重试): {url} → {last_err}")


def _extract_one(zip_path: Path, *, member_dir: str, filename: str, dst: Path) -> None:
    """从 zip 里抽一个匹配的文件(member_dir 是目录子串,filename 是文件名)。

    匹配规则:成员路径必须以 member_dir 结尾的目录段 + filename 开头
    防止匹配到错误路径(比如 changelog 里出现文件名)。
    """
    print(f"  📦 解压 {zip_path.name} → {dst.name}")
    matches: list[str] = []
    with zipfile.ZipFile(zip_path) as zf:
        for member in zf.namelist():
            # 匹配:<dir>/<filename> 或 <dir>/<filename>
            # member_dir 用 '/' 分隔确保是完整目录段
            parts = member.split("/")
            if filename in parts and member_dir in "/".join(parts):
                matches.append(member)
        if not matches:
            raise FileNotFoundError(
                f"在 {zip_path.name} 里找不到 {member_dir!r} 下的 {filename!r}\n"
                f"zip 内前 10 个成员: {zf.namelist()[:10]}"
            )
        # 取最短路径(优先顶层 bin 目录下的文件)
        matches.sort(key=len)
        target_member = matches[0]
        with zf.open(target_member) as src, dst.open("wb") as out:
            shutil.copyfileobj(src, out)
    dst.chmod(0o755 if os.name != "nt" else 0o777)
    print(f"    ✓ {dst} ({dst.stat().st_size // 1024} KB)")


def fetch_aria2() -> Path:
    """下载 aria2c.exe,返回目标路径。"""
    TARGET_DIR.mkdir(parents=True, exist_ok=True)
    is_win = os.name == "nt"
    dst = TARGET_DIR / ("aria2c.exe" if is_win else "aria2c")
    if dst.exists():
        print(f"  ✓ {dst.name} 已存在,跳过")
        return dst

    zip_path = TARGET_DIR / "_aria2.zip"
    try:
        _download(ARIA2_URL, zip_path)
        # aria2 zip 内路径:aria2-1.37.0-win-64bit-build1/aria2c.exe
        member_dir = "win-64bit-build1" if is_win else "linux"
        _extract_one(zip_path, member_dir=member_dir, filename="aria2c", dst=dst)
    finally:
        zip_path.unlink(missing_ok=True)
    return dst


def fetch_ffmpeg() -> Path:
    """下载 ffmpeg.exe,多源 fallback(BtbN → Gyan)。"""
    TARGET_DIR.mkdir(parents=True, exist_ok=True)
    is_win = os.name == "nt"
    dst = TARGET_DIR / ("ffmpeg.exe" if is_win else "ffmpeg")
    if dst.exists():
        print(f"  ✓ {dst.name} 已存在,跳过")
        return dst

    zip_path = TARGET_DIR / "_ffmpeg.zip"
    last_err = None
    for url in FFMPEG_URLS:
        try:
            _download(url, zip_path)
            # BtbN: ffmpeg-master-latest-win64-gpl/bin/ffmpeg.exe
            # Gyan: ffmpeg-7.1-essentials_build/bin/ffmpeg.exe
            _extract_one(zip_path, member_dir="/bin/", filename="ffmpeg.exe", dst=dst)
            zip_path.unlink(missing_ok=True)
            return dst
        except Exception as e:
            last_err = e
            print(f"  ⚠️  此源失败: {e}")
            zip_path.unlink(missing_ok=True)
            if dst.exists():
                dst.unlink()
            continue
    raise RuntimeError(f"所有 ffmpeg 源都失败: {last_err}")


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
        fetch_aria2()
        print()
    if do_ffmpeg:
        print("▶ ffmpeg")
        fetch_ffmpeg()
        print()

    if not TARGET_DIR.exists():
        print("⚠️ 没有任何文件被下载")
        return 1

    print("✅ 完成。打包时 PyInstaller 会自动把这俩打进 .exe:")
    files = sorted(p.name for p in TARGET_DIR.iterdir() if not p.name.startswith("_"))
    print(f"   {files}")
    return 0


if __name__ == "__main__":
    sys.exit(main())