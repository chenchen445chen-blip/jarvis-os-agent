#!/usr/bin/env python3
"""
JARVIS / AIVY OS - 桌面级私有智能体一键启动入口
"""
import sys
import os
import uvicorn
from pathlib import Path

# 将 backend 加入模块搜索路径
CURRENT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = CURRENT_DIR / "backend"
sys.path.insert(0, str(BACKEND_DIR))

if __name__ == "__main__":
    print("=" * 60)
    print(" 🚀 JARVIS / AIVY DESKTOP AGENT CORE STARTING...")
    print(" ⚡ Web HUD Interface: http://localhost:8765/app/")
    print(" 🧠 OS Tools: App Launcher | Music | AI Painter | Calendar | Email")
    print("=" * 60)
    
    # 切换至 backend 目录并启动服务（开启热重载）
    os.chdir(str(BACKEND_DIR))
    uvicorn.run("server:app", host="127.0.0.1", port=8765, reload=True, reload_dirs=[str(BACKEND_DIR)])
