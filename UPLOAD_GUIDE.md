# 上传 & 打包 EXE 完整指南(v0.8)

一句话:**仓库里只放源码(426KB),exe 由 Actions 构建后自动发到 GitHub Release。**
全程不需要上传任何超过 25MB 的东西。

---

## 0. 先搞明白 GitHub 的三条线

| 通道 | 单文件上限 | 要登录吗 | 永久吗 | 用途 |
|---|---|---|---|---|
| 网页上传文件(拖到 Code 页面) | **25 MB** | 是 | 永久 | ⚠️ 就是卡住你的那个 |
| `git push` | **100 MB**(超了直接拒绝) | 是 | 永久 | 能传大文件,但没必要 |
| **GitHub Release 附件** | **2 GB** | **下载方免登录** | **永久** | ✅ exe 就走这条 |
| Actions artifact | 10 GB | 要登录 | ❌ **90 天过期** | 只当构建留档 |

以前那个 `binaries.tar.gz` 有 **75MB**,网页上传直接被拒 —— 这就是你传不上去的原因。
v0.8 把它从仓库里彻底拿掉了。

---

## 1. 一次性:把源码推进仓库

解压你拿到的包,里面有 `短剧下载器-一键打包版/` 目录(426KB,41 个文件)。

### 方式 A:git 命令行(推荐)

```bash
cd path/to/pian123465-DJUTool

# 关键:用 "目录/." 而不是 "目录/*"
# 前者会把 .github/ 和 .gitignore 这种隐藏文件一起带过去,后者不会
cp -a 短剧下载器-一键打包版/. .

git add -A
git commit -m "v0.8: source-only repo + Release publishing"
git push
```

### 方式 B:网页上传(现在也行了,因为没有大文件)

1. 打开仓库 → **Code** → **uploading files** → 把你包里**全部**文件拖进去
2. ⚠️ **`.github` 是隐藏目录**,网页拖拽**不会**自动带上它。
   必须单独操作一次:先进 **Add file → Create new file**,路径填
   `.github/workflows/build-windows.yml`,把内容粘进去再 Commit。
   或者干脆用方式 A。
3. Commit 之后应该看到 41 个文件、总大小 400KB 左右

**验证一下大文件确实没了:**

```bash
find . -type f -size +20M          # 应该什么都不输出
ls -la assets/bin/                 # 只剩 .gitkeep
```

---

## 2. 触发构建

1. 仓库 → 上方 **Actions** 标签
2. 左侧选 **Build Windows .exe**
3. 右侧 **Run workflow**,两个输入项:

| 输入 | 建议 |
|---|---|
| `publish_release` | **勾上**(构建完自动发 Release,exe 就有永久下载地址了) |
| `release_tag` | **留空** —— 自动读仓库根目录的 `VERSION` 文件 |

4. 等 **3~8 分钟**,绿色对勾就完成了

---

## 3. exe 去哪拿

### 主渠道:GitHub Release(推荐给用户)

```
https://github.com/pian123465/DJUTool/releases
```

- **任何人点链接直接下载,不需要登录**
- **永久保存**,不会像 Actions artifact 那样 90 天后消失
- 2GB 上限,你那个 198MB 的 exe 随便放
- 每次发布/重跑都会自动刷新对应版本的附件

### 备用:Actions artifact(当次构建留档用)

构建页往下滚,Artifacts 区域点 `shortdrama-dl-windows`。
**90 天过期 + 下载要登录**,只适合你自己临时取。

---

## 4. 以后每次迭代的完整闭环

```
改代码  →  改 VERSION(比如 0.8.0 → 0.8.1)  →  git push
       →  Actions 里点 Run workflow(勾 publish_release)
       →  3 分钟后 https://github.com/pian123465/DJUTool/releases 出现 v0.8.1
```

同一个 tag 重跑会**覆盖**旧附件,不会堆一串重复版本 —— 所以忘记改 VERSION 也
不会把 Releases 列表搞乱(只是覆盖同一个 tag 的 exe)。

**只想自测、不想发版**:把 `publish_release` 的勾去掉,构建照跑,Release 不动。

---

## 5. 本地打包(不想等 CI)

Windows 上装好 Python 3.11+,在 `短剧下载器-一键打包版/` 里双击 **`build.bat`**。

它会自动:装依赖 → 下 aria2c+ffmpeg → PyInstaller 打包 → 出
`dist\shortdrama-dl.exe`。第一次约 5 分钟,之后有缓存会快很多。

想在本地离线构建(不想每次都联网下 86MB)?

```bash
# 把 binaries.tar.gz 放进 assets/bin/ 即可,setup_binaries.py 会自动解压
cp 某处/binaries.tar.gz assets/bin/
set SHORTDRAMA_KEEP_BUNDLE=1     # 让它解压后别删,以后还能用
```

这个文件已经在 `.gitignore` 里,**不会被提交**,不会让你的仓库超限。

---

## 6. 常见问题

**Q: Release 步骤报 `HTTP 403` / `Resource not accessible by integration`**
A: 仓库给 Actions 的默认 token 只有 read 权限。v0.8 的 workflow 已经加了
`permissions: contents: write`,确认你推上去的 workflow 是新版本
(`grep -n "contents: write" .github/workflows/build-windows.yml`)。

**Q: 每次构建都要重新下 86MB ffmpeg?**
A: 第一次会下,之后走 `actions/cache` 命中缓存,不联网。只有缓存过期才会重下。
主源 BtbN 在 GitHub CDN 上,实测 4 秒下完;备用源 gyan.dev 经常 503,
所以别指望它 —— 真失败重跑一次就行。

**Q: 构建日志里 `Fetch and check binaries` 失败**
A: 看它上面那几行 `[DL] https://...`,是外网镜像挂了,不是代码问题。
直接再点一次 Run workflow。

**Q: 双击 exe 弹出红色错误框**
A: 把框截图发我,`disable_windowed_traceback=False` 是开着的,
任何运行期错误都会弹框而不是静默退出。

**Q: Windows 提示"已保护你的电脑"**
A: 198MB 的 exe 没做代码签名,SmartScreen 正常拦截。
点 **更多信息 → 仍要运行**。要彻底避免得买代码签名证书(每年几百块),
个人项目一般不值得。

**Q: exe 第一次启动很久没反应**
A: onefile 模式要把运行库解压到临时目录,**10~20 秒**正常,不是卡死。
