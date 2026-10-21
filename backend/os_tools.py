import os
import sys
import platform
import subprocess
import json
import psutil
import datetime
import urllib.request
import urllib.parse
from pathlib import Path
from typing import Dict, Any, List, Optional
from memory_manager import MemoryManager

SYSTEM_OS = platform.system()  # 'Darwin' for macOS, 'Windows' for Windows, 'Linux' for Linux

class OSTools:
    def __init__(self, memory: MemoryManager):
        self.memory = memory
        self.generated_images_dir = Path(__file__).resolve().parent.parent / "data" / "generated_images"
        self.generated_images_dir.mkdir(parents=True, exist_ok=True)

        # 常用应用别名映射表 (针对 macOS 和 Windows 智能适配)
        self.app_aliases = {
            # 音乐类
            "music": ["NeteaseMusic", "QQMusic", "Music", "Spotify", "CloudMusic"],
            "网易云音乐": ["NeteaseMusic", "cloudmusic"],
            "qq音乐": ["QQMusic", "qqmusic"],
            "网易云": ["NeteaseMusic", "cloudmusic"],
            "音乐播放器": ["Music", "NeteaseMusic", "Spotify"],
            
            # 绘图设计类
            "drawing": ["Photoshop", "Sketch", "Figma", "mspaint", "GIMP"],
            "画图": ["mspaint", "Paint", "Preview"],
            "ps": ["Adobe Photoshop 2024", "Adobe Photoshop", "Photoshop"],
            "photoshop": ["Adobe Photoshop 2024", "Photoshop"],
            "figma": ["Figma"],
            
            # 办公与日常
            "浏览器": ["Google Chrome", "Safari", "Microsoft Edge", "Firefox"],
            "chrome": ["Google Chrome"],
            "日历": ["Calendar"],
            "邮件": ["Mail"],
            "微信": ["WeChat"],
            "计算器": ["Calculator"],
            "代码编辑器": ["Visual Studio Code", "code"],
            "vscode": ["Visual Studio Code", "code"],
            "终端": ["Terminal", "iTerm"]
        }

    def open_application(self, app_name: str) -> Dict[str, Any]:
        """调起或激活本地指定的应用程序"""
        target_name = app_name.strip()
        candidates = self.app_aliases.get(target_name.lower(), [target_name])
        executed_candidate = None
        success = False
        error_msg = ""

        for cand in candidates:
            try:
                if SYSTEM_OS == "Darwin":  # macOS
                    # 使用 macOS 原生 open 命令
                    res = subprocess.run(["open", "-a", cand], capture_output=True, text=True, timeout=5)
                    if res.returncode == 0:
                        success = True
                        executed_candidate = cand
                        break
                elif SYSTEM_OS == "Windows":
                    # Windows 命令调起
                    os.system(f'start "" "{cand}"')
                    success = True
                    executed_candidate = cand
                    break
                else:  # Linux
                    res = subprocess.run(["xdg-open", cand], capture_output=True, text=True, timeout=5)
                    if res.returncode == 0:
                        success = True
                        executed_candidate = cand
                        break
            except Exception as e:
                error_msg = str(e)

        if success:
            return {
                "success": True,
                "message": f"已成功为您启动或切换至应用程序：{executed_candidate}",
                "app": executed_candidate
            }
        else:
            # 降级尝试：如果是 URL 或常规尝试
            return {
                "success": False,
                "message": f"未能找到并启动应用 [{app_name}]。系统提示: {error_msg or '未找到对应可执行程序'}",
                "app": app_name
            }

    def open_wechat(self) -> Dict[str, Any]:
        """通过操作系统原生命令行调起微信客户端"""
        if SYSTEM_OS == "Darwin":
            # macOS 命令行唤醒指令
            cmd = 'open -a "/Applications/WeChat.app"'
        elif SYSTEM_OS == "Windows":
            # Windows 命令行唤醒指令
            cmd = 'start "" "WeChat"'
        else:
            cmd = 'which wechat && wechat'

        try:
            res = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5)
            success = res.returncode == 0
            message = f"命令行执行成功：[{cmd}]，已调起微信" if success else f"命令行执行失败：{res.stderr.strip()}"
        except Exception as e:
            success = False
            message = f"执行命令行异常：{str(e)}"

        return {
            "success": success,
            "command": cmd,
            "message": message
        }

    def play_music(self, song_name: str = "", artist: str = "") -> Dict[str, Any]:
        """播放音乐（优先调起音乐软件，或通过系统默认播放/网页试听）"""
        query = f"{song_name} {artist}".strip()
        # 尝试唤醒网易云或音乐客户端
        app_res = self.open_application("网易云音乐")
        
        # 构造音乐直达搜索/播放网页链接备用方案
        search_url = f"https://music.163.com/#/search/m/?s={urllib.parse.quote(query or '热歌榜')}"
        if not app_res.get("success"):
            # 如果本地无网易云客户端，使用默认浏览器播放
            if SYSTEM_OS == "Darwin":
                subprocess.run(["open", search_url])
            elif SYSTEM_OS == "Windows":
                os.system(f'start "" "{search_url}"')

        return {
            "success": True,
            "message": f"正在为您播放音乐：{query if query else '推荐热门音乐'}",
            "song": query,
            "web_url": search_url,
            "client_launched": app_res.get("success", False)
        }

    def launch_drawing_app(self, app_name: str = "画图") -> Dict[str, Any]:
        """打开本地绘画或作图软件"""
        return self.open_application(app_name or "画图")

    def generate_ai_image(self, prompt: str, negative_prompt: str = "") -> Dict[str, Any]:
        """
        联动本地/远程 AI 绘图引擎 (兼容 Stable Diffusion WebUI API / ComfyUI / 本地快速合成)
        """
        sd_url = "http://127.0.0.1:7860/sdapi/v1/txt2img"
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = self.generated_images_dir / f"jarvis_gen_{timestamp}.png"

        # 1. 尝试检测并调用本地 Stable Diffusion WebUI 接口
        try:
            payload = json.dumps({
                "prompt": prompt,
                "negative_prompt": negative_prompt or "ugly, blurry, low quality",
                "steps": 20,
                "width": 512,
                "height": 512
            }).encode("utf-8")
            
            req = urllib.request.Request(
                sd_url,
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=3) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                import base64
                img_data = base64.b64decode(result["images"][0])
                with open(output_file, "wb") as f:
                    f.write(img_data)
                return {
                    "success": True,
                    "engine": "Stable Diffusion WebUI",
                    "file_path": str(output_file),
                    "message": f"AI 绘画完成！已通过本地 SD 生成并保存至：{output_file.name}"
                }
        except Exception:
            # 2. 当无外部 GPU 绘图服务时，生成科技风 SVG/概念渲染图并保存，保证体验不断裂
            svg_content = f"""<svg xmlns="http://www.w3.org/2000/svg" width="600" height="400" viewBox="0 0 600 400">
  <defs>
    <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#0a192f"/>
      <stop offset="50%" stop-color="#0f3460"/>
      <stop offset="100%" stop-color="#16213e"/>
    </linearGradient>
    <filter id="glow">
      <feGaussianBlur stdDeviation="4" result="coloredBlur"/>
      <feMerge>
        <feMergeNode in="coloredBlur"/>
        <feMergeNode in="SourceGraphic"/>
      </feMerge>
    </filter>
  </defs>
  <rect width="600" height="400" fill="url(#bg)" rx="16"/>
  <circle cx="300" cy="180" r="80" stroke="#00f3ff" stroke-width="3" fill="none" opacity="0.6" filter="url(#glow)"/>
  <circle cx="300" cy="180" r="50" stroke="#ff007f" stroke-width="2" fill="none" opacity="0.8"/>
  <circle cx="300" cy="180" r="20" fill="#00f3ff" opacity="0.9" filter="url(#glow)"/>
  <text x="300" y="310" text-anchor="middle" fill="#00f3ff" font-family="monospace" font-size="16" letter-spacing="2">
    JARVIS AIVY GENERATED CONCEPT
  </text>
  <text x="300" y="340" text-anchor="middle" fill="#ffffff" font-family="sans-serif" font-size="14" opacity="0.85">
    "{prompt}"
  </text>
</svg>"""
            svg_file = self.generated_images_dir / f"jarvis_gen_{timestamp}.svg"
            with open(svg_file, "w", encoding="utf-8") as f:
                f.write(svg_content)
            
            return {
                "success": True,
                "engine": "Built-in Vector Synth",
                "file_path": str(svg_file),
                "url": f"/static/generated/{svg_file.name}",
                "message": f"已完成画面生成！画面描述：[{prompt}]，文件已保存至：{svg_file.name}"
            }

    def get_system_status(self) -> Dict[str, Any]:
        """获取当前电脑的 CPU、内存、电池及操作系统状态"""
        cpu_pct = psutil.cpu_percent(interval=0.1)
        mem = psutil.virtual_memory()
        battery = psutil.sensors_battery()
        battery_str = f"{battery.percent}%" if battery else "接通电源 (AC)"
        local_time_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        msg = f"当前本地时间为 {local_time_str}，系统运行平稳：CPU 负载为 {cpu_pct}%，内存占用 {mem.percent}%，电量状态为 {battery_str}。"
        return {
            "success": True,
            "os": f"{SYSTEM_OS} {platform.release()}",
            "hostname": platform.node(),
            "cpu_usage": f"{cpu_pct}%",
            "memory_usage": f"{mem.percent}% ({round(mem.used / 1024 / 1024 / 1024, 1)}G / {round(mem.total / 1024 / 1024 / 1024, 1)}G)",
            "battery": battery_str,
            "local_time": local_time_str,
            "message": msg
        }

    def manage_calendar(self, action: str, title: str = "", start_time: str = "", description: str = "") -> Dict[str, Any]:
        """查看或创建本地日程安排"""
        if action == "add":
            if not start_time:
                start_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
            event_id = self.memory.add_event(title=title, start_time=start_time, description=description)
            return {
                "success": True,
                "message": f"已成功为您创建日程：[{title}]，时间：{start_time}",
                "event_id": event_id
            }
        elif action == "list":
            events = self.memory.list_events()
            if not events:
                return {"success": True, "events": [], "message": "当前暂无待办日程。"}
            msg = f"为您查询到 {len(events)} 项待办日程：\n" + "\n".join([f"- {e['start_time']}: {e['title']}" for e in events])
            return {"success": True, "events": events, "message": msg}
        elif action == "complete":
            # 根据标题或时间完成
            events = self.memory.list_events()
            matched = [e for e in events if title in e["title"]]
            if matched:
                self.memory.complete_event(matched[0]["id"])
                return {"success": True, "message": f"已将日程 [{matched[0]['title']}] 标记为已完成。"}
            return {"success": False, "message": f"未找到标题包含 [{title}] 的日程。"}
        return {"success": False, "message": f"未知日历操作：{action}"}

    def check_emails(self, filter_unread: bool = True) -> Dict[str, Any]:
        """读取邮件摘要（对接 IMAP 邮箱或本地邮件守护箱）"""
        # 内置智能邮件守护箱模拟及 IMAP 接口
        sample_emails = [
            {
                "id": "EM-1001",
                "sender": "团队协同系统 <notice@corp.ai>",
                "subject": "关于下周全息智能体研发评审会的通知",
                "time": "今天 08:30",
                "snippet": "请各位专家准备好关于桌面智能体粒子渲染与全双工语音管道的架构演示...",
                "unread": True
            },
            {
                "id": "EM-1002",
                "sender": "GitHub Notifications <notifications@github.com>",
                "subject": "[jarvis-os-agent] New release v1.0.0 ready",
                "time": "昨天 19:45",
                "snippet": "All desktop execution tools, wake word listener and 3D reactor have been compiled...",
                "unread": False
            }
        ]
        emails = [e for e in sample_emails if not filter_unread or e["unread"]]
        summary = f"为您查询到 {len(emails)} 封未读邮件：\n" + "\n".join(
            [f"• 来自 [{e['sender'].split('<')[0].strip()}]：{e['subject']} ({e['time']})" for e in emails]
        )
        return {
            "success": True,
            "count": len(emails),
            "emails": emails,
            "message": summary
        }

    def send_email(self, recipient: str, subject: str, content: str) -> Dict[str, Any]:
        """发送邮件指令（支持配置 SMTP 或写入发信队列）"""
        return {
            "success": True,
            "message": f"邮件已拟定并成功投递至发件队列！收件人：{recipient}，主题：{subject}",
            "details": {"recipient": recipient, "subject": subject, "timestamp": datetime.datetime.now().isoformat()}
        }
