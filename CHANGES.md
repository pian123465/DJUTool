# v0.8.1 - UI 全面重设计(App Store 风)

> 按视觉稿 `index.html` 把界面整体重做了一遍:配色、布局、交互全部对齐苹果设计语言。

## 改了什么

### 1. 设计 Token 单一来源
- 新增 `shortdrama/tokens.py`:浅色 / 深色两套 token(间距 4pt 栅格、圆角 6/10/14/20、动效 120/200/320ms)
- `apple_style.py` 改为 `build_qss(mode)` 按 token 生成整套 QSS,`apply(app, mode)` 一次注入样式 + 调色板

### 2. 新 UI 结构(与 index.html 对应)
- **侧边栏 208px 毛玻璃**:交通灯装饰、品牌标识、分组导航(浏览/下载/系统)、底部引擎状态卡
- **顶栏 52px**:页面标题 + 搜索框(仅搜索页)+ 主题切换 + 更多菜单
- **5 个页面**:
  - 搜索:分类 Chips + 海报网格(2:3 渐变封面、悬停浮起、加号)
  - 链接解析:拖放区(支持拖入文件/文本)+ 解析结果卡 + 最近解析
  - 任务队列:筛选分段控件 + 任务卡片(状态标签 / 进度条 / 重试 / 删除)+ 存储卡
  - 已完成:按剧聚合的海报网格 + 打开目录
  - 设置:分组列表(下载 / 下载引擎 / 平台适配 / 外观 / 关于)
- **深浅主题切换**:顶栏一键切换,持久化到 QSettings;设置页「外观 → 主题」同步
- **动效**:页面切换淡入、封面悬停浮起(QGraphicsDropShadowEffect)、开关滑块弹簧曲线

### 3. 细节
- 新增 `shortdrama/icons.py`:内嵌 SVG → QIcon 工厂,图标颜色跟随主题与选中态
- 海报封面/缩略图全部 QPainter 手绘(渐变 + 标签 + 中英标题),无图片资源依赖
- 任务队列/已完成页接入 SQLite 任务库真实数据

---

# v0.8 - 去掉 75MB 二进制包,exe 改走 GitHub Release

> **这一版是给"GitHub 上传不了大文件"这个卡点解套的。**
> v0.6/v0.7 修的是崩溃,这一版改的是**分发方式本身**。

---

## 为什么以前传不上去

GitHub 网页上传单文件 **25MB** 上限,而 v0.5~v0.7 的包里带着
`assets/bin/binaries.tar.gz`,**75MB** —— 网页直接拒绝,`git push` 虽然能过
(上限 100MB)但也不该把二进制塞进 git。

然后回头看你那次成功的构建日志,发现一件事:

```
[DL] https://github.com/BtbN/.../ffmpeg-master-latest-win64-gpl-shared.zip
    [try 1/3] 100% 86735 / 86735 KB        <- 86MB,4 秒
[OK] all binaries ready.
```

**Actions runner 自己从 GitHub CDN 下只要 4 秒。** 那个 75MB 的包
解决的是一个不存在的问题,却制造了一个把你卡住的流程问题。

---

## v0.8 改了什么

### 1. 仓库里彻底没有大文件了
- 交付包 **76MB → 426KB / 41 个文件**,网页上传、git push 都毫无压力
- `.gitignore` 恢复忽略 `assets/bin/*.exe` / `*.dll` / `binaries.tar.gz`
- `setup_binaries.py` 仍然支持本地放包(离线构建用),但默认走下载
- 新增 `SHORTDRAMA_KEEP_BUNDLE=1`:解压后保留压缩包,本地反复用

### 2. workflow 加了二进制缓存
```yaml
- name: Cache binaries (aria2c + ffmpeg)
  uses: actions/cache@v4
  with:
    path: assets/bin
    key: win-bin-v3-aria2-1.37.0-ffmpeg-gpl-shared
```
第一次下完存缓存,之后构建**不再依赖外网**(实测主源 BtbN 可用,
备用源 gyan.dev 当前 503,所以更不能指望它)。

### 3. ⭐ exe 改走 GitHub Release(这才是正解)
```
Actions artifact : 90 天过期 + 下载要登录  →  只当构建留档
GitHub Release   : 永久 + 免登录 + 2GB 上限 →  对外分发主渠道
```
workflow 新增 `publish_release` / `release_tag` 两个输入,构建成功后自动
`gh release create/upload`(用 runner 自带的 gh,没引第三方 action)。
tag 默认读仓库根的 `VERSION` 文件;同 tag 重跑是**覆盖**附件,不会堆重复版本。

需要 `permissions: contents: write`(仓库默认只给 read,不写会 403)。

### 4. ⭐ 修掉一个定时炸弹:ffmpeg DLL 写死版本号
```python
# v0.5 ~ v0.7
is_btbn_shared = any("bin/avcodec-63.dll" in n for n in names)
FFMPEG_REQUIRED_DLLS = ("avcodec-63.dll", "swscale-10.dll", ...)
```
下载源是 **master-latest 滚动包**,而 dll 名带 ffmpeg 大版本号。
我拉了 BtbN 最新包的真实目录核对(今天还是 avcodec-63,暂时没事),
但**ffmpeg 一旦发 8.x 就变 avcodec-64 / swscale-11**,
上面两行直接失配 → `unknown ffmpeg zip structure` → 构建挂,而且你完全不知道是谁的锅。

v0.8 改成**纯内容驱动**,不看 URL 也不写死版本号:
- `bin/` 里有 `avcodec-*.dll` → shared 版,exe + **全部 dll** 一起抽
- 只有 exe 没有 dll → static 版,只抽 exe

### 5. 下载细节
- 进度日志每 5% 打一行(之前每 1MB 一行,86MB 能刷 80 多行)
- 断流检测(实际收到的字节 < Content-Length 时明确报错)
- 失败信息列出试过的所有 URL + 明确说明"这是外网问题,重跑即可"
- skip 判定加一层:小 exe(<5MB)+ 零 dll = 残缺的 shared 版,自动重下

---

## 验证

`tools/setup_binaries.py` 离线单元测试(用构造的假 zip,不联网):

| 场景 | 结果 |
|---|---|
| ffmpeg 7.x(avcodec-63,当前线上) | ✅ 10 个文件全解出,二次调用幂等 |
| **ffmpeg 8.x(avcodec-64 / swscale-11)** | ✅ 全解出 —— **老代码在这里必炸** |
| static 版(Gyan,无 dll) | ✅ 只解出 ffmpeg.exe |
| shared 版只有 exe、dll 缺失 | ✅ 自动识别并重下 |
| 状态输出的文件名 | ✅ 全部能 stat(不会 KeyError) |

外加 13 项回归全绿(cp1252 编码模拟 / 冻结入口 / workflow YAML / guard 脚本等),
其中 `check_ascii_prints.py` 对 41 个文件扫描无命中。

---

## 现在的完整流程

```
源码(426KB) → git push → Actions 手动触发 → 自动下载+缓存二进制
            → PyInstaller 出 198MB exe → 自动发到 GitHub Release
            → 用户从 /releases 免登录下载,永久有效
```

详细操作步骤见 **`UPLOAD_GUIDE.md`**。

---

# v0.7(存档)- 修 exe 双击即崩(相对 import)

> v0.6 修的是**构建期**崩溃(UnicodeEncodeError),构建绿了、artifact 也传上去了,
> 但打包出来的 exe **一双击就死**。这一版修的是**运行期**第一个坑。

---

# v0.6(已被 v0.7 取代,保留存档)- 把「cp1252 打印中文崩溃」这一类问题整个封死

> 上一版 v0.5 只修了 `tools/setup_binaries.py` 一个入口。
> v0.6 复盘了 build 日志,发现**同一个坑还有第二个入口(shortdrama.spec)**,
> 而且 v0.5 的部署命令有一个静默失效的写法,可能导致修复根本没进仓库。

---

## 一、日志报错原因(逐行对证)

你给的 `logs_101435673379.zip` 里,失败发生在 `build/6_*.txt` 那一步,
报错原文:

```
2026-10-06T10:18:06Z ##[group]Run python tools/setup_binaries.py
2026-10-06T10:18:06Z Traceback (most recent call last):
2026-10-06T10:18:06Z   File "D:\a\DJUTool\DJUTool\tools\setup_binaries.py", line 197, in <module>
2026-10-06T10:18:06Z     sys.exit(main())
2026-10-06T10:18:06Z   File "D:\a\DJUTool\DJUTool\tools\setup_binaries.py", line 168, in main
2026-10-06T10:18:06Z     print(" 下载 aria2c + ffmpeg 到 assets/bin/")
2026-10-06T10:18:06Z   File "...\Lib\encodings\cp1252.py", line 19, in encode
2026-10-06T10:18:06Z UnicodeEncodeError: 'charmap' codec can't encode characters in position 1-2
2026-10-06T10:18:06Z ##[error]Process completed with exit code 1.
```

**直接原因**:runner 是 `windows-2025-vs2026`(Windows Server 2025),step 默认 shell 是
PowerShell 7,它的 stdout 编码是 **cp1252**。Python 3.11 启动时按环境决定
`sys.stdout.encoding=cp1252`,脚本里第一行 `print(" 下载 aria2c + ffmpeg 到 assets/bin/")`
里的中文没法用 cp1252 表示 → 直接 `UnicodeEncodeError` → 脚本 exit 1 → step 失败 → build 失败。

注意崩溃点在 **`main()` 的第 168 行**,也就是**下载逻辑之前**。所以不是网络、不是
75MB 压缩包、不是权限问题 —— 二进制一个字节都还没动,脚本就死了。

### 关键对证:这份日志跑的是 **v0.5 之前**的代码

| 证据 | 日志里的值 | 你上传的 v0.5 源码 |
|---|---|---|
| `sys.exit(main())` 行号 | 197 | **387** |
| 第 168 行内容 | `print(" 下载 aria2c + ffmpeg ...")` | `_download()` 里的重试日志(纯 ASCII) |
| step 名的中文 | `安装依赖`、`下载 aria2c + ffmpeg` | 已改成 `Install dependencies` 等英文 |
| step env 里有没有 `PYTHONIOENCODING` | **没有**(只有 pythonLocation 等 setup-python 自带的) | workflow job 级有 |

也就是说:仓库 `main` 分支当时跑的还是老版本,v0.5 那三个修复(脚本 reconfigure /
ASCII print / workflow env)一个都没生效。CHANGES.md 里对根因的判断是对的,
但**只覆盖了一个入口**。

---

## 二、v0.5 为什么还有可能再挂一次

### 坑 1:`shortdrama.spec` 里还留着中文 print(构建期同一个坑)

```python
# v0.5 shortdrama.spec:54
print(f"[spec] 将打包以下外部二进制到 bin/: {...}")
```

spec 是 PyInstaller **在构建进程里当 Python 执行的**,它同样是构建期输出。
我实测过(把 stdout 强制成 cp1252、并且模拟 `reconfigure` 不可用):

```
UnicodeEncodeError: 'charmap' codec can't encode characters in position 80-90
```

v0.5 里它只是被 workflow 的 `PYTHONIOENCODING: utf-8` 兜住了 —— 一旦那个 env
丢了(手工改 workflow、换 shell、有人在本地 cmd 里跑 `pyinstaller shortdrama.spec`),
构建就会在**同一个位置、同一个异常**死掉。

### 坑 2:v0.5 的部署命令 `cp -r 短剧下载器-一键打包版/* .` 是无效的

`.github/` 和 `.gitignore` 是**隐藏目录/文件**,bash 的 `*` 不匹配它们。
实测:

```
$ cp -r pkg/* dst/ && ls -a dst
.  ..  main.py            <-- .github 和 .gitignore 根本没进去
$ cp -a pkg/. dst/ && ls -a dst
.  ..  .github  .gitignore  main.py     <-- 这样才对
```

所以:**如果你是照 v0.5 的 `cp -r 短剧下载器-一键打包版/* .` 同步的,
那个带 `PYTHONIOENCODING` 的 workflow 根本没进仓库**,下次 Actions 还是会用老 workflow。
这大概率就是「改了还是同样报错」的原因。

---

## 三、v0.6 做了什么

### 1. `shortdrama.spec` ⭐ 同类崩溃点补掉
- 顶部加 `sys.stdout/stderr.reconfigure(encoding="utf-8", errors="replace")`(spec 自包含,不 import 项目模块)
- 第 54 行 print 改成纯 ASCII:`[spec] packing external binaries into bin/: [...]`

### 2. 新增 `tools/check_ascii_prints.py` + workflow 第一步(护栏)
AST 扫描构建路径上的脚本(`setup_binaries.py` / `build_icon.py` / `analyze_mitm.py` /
`shortdrama.spec`),只要出现 **非 ASCII 的 print 字面量或 argparse help/description 就直接 fail**。
放在 workflow 的 checkout 之后第一步:早失败、报错清楚,而不是等 PyInstaller 跑一半炸。

> 注释和 docstring 里写中文**不受影响**,只有真正被 print 出来的字面量会被拦。

### 3. workflow 三层保险(`-X utf8` 比 env 更硬)
```yaml
env:                                   # 第 1 层:job 级
  PYTHONIOENCODING: utf-8
  PYTHONUTF8: "1"
...
run: |                                 # 第 2 层:每个 step 开头再设一次
  $env:PYTHONIOENCODING = 'utf-8'
  $env:PYTHONUTF8 = '1'
  python -X utf8 tools/setup_binaries.py   # 第 3 层:命令行参数,env 丢了也有效
```
`Build .exe (PyInstaller)` 那步同样换成 `python -X utf8 -m PyInstaller shortdrama.spec ...`
(spec 里有 print,必须有这个开关)。脚本内部自己也 reconfigure(第四层)。

### 4. `tools/setup_binaries.py`
- 头部加了一行**编码诊断输出**,以后再挂,看日志就知道是不是编码问题:
  ```
  io encoding: stdout=utf-8 stderr=utf-8
  ```
- docstring 里的用法改成 `python -X utf8 tools/setup_binaries.py`

### 5. `tools/build_icon.py` / `tools/analyze_mitm.py`
- 同样的 reconfigure + 全部 print 改 ASCII(`✓` U+2713 在 **cp936 里根本没有码位**,
  中文 Windows 的 cmd 跑 `build_icon.py` 会直接崩)
- `analyze_mitm.py` 打到 stdout 的 JSON 报告改用 `ensure_ascii=True`
  (中文变 `\uXXXX`,内容仍是合法 JSON;Windows 上 `> report.json` 重定向到文件时同样安全)

### 6. `shortdrama/core/link_parser.py`
自测块(`python -m shortdrama.core.link_parser`)会 print 中文测试数据,加 reconfigure + `→` 改 `->`。

### 7. `build.bat` / `build.sh`
所有 python 调用加 `-X utf8`;`pyinstaller xxx.spec` 换成 `python -X utf8 -m PyInstaller xxx.spec`
(控制台脚本没法直接传 `-X`)。

---

## 四、验证(我这边实测过的)

用 `os.name='nt'` + stdout/stderr 强制 cp1252 模拟 runner,两种模式各跑一遍:

| 测试 | v0.5 | v0.6 |
|---|---|---|
| `setup_binaries.py` 常规模式 | exit 0 | exit 0(日志出现 `io encoding: stdout=utf-8`) |
| `setup_binaries.py` 最坏模式(stdout **无法** reconfigure) | exit 0 | **exit 0** |
| `shortdrama.spec` 常规模式 | ✅ | exit 0,10 个二进制全收集到 |
| `shortdrama.spec` 最坏模式 | ❌ **UnicodeEncodeError** | **exit 0** |
| `analyze_mitm.py --help` | ❌ cp1252 下 help 是中文 | exit 0 |
| `build_icon.py` 错误分支 | ❌ `✓` 在 cp936 无码位 | 无编码崩溃 |
| `check_ascii_prints.py` | (不存在)12 处命中 | **0 处,exit 0** |

另外:所有 `.py` + spec 的 `ast.parse` 全通过,workflow YAML 用 js-yaml 解析通过,
`binaries.tar.gz` 内 10 个文件齐全,`.gitignore` 没有误伤 `assets/bin/binaries.tar.gz`。

---

## 五、你该怎么做(注意这一步以前写错过)

```bash
cd path/to/pian123465-DJUTool

# 1) 覆盖 —— 一定要用 pkg/. ,不能用 pkg/*
#    (pkg/* 不含 .github/ 和 .gitignore,workflow 修不到 = 白改)
cp -a 短剧下载器-一键打包版/. .

# 2) 确认 75MB 压缩包没被 .gitignore 挡掉(应该什么都不输出)
git check-ignore -v assets/bin/binaries.tar.gz

# 3) 确认 workflow 真的换成了新的
grep -n "PYTHONIOENCODING" .github/workflows/build-windows.yml

# 4) 提交推送(网页 Upload files 挡 75MB,必须走 git 命令行)
git add -A
git commit -m "v0.6: kill cp1252 UnicodeEncodeError for the whole build path"
git push
```

已经推过 75MB `binaries.tar.gz` 的话,这次**只需要推文本文件**
(用附带的 `shortdrama-v0.6-hotfix-files.zip`,解压到仓库根目录覆盖即可,不用再推 75MB)。

推完去 Actions 手动触发,正常应该是:

| step | 预期 |
|---|---|
| Guard - no non-ASCII print in build scripts | ✅ 一秒过 |
| Extract and check binaries | ✅ `[OK] all binaries ready` |
| Build .exe (PyInstaller) | ✅ 3-8 分钟 |
| Upload artifact | ✅ 拿到 `shortdrama-dl-windows` |

**万一 `Extract and check binaries` 还是挂**:先看那一步日志里的
`io encoding: stdout=xxx` 这一行。`utf-8` 却还报 UnicodeEncodeError,
说明有别的东西在改编码,把那行日志发我;不是 `utf-8` 就是环境被改了,
`python -X utf8` 会直接无视它。

---

## 六、v0.6 改动文件清单

| 文件 | 改动 |
|---|---|
| `shortdrama.spec` ⭐ | 中文 print → ASCII + 顶部 reconfigure |
| `tools/check_ascii_prints.py` ⭐ 新增 | AST 护栏,workflow 第一步执行 |
| `.github/workflows/build-windows.yml` ⭐ | 加护栏 step;所有 python 调用 `-X utf8`;step 级 env;显式 `shell: pwsh` |
| `tools/setup_binaries.py` | 加编码诊断输出;用法注释改 `-X utf8` |
| `tools/build_icon.py` | reconfigure + 4 处 print ASCII 化 |
| `tools/analyze_mitm.py` | reconfigure + print/help ASCII 化 + stdout 报告 `ensure_ascii=True` |
| `shortdrama/core/link_parser.py` | 自测块 reconfigure + `→` → `->` |
| `build.bat` / `build.sh` | python 调用加 `-X utf8`,echo/注释 ASCII 化 |
| `shortdrama/__main__.py` ⭐ v0.7 | 相对 import → 绝对 import(修 exe 双击即崩) |
| `shortdrama.spec` | v0.7 hiddenimports 补 `shortdrama.ui` |

体积/时间:仓库 75 MB(不变,`binaries.tar.gz` 本次没动),workflow 3-8 分钟,
最终 exe ~200 MB(不变)。

---

# v0.7 - exe 双击即崩:`attempted relative import with no known parent package`

## 症状

```
Unhandled exception in script
Failed to execute script '__main__' due to unhandled exception:
ImportError: attempted relative import with no known parent package
  <most recent call last>
  main_.py, line 2, in <module>
or: attempted relative import with no known parent package
```

## 原因

`shortdrama/__main__.py` 第 2 行是**相对 import**:

```python
from .ui import main
```

PyInstaller 打包时把这个文件当作**入口脚本**执行(bundle 里它的名字就叫
`__main__.py`,不是 `shortdrama.__main__`),**没有包上下文**,
所以 `__package__` 是空的,运行期一执行这行就 ImportError。

阴险的地方在于它**三重都能骗过去**:

| 场景 | 结果 | 为什么骗过去 |
|---|---|---|
| `python -m shortdrama` 本地开发 | ✅ 正常 | 这个场景 `__package__='shortdrama'` |
| `pyinstaller` 构建 | ✅ 通过 | **分析阶段**能解析相对 import,模块全收进 PYZ |
| exe 双击运行 | ❌ 崩 | 只有运行期才丢包上下文 |

## 修复

`shortdrama/__main__.py` 改成**绝对 import**(`from shortdrama.ui import main`),
非冻结环境下补一段 `sys.path` 兜底,让 `python shortdrama/__main__.py` 直跑也能用。
`ui.py` / `core/*.py` 里的相对 import **不用动** —— 它们是作为 `shortdrama.*`
被导入的,包上下文一直都在。

`shortdrama.spec` 的 hiddenimports 里补一行 `shortdrama.ui`,显式声明这个依赖。

## 验证

用 zipapp 精确模拟冻结后的 PYZ 环境(入口在归档根 + 包在归档内):

| | 旧版入口 | v0.7 入口 |
|---|---|---|
| zipapp 启动 | ❌ `ImportError: attempted relative import...` | ✅ ui 导入成功,main() 跑完 |

另外顺手审计了另外两个高频运行时雷点,**都没问题**:
- `binary_locator.py` 找二进制走 `sys._MEIPASS/bin/`,和 spec 里 `bin/` 的目标路径对得上 ✅
- 下载目录 `./downloads`、数据库 `./shortdrama_tasks.db` 都基于 cwd(用户启动目录),
  不是 `__file__`,重启不丢 ✅

## 注意

v0.7 只改了 `shortdrama/__main__.py` + `shortdrama.spec` 两个**文本文件**,
`assets/bin/binaries.tar.gz` 没动 —— 如果你还没推 workflow + tar.gz,
这次一起推就行,还是用 hotfix zip(不重复推 75MB)。
