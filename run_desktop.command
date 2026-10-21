#!/bin/bash
# 进入脚本所在目录
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR/desktop-electron"

# 检查是否已安装 node_modules
if [ ! -d "node_modules" ]; then
    echo "⚡ 首次运行，正在自动安装 Electron 桌面依赖..."
    npm install
fi

echo "🚀 正在启动 JARVIS / AIVY 桌面应用程序..."
npm start
