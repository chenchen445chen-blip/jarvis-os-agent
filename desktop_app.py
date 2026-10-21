#!/usr/bin/env python3
"""
JARVIS / AIVY OS - 原生极简桌面窗口启动器 (Native GUI Launcher)
无需繁重的 Node.js/Electron 打包，直接基于系统底层 WebKit 引擎拉起独立桌面窗口。
"""

import sys
import os
import time
import threading
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = ROOT_DIR / "backend"
sys.path.insert(0, str(BACKEND_DIR))

def run_backend_server():
    """在后台独立线程中托管 FastAPI 智能体服务"""
    import uvicorn
    os.chdir(str(BACKEND_DIR))
    uvicorn.run("server:app", host="127.0.0.1", port=8765, log_level="warning")

def main():
    print("=" * 60)
    print(" 🖥️  正在拉起 JARVIS / AIVY 独立桌面原生应用窗口...")
    print("=" * 60)

    # 1. 后台线程启动后端核心
    server_thread = threading.Thread(target=run_backend_server, daemon=True)
    server_thread.start()
    time.sleep(1.2)  # 等待后端端口就绪

    # 2. 尝试载入 pywebview 原生窗口库
    try:
        import webview
        # 创建原生科技感无边框/原生窗口
        window = webview.create_window(
            title="JARVIS // AIVY OS - 桌面私人助理",
            url="http://127.0.0.1:8765/app/",
            width=1280,
            height=820,
            min_size=(1024, 700),
            background_color="#050b14",
            text_select=False
        )
        # 启动 macOS Cocoa 原生渲染视窗
        webview.start()
    except ImportError:
        print("\n[提示] 检测到尚未安装 pywebview 原生桌面窗口库。")
        print("您只需运行以下命令进行一次极速安装：")
        print("    pip install pywebview\n")
        print("或者您也可以通过 Electron 模式启动：")
        print("    cd desktop-electron && npm install && npm start\n")

if __name__ == "__main__":
    main()
