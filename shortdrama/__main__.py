"""包入口。

⚠️ 这里的 import 写法直接决定打包后的 exe 能不能起来,别改回相对 import。

背景:PyInstaller 打包时把本文件当作**入口脚本**执行(bundle 里它的名字就叫
`__main__.py`,没有包上下文),此时 `__package__` 是空的。所以

    from .ui import main          # ← 相对 import,运行期直接炸

    ImportError: attempted relative import with no known parent package

诡异之处在于:`python -m shortdrama` 跑得好好的(那个场景 __package__ 正常),
构建也完全通过(PyInstaller 分析阶段能解析相对 import),
**只有打包后的 exe 一双击才崩** —— 报错长这样:

    Unhandled exception in script
    Failed to execute script '__main__' due to unhandled exception:
    ImportError: attempted relative import with no known parent package

所以这里统一用绝对 import:打包后由 PYZ 里的 `shortdrama` 包正常解析。
(ui.py / core/*.py 里的相对 import 不用动 —— 它们是作为 `shortdrama.*`
被导入的,包上下文一直都在。)
"""
import sys

# 本地直接 `python shortdrama/__main__.py` 时, sys.path[0] 是 shortdrama/
# 而不是仓库根,绝对 import 会找不到 shortdrama 包,这里补一下。
# 打包后 sys.frozen 为真,这段自动跳过 —— 冻结导入器负责解析 PYZ 里的包。
if not getattr(sys, "frozen", False):
    import os
    _ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _ROOT not in sys.path:
        sys.path.insert(0, _ROOT)

from shortdrama.ui import main

if __name__ == "__main__":
    main()