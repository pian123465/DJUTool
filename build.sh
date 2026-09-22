#!/usr/bin/env bash
# Linux/macOS 本地开发构建(仅打包源码 zip,真正 .exe 必须在 Windows 上构建)

set -e
echo "========================================="
echo " 短剧下载器 - 源码打包脚本"
echo "========================================="

# 清理缓存
find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

# 打源码 zip(供下载)
zip -rq shortdrama-dl-source.zip . \
    -x "*.pyc" "*__pycache__*" \
    -x ".venv/*" "dist/*" "build/*" \
    -x "*.db" ".git/*" "node_modules/*"

echo
echo "✓ 源码包:shortdrama-dl-source.zip"
echo
echo "在 Windows 上构建 .exe 的步骤:"
echo "  1. 解压源码到 Windows 11"
echo "  2. 双击 build.bat"
echo "  3. 等待 1-3 分钟,产出 dist\\shortdrama-dl.exe"