"""把 SVG 渲染成多尺寸 ICO。

需要:ImageMagick (convert) 或 Inkscape 已安装,本脚本会优先用 convert。

用法:
    python tools/build_icon.py
"""
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).parent.parent
ASSETS = HERE / "assets"
SVG = ASSETS / "icon.svg"
ICO = ASSETS / "icon.ico"

SIZES = [16, 24, 32, 48, 64, 128, 256]


def render_via_convert(svg: Path) -> list[Path]:
    """用 ImageMagick 把 SVG 转成多尺寸 PNG。"""
    out = []
    for sz in SIZES:
        p = ASSETS / f"icon-{sz}.png"
        subprocess.run([
            "convert", "-background", "none", "-density", "384",
            str(svg), "-resize", f"{sz}x{sz}", str(p),
        ], check=True)
        out.append(p)
    return out


def pack_ico(pngs: list[Path], ico: Path):
    """用 ImageMagick 把多张 PNG 打包成 ICO。"""
    subprocess.run(["convert", *[str(p) for p in pngs], str(ico)], check=True)


def render_via_pillow(svg: Path) -> list[Path]:
    """用 cairosvg + PIL 转 PNG,做 fallback。"""
    try:
        import cairosvg
        from io import BytesIO
        from PIL import Image
    except ImportError:
        print("需要 cairosvg + Pillow", file=sys.stderr)
        raise
    raw = svg.read_bytes()
    out = []
    for sz in SIZES:
        png_bytes = cairosvg.svg2png(bytestring=raw, output_width=sz, output_height=sz)
        p = ASSETS / f"icon-{sz}.png"
        p.write_bytes(png_bytes)
        out.append(p)
    return out


def main():
    if not SVG.exists():
        print(f"找不到 {SVG}", file=sys.stderr)
        sys.exit(1)

    # 优先 ImageMagick
    try:
        pngs = render_via_convert(SVG)
    except (FileNotFoundError, subprocess.CalledProcessError):
        print("ImageMagick 失败,试 cairosvg ...")
        pngs = render_via_pillow(SVG)

    pack_ico(pngs, ICO)
    print(f"✓ {ICO} ({ICO.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()