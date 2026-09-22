@echo off
REM Windows 11 一键构建脚本
REM 用法:双击 build.bat,等 3 分钟,产出 dist\shortdrama-dl.exe
REM
REM 产出物:
REM   dist\shortdrama-dl.exe           ← 单文件可执行(可直接运行)
REM   installer_output\Setup-Shortdrama-0.3.exe  ← 安装包(需先装 Inno Setup)

echo =========================================
echo  短剧下载器 - Windows 一键构建
echo =========================================

REM 1. 检查 Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [X] Python 未安装,请先去 https://www.python.org 下载 3.10+
    echo    安装时记得勾选 "Add Python to PATH"
    pause
    exit /b 1
)

REM 2. 创建虚拟环境
if not exist ".venv" (
    echo [1/6] 创建虚拟环境...
    python -m venv .venv
)

call .venv\Scripts\activate

REM 3. 装依赖
echo [2/6] 安装依赖...
pip install --upgrade pip -q
pip install pyinstaller -q
pip install -r requirements.txt -q

REM 4. 检查 / 生成图标
echo [3/6] 检查图标...
if not exist "assets\icon.ico" (
    where convert >nul 2>&1
    if not errorlevel 1 (
        python tools\build_icon.py
    ) else (
        echo [警告] 未找到 ImageMagick,跳过图标生成;图标需手动提供到 assets\icon.ico
    )
) else (
    echo    图标已存在,跳过
)

REM 5. PyInstaller 打包
echo [4/6] PyInstaller 打包(可能 1-3 分钟)...
pyinstaller shortdrama.spec --clean --noconfirm
if errorlevel 1 (
    echo [X] 打包失败
    pause
    exit /b 1
)

REM 6. 询问是否生成安装包
echo [5/6] 检查 Inno Setup...
where iscc >nul 2>&1
if not errorlevel 1 (
    echo [6/6] 生成安装包...
    iscc installer.iss
) else (
    echo [提示] Inno Setup Compiler 未安装(https://jrsoftware.org)
    echo        可执行文件已就绪:dist\shortdrama-dl.exe
    echo        要生成安装包请先装 Inno Setup,再运行 iscc installer.iss
)

echo.
echo =========================================
echo  构建完成!
echo =========================================
echo  直接运行: dist\shortdrama-dl.exe
if exist installer_output\Setup-Shortdrama-0.3.exe (
    echo  安装包:   installer_output\Setup-Shortdrama-0.3.exe
)
echo =========================================
echo.
pause