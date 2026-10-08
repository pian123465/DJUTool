"""管理 aria2c + ffmpeg 二进制,放在 assets/bin/。

默认行为:**本地优先**。如果 assets/bin/ 下已经有对应的二进制,直接跳过;
只有缺失时才下载(给"clone 仓库但漏掉 assets/bin/ "的人用)。

[v0.8] **仓库里不再放 binaries.tar.gz**。GitHub 网页上传单文件上限 25MB、
git push 上限 100MB,75MB 的压缩包两头不讨好,而且实际根本用不上 ——
Actions runner 从 GitHub CDN 下 aria2c + ffmpeg 实测只要 4 秒
(见 CHANGES.md v0.8)。所以现在:仓库只放源码,CI 自己下 + 缓存。

如果你本地想要离线包(不想每次构建都下),把 binaries.tar.gz 丢进 assets/bin/ 即可,
它仍然会被自动解压 —— 该文件已在 .gitignore 里,不会被提交。
设 SHORTDRAMA_KEEP_BUNDLE=1 可以让脚本解压后不删掉它。

用法:
    python -X utf8 tools/setup_binaries.py                # 解压 tar.gz(如有)+ 缺啥下啥
    python -X utf8 tools/setup_binaries.py --force        # 强制重新下载,忽略本地
    python -X utf8 tools/setup_binaries.py --only-aria2   # 只处理 aria2c
    python -X utf8 tools/setup_binaries.py --only-ffmpeg  # 只处理 ffmpeg
    python -X utf8 tools/setup_binaries.py --status       # 只检查本地,不下载

下载源(都基于 GitHub CDN;Windows runner 访问 BtbN/Gyan 经常不稳):
    aria2c : github.com/aria2/aria2/releases(官方 release zip,GitHub CDN 极稳)
    ffmpeg : github.com/BtbN/FFmpeg-Builds(主,GitHub CDN 极稳)
             + www.gyan.dev/ffmpeg/builds(备,URL 偶尔 503)
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys
import tarfile
import time
import zipfile
from pathlib import Path

import requests


# === Windows PowerShell stdout 兼容性 fix ====================================
# Windows runner 默认 PowerShell 7 (pwsh) 的 stdout 是 cp1252 编码,
# 直接 print 中文/emoji 会触发 UnicodeEncodeError 让脚本崩。
# 这里强制把 stdout/stderr 切到 utf-8。Python 3.7+ 都支持 reconfigure。
#
# 注意:
#   - `errors="replace"` 保证遇到极端编码不上的字符也不会崩,只是显示成 ?
#   - 用 try/except 兜底,防止老 Python 或非 CPython 实现出问题
def _fix_io_encoding() -> None:
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream is None:
            continue
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        except Exception:
            # Python < 3.7 / 非 CPython,跳过
            pass


_fix_io_encoding()
# ============================================================================


REPO_ROOT = Path(__file__).resolve().parent.parent
TARGET_DIR = REPO_ROOT / "assets" / "bin"

# 仓库自带的 binaries 压缩包(75MB,GitHub 单文件 100MB 限制以内)
# 启动时检测到就自动解压,然后删掉压缩包(working tree 干净)
BUNDLE_NAME = "binaries.tar.gz"

# aria2c 官方 Win64 release
# zip 内唯一路径:aria2-1.37.0-win-64bit-build1/aria2c.exe
ARIA2_VERSION = "1.37.0"
ARIA2_URL = (
    f"https://github.com/aria2/aria2/releases/download/release-{ARIA2_VERSION}/"
    f"aria2-{ARIA2_VERSION}-win-64bit-build1.zip"
)

# ffmpeg 主源(BtbN GPL-shared,自带 dll,ffmpeg.exe + avcodec 等,体积约 80MB zip)
# 备源(Gyan essentials,只下 ffmpeg.exe 体积小但 URL 偶尔 503)
#
# 用 shared 版是因为:这套 ffmpeg.exe 自己很小(~540KB),主要代码在 avcodec-63.dll(114MB)
# shared 版本跟 static 版本总大小差不多,但 spec 处理多文件本来就行
# [v0.8] 实测(2026-10-08):
#   BtbN  → 200,86MB,GitHub CDN,4 秒下完          ✅ 主力
#   gyan  → 503(站点不稳定,经常挂)                ⚠️ 只是兜底
# 所以主源必须放在 BtbN,并且成功下载后靠 actions/cache 缓存,别每回构建都赌外网。
FFMPEG_URLS = [
    "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl-shared.zip",
    "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip",
]

# [v0.8] ffmpeg shared 版的 dll 名字带主版本号(avcodec-62 / 63 / 64 ...),
# 而下载源是 BtbN 的 **master-latest 滚动包** —— ffmpeg 一升级大版本,写死的名字就全废了
# (轻则 FileNotFoundError,重则 "unknown ffmpeg zip structure" 直接把构建搞挂)。
# 所以这里不再写死任何 dll 名,一律动态扫描 assets/bin/*.dll。


def _maybe_extract_bundle() -> bool:
    """如果 assets/bin/binaries.tar.gz 存在,自动解压到 TARGET_DIR 后删除压缩包。

    返回:是否执行了解压(用于打日志)。
    """
    bundle = TARGET_DIR / BUNDLE_NAME
    if not bundle.exists():
        return False

    print(f"  [PKG] found {BUNDLE_NAME} ({bundle.stat().st_size // 1024 // 1024} MB), extracting...")
    TARGET_DIR.mkdir(parents=True, exist_ok=True)
    try:
        with tarfile.open(bundle, "r:gz") as tf:
            tf.extractall(TARGET_DIR)
    except Exception as e:
        # 解压失败,保留压缩包以便排查
        print(f"  [X] extract failed: {e}")
        raise

    # 解压成功就删压缩包(working tree 干净)。
    # 设 SHORTDRAMA_KEEP_BUNDLE=1 可以保留 —— 本地离线构建时会反复用到它。
    if os.environ.get("SHORTDRAMA_KEEP_BUNDLE") == "1":
        print(f"  [OK] extract done, kept {BUNDLE_NAME} (SHORTDRAMA_KEEP_BUNDLE=1)")
    else:
        bundle.unlink()
        print(f"  [OK] extract done, removed {BUNDLE_NAME}")
    return True


def _existing_dlls() -> list[str]:
    """assets/bin 下现有的 dll 文件名(动态扫描,不写死版本号)。"""
    if not TARGET_DIR.exists():
        return []
    return sorted(p.name for p in TARGET_DIR.glob("*.dll"))


# shared 版(BtbN gpl-shared)的 ffmpeg.exe 本身只有几百 KB —— 代码都在 avcodec-*.dll 里;
# static 版(Gyan essentials)是自包含的,exe 有 70MB+。
# 用这个体积差就能判断"手上这个 exe 是不是掉了 dll 的残缺 shared 版"。
SHARED_FFMPEG_EXE_MAX_KB = 5 * 1024


def _has_avcodec() -> bool:
    """有没有 avcodec-*.dll —— 有就说明是 shared 版 ffmpeg,必须带运行时 dll。"""
    return any(n.lower().startswith("avcodec-") for n in _existing_dlls())


def _is_already_present() -> dict[str, bool]:
    """检查本地二进制。返回 {真实文件名: exists}(供状态打印用)。"""
    is_win = os.name == "nt"
    names = ["aria2c.exe" if is_win else "aria2c",
             "ffmpeg.exe" if is_win else "ffmpeg"]
    if is_win:
        if (TARGET_DIR / "ffprobe.exe").exists():
            names.append("ffprobe.exe")
        names.extend(_existing_dlls())
    return {n: (TARGET_DIR / n).exists() for n in names}


def _download(url: str, dst: Path, chunk: int = 1 << 20, retries: int = 3) -> None:
    """流式下载,带进度 + 重试 + 指数退避。"""
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        print(f"  [OK] {dst.name} exists ({dst.stat().st_size // 1024} KB), skip")
        return

    print(f"  [DL] {url}")
    print(f"    -> {dst}")
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            with requests.get(url, stream=True, timeout=300, allow_redirects=True) as r:
                r.raise_for_status()
                total = int(r.headers.get("Content-Length", 0))
                done = 0
                last_pct = -1
                with dst.open("wb") as f:
                    for chunk_data in r.iter_content(chunk_size=chunk):
                        f.write(chunk_data)
                        done += len(chunk_data)
                        if total:
                            pct = done * 100 // total
                            # [v0.8] 每 5% 打一次就够 —— 之前每 1MB 一行,
                            # 86MB 的包能在 CI 日志里刷出 80 多行,刷屏又难查错。
                            if pct >= last_pct + 5 or pct == 100:
                                last_pct = pct
                                print(f"    [try {attempt}/{retries}] {pct:3d}%  "
                                      f"{done // 1024 // 1024} / {total // 1024 // 1024} MB")
                            if done % (16 << 20) < chunk:
                                f.flush()
                if total and done < total:
                    raise RuntimeError(f"connection closed early: {done}/{total} bytes")
                if total and dst.stat().st_size != total:
                    raise RuntimeError(f"size mismatch: expected {total}, got {dst.stat().st_size}")
                return
        except Exception as e:
            last_err = e
            print(f"\n    [!] attempt {attempt}/{retries} failed: {e}")
            if dst.exists():
                dst.unlink()
            if attempt < retries:
                time.sleep(2 ** attempt)
    raise RuntimeError(f"download failed ({retries} retries): {url} -> {last_err}")


def _extract_member(zip_path: Path, member: str, dst: Path) -> None:
    """从 zip 里抽一个指定成员到 dst。"""
    with zipfile.ZipFile(zip_path) as zf:
        if member not in zf.namelist():
            raise FileNotFoundError(f"{zip_path.name} has no member {member!r}")
        with zf.open(member) as src, dst.open("wb") as out:
            shutil.copyfileobj(src, out)
    dst.chmod(0o755 if os.name != "nt" else 0o777)


def fetch_aria2(force: bool = False) -> Path:
    """获取 aria2c 二进制。force=True 时强制重新下载。"""
    TARGET_DIR.mkdir(parents=True, exist_ok=True)
    is_win = os.name == "nt"
    fname = "aria2c.exe" if is_win else "aria2c"
    dst = TARGET_DIR / fname

    if dst.exists() and not force:
        print(f"  [OK] {fname} exists ({dst.stat().st_size // 1024} KB), skip")
        return dst

    zip_path = TARGET_DIR / "_aria2.zip"
    try:
        if force and zip_path.exists():
            zip_path.unlink()
        _download(ARIA2_URL, zip_path)
        # aria2 zip 内路径:aria2-1.37.0-win-64bit-build1/aria2c.exe
        member_dir = "win-64bit-build1" if is_win else "linux"
        # 用通配找出 .exe(忽略大小写差异、linux 上没有 .exe 后缀)
        with zipfile.ZipFile(zip_path) as zf:
            candidates = [
                m for m in zf.namelist()
                if member_dir in m and (m.endswith("/aria2c.exe") or m.endswith("/aria2c"))
            ]
            if not candidates:
                raise FileNotFoundError(
                    f"{zip_path.name} has no aria2c under {member_dir}\n"
                    f"first 10 members: {zf.namelist()[:10]}"
                )
            target_member = sorted(candidates, key=len)[0]
        print(f"  [PKG] extracting {target_member} -> {fname}")
        _extract_member(zip_path, target_member, dst)
        print(f"    [OK] {dst} ({dst.stat().st_size // 1024} KB)")
    finally:
        zip_path.unlink(missing_ok=True)
    return dst


def fetch_ffmpeg(force: bool = False) -> list[Path]:
    """获取 ffmpeg 二进制及其依赖 dll(shared 版)。force=True 时强制重新下载。

    返回所有放进去的文件路径列表。
    """
    TARGET_DIR.mkdir(parents=True, exist_ok=True)
    is_win = os.name == "nt"
    fname = "ffmpeg.exe" if is_win else "ffmpeg"
    dst = TARGET_DIR / fname

    # 已经有就跳过。[v0.8] 同时确认 shared 版的运行时 dll 也在 ——
    # 光有个 ffmpeg.exe 而 dll 缺失,运行时会报 "找不到 avcodec-62.dll" 之类。
    if dst.exists() and not force:
        dlls = _existing_dlls() if is_win else []
        exe_kb = dst.stat().st_size // 1024
        looks_shared = exe_kb < SHARED_FFMPEG_EXE_MAX_KB   # 小 exe = 代码在 dll 里
        if is_win and looks_shared and not dlls:
            print(f"  [!] ffmpeg.exe exists ({exe_kb} KB) but no runtime dll found "
                  "-> broken shared build, re-downloading")
        else:
            print(f"  [OK] ffmpeg exists ({exe_kb} KB), {1 + len(dlls)} files ready, skip")
            return [TARGET_DIR / n for n in ([fname] + dlls) if (TARGET_DIR / n).exists()]

    zip_path = TARGET_DIR / "_ffmpeg.zip"
    try:
        if force and zip_path.exists():
            zip_path.unlink()
        last_err = None
        for url in FFMPEG_URLS:
            try:
                _download(url, zip_path)
                with zipfile.ZipFile(zip_path) as zf:
                    names = zf.namelist()
                    # BtbN shared: .../bin/ffmpeg.exe + .../bin/avcodec-63.dll 等
                    # Gyan essentials: .../bin/ffmpeg.exe(只 1 个,static,不要 dll)
                    # [v0.8] 完全按 **包内容** 判断结构,不再看 URL 猜:
                    #   - bin/ 里有 avcodec-*.dll  → shared 版,exe + 全部 dll 一起抽
                    #   - 只有 ffmpeg.exe,没有 dll → static 版,只抽 exe
                    # 老代码两处都会栽:
                    #   1) 写死 "bin/avcodec-63.dll" 判断 shared → ffmpeg 升到 8.x
                    #      就失配 → "unknown ffmpeg zip structure" → 构建挂
                    #   2) 靠 URL 里有没有 gyan.dev 判断 static → 换个镜像源就误判
                    members = {n.rsplit("/", 1)[-1].lower(): n for n in names if "/bin/" in n}
                    if is_win:
                        members.update({
                            n.rsplit("/", 1)[-1].lower(): n
                            for n in names
                            if n.lower().endswith((".exe", ".dll")) and n not in members.values()
                            and "shared/bin" in n
                        })
                    ffmpeg_key = "ffmpeg.exe" if is_win else "ffmpeg"
                    if ffmpeg_key not in members:
                        raise FileNotFoundError(
                            f"{zip_path.name} has no bin/{ffmpeg_key}\n"
                            f"first 10 members: {names[:10]}"
                        )

                    wanted: dict[str, str] = {}          # basename -> zip 内路径
                    dlls = [b for b in members if b.endswith(".dll")]
                    if dlls:
                        # shared 版:ffmpeg.exe + ffprobe.exe + 全部运行时 dll
                        for key in ("ffmpeg.exe", "ffprobe.exe") if is_win else ("ffmpeg", "ffprobe"):
                            if key in members:
                                wanted[key] = members[key]
                        for d in dlls:
                            wanted[d] = members[d]
                        print(f"  [PKG] shared build: ffmpeg + ffprobe + {len(dlls)} dll")
                    else:
                        # static 版(gyan essentials 之类):自包含,只要 exe
                        wanted[ffmpeg_key] = members[ffmpeg_key]
                        if is_win and "ffprobe.exe" in members:
                            wanted["ffprobe.exe"] = members["ffprobe.exe"]
                        print("  [PKG] static build: no runtime dll needed")

                    extracted: list[Path] = []
                    for base in sorted(wanted):
                        out = TARGET_DIR / base
                        print(f"  [PKG] extracting {wanted[base]} -> {base}")
                        _extract_member(zip_path, wanted[base], out)
                        extracted.append(out)
                    for out in extracted:
                        print(f"    [OK] {out.name} ({out.stat().st_size // 1024} KB)")
                    return extracted

            except Exception as e:
                last_err = e
                print(f"  [!] this source failed: {e}")
                zip_path.unlink(missing_ok=True)
                # 失败时清掉半成品
                # 清半成品:这次下载出来的 exe + 所有 dll 都清掉
                for f in [fname, "ffprobe.exe"] + (_existing_dlls() if is_win else []):
                    fp = TARGET_DIR / f
                    if fp.exists():
                        fp.unlink()
                continue
        raise RuntimeError(
            f"all ffmpeg sources failed ({len(FFMPEG_URLS)} tried): {last_err}\n"
            "  源码列表:\n" + "\n".join(f"    - {u}" for u in FFMPEG_URLS) +
            "\n  这是外网问题,不是代码问题 —— 直接重新跑一次 Actions 即可"
            "(成功的下载会被 actions/cache 缓存下来,下次不再依赖外网)。"
        )
    finally:
        zip_path.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="manage aria2c + ffmpeg binaries (local-first, download on miss)")
    parser.add_argument("--force", action="store_true", help="force re-download, ignore local")
    parser.add_argument("--only-aria2", action="store_true", help="only handle aria2c")
    parser.add_argument("--only-ffmpeg", action="store_true", help="only handle ffmpeg")
    parser.add_argument("--status", action="store_true", help="only check local binaries, no download")
    args = parser.parse_args()

    print("=========================================")
    print(" check aria2c + ffmpeg binaries")
    print("=========================================")
    print(f"target dir: {TARGET_DIR}")
    print(f"platform:   {os.name} ({sys.platform})")
    print(f"strategy:   {'force-redownload' if args.force else 'local-first, download on miss'}")
    # v0.6:把最终生效的 stdout 编码打进日志。
    # 下次再挂的话,看这一行就知道是编码问题还是别的问题(应该永远是 utf-8;
    # 万一不是,脚本里下面的 print 也全是 ASCII,不会 UnicodeEncodeError)。
    print(f"io encoding: stdout={getattr(sys.stdout, 'encoding', None)} "
          f"stderr={getattr(sys.stderr, 'encoding', None)}")
    print()

    # 先解压仓库自带的 binaries.tar.gz(如存在)
    if not args.force:
        try:
            _maybe_extract_bundle()
        except Exception as e:
            print(f"  [!] extracting bundled binaries.tar.gz failed: {e}")
            print(f"      will try network download (BtbN/Gyan), may be slow or fail")
    print()

    if args.status:
        present = _is_already_present()
        for fname, exists in present.items():
            mark = "[OK]" if exists else "[X]"
            print(f"  {mark} {fname}")
        return 0 if all(present.values()) else 1

    do_aria2 = not args.only_ffmpeg
    do_ffmpeg = not args.only_aria2

    if do_aria2:
        print("> aria2c")
        fetch_aria2(force=args.force)
        print()
    if do_ffmpeg:
        print("> ffmpeg")
        fetch_ffmpeg(force=args.force)
        print()

    print("=========================================")
    print(" status")
    print("=========================================")
    present = _is_already_present()
    for fname, exists in present.items():
        mark = "[OK]" if exists else "[X]"
        size = (TARGET_DIR / fname).stat().st_size // 1024 if exists else 0
        print(f"  {mark} {fname}  ({size} KB)")

    all_ok = all(present[k] for k in [f"aria2c{'.exe' if os.name == 'nt' else ''}",
                                       f"ffmpeg{'.exe' if os.name == 'nt' else ''}"]
                 if k in present)
    if all_ok:
        print("\n[OK] all binaries ready. PyInstaller will pack them into the .exe.")
        return 0
    print("\n[X] some binaries missing, [X] items above need re-download.")
    return 1


if __name__ == "__main__":
    sys.exit(main())