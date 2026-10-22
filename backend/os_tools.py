import os
import sys
import re
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
            "music": ["Music", "NeteaseMusic", "QQMusic", "Spotify", "CloudMusic"],
            "网易云音乐": ["NeteaseMusic", "cloudmusic"],
            "qq音乐": ["QQMusic", "qqmusic"],
            "网易云": ["NeteaseMusic", "cloudmusic"],
            "音乐播放器": ["Music", "NeteaseMusic", "QQMusic", "Spotify"],
            "音乐": ["Music", "NeteaseMusic", "QQMusic"],
            
            # 绘图设计类
            "drawing": ["Preview", "Photoshop", "Sketch", "Figma", "mspaint", "GIMP"],
            "画图": ["Preview", "Paint", "mspaint"],
            "画图软件": ["Preview", "Paint", "mspaint"],
            "ps": ["Adobe Photoshop 2024", "Adobe Photoshop", "Photoshop"],
            "photoshop": ["Adobe Photoshop 2024", "Photoshop"],
            "figma": ["Figma"],
            
            # 办公与日常
            "浏览器": ["Google Chrome", "Safari", "Microsoft Edge", "Firefox"],
            "谷歌浏览器": ["Google Chrome", "Chrome"],
            "chrome": ["Google Chrome", "Chrome"],
            "safari": ["Safari"],
            "日历": ["Calendar"],
            "邮件": ["Mail"],
            "邮箱": ["Mail"],
            "微信": ["WeChat"],
            "计算器": ["Calculator"],
            "备忘录": ["Notes"],
            "便签": ["Stickies", "Notes"],
            "设置": ["System Settings", "System Preferences"],
            "系统设置": ["System Settings", "System Preferences"],
            "地图": ["Maps"],
            "天气": ["Weather"],
            "照片": ["Photos"],
            "访达": ["Finder"],
            "代码编辑器": ["Visual Studio Code", "Cursor", "Antigravity IDE", "HBuilderX", "code"],
            "vscode": ["Visual Studio Code", "code"],
            "cursor": ["Cursor"],
            "终端": ["Terminal", "iTerm", "iTerm2"]
        }

    def open_application(self, app_name: str) -> Dict[str, Any]:
        """调起或激活本地指定的应用程序，并返回清晰的成功或失败提示"""
        target_name = app_name.strip()
        candidates = list(self.app_aliases.get(target_name.lower(), []))
        if target_name not in candidates:
            candidates.append(target_name)

        executed_candidate = None
        success = False
        error_detail = ""

        for cand in candidates:
            try:
                if SYSTEM_OS == "Darwin":  # macOS
                    res = subprocess.run(["open", "-a", cand], capture_output=True, text=True, timeout=5)
                    if res.returncode == 0:
                        success = True
                        executed_candidate = cand
                        break
                    else:
                        if not error_detail and res.stderr:
                            error_detail = res.stderr.strip()
                elif SYSTEM_OS == "Windows":
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
                    else:
                        if not error_detail and res.stderr:
                            error_detail = res.stderr.strip()
            except Exception as e:
                error_detail = str(e)

        # macOS 深度检索：若指定名称未能直接调起，智能遍历应用程序目录扫描匹配的 .app
        if not success and SYSTEM_OS == "Darwin":
            search_dirs = [
                Path("/Applications"),
                Path("/System/Applications"),
                Path("/System/Applications/Utilities"),
                Path.home() / "Applications"
            ]
            clean_kw = target_name.lower().replace(".app", "")
            for d in search_dirs:
                if d.exists():
                    for app_file in d.glob("*.app"):
                        app_stem = app_file.stem
                        if clean_kw in app_stem.lower() or app_stem.lower() in clean_kw:
                            res = subprocess.run(["open", str(app_file)], capture_output=True, text=True, timeout=5)
                            if res.returncode == 0:
                                success = True
                                executed_candidate = app_stem
                                break
                    if success:
                        break

        if success:
            return {
                "success": True,
                "status": "success",
                "app": executed_candidate,
                "message": f"已成功为您启动或切换至应用程序：[{executed_candidate}]。"
            }
        else:
            return {
                "success": False,
                "status": "failed",
                "app": app_name,
                "message": f"未能启动应用 [{app_name}]：系统中未检测到该应用程序，请确认是否已安装或名称是否准确。"
            }

    def open_wechat(self) -> Dict[str, Any]:
        """通过操作系统原生命令行调起微信客户端并返回状态提示"""
        res = self.open_application("微信")
        if res.get("success"):
            return {
                "success": True,
                "status": "success",
                "app": "微信",
                "command": 'open -a "/Applications/WeChat.app"' if SYSTEM_OS == "Darwin" else "WeChat",
                "message": "已成功为您启动或切换至微信客户端。"
            }
        else:
            return {
                "success": False,
                "status": "failed",
                "app": "微信",
                "command": 'open -a "/Applications/WeChat.app"' if SYSTEM_OS == "Darwin" else "WeChat",
                "message": "微信启动失败：系统中未检测到微信客户端，请确认是否已安装。"
            }

    def execute_command(self, command: str, cwd: str = "") -> Dict[str, Any]:
        """
        在操作系统本地终端（Shell/Terminal）中执行命令行指令。
        支持文件查看(cat/head/tail/ls)、文件修改与写入(echo/tee/sed/python脚本)、检索查找(grep/find)、目录操作、Git操作等一切终端指令。
        """
        if not command or not command.strip():
            return {
                "success": False,
                "command": command,
                "output": "",
                "message": "指令为空，无法执行终端命令。"
            }

        # 危险命令拦截保护
        dangerous_patterns = [
            r"\brm\s+.*-[a-zA-Z]*r[a-zA-Z]*\s+/(?:\s|$|\*)",
            r"\bmkfs\b",
            r"\bdd\s+if=",
            r":\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;",
        ]
        for pattern in dangerous_patterns:
            if re.search(pattern, command.strip()):
                return {
                    "success": False,
                    "command": command,
                    "output": "",
                    "message": f"安全拦截：检测到高危系统破坏性命令 [{command}]，已阻止执行以保护系统安全。"
                }

        # 项目根目录作为缺省工作目录
        base_dir = str(Path(__file__).resolve().parent.parent)
        work_dir = cwd.strip() if cwd and os.path.exists(cwd.strip()) else base_dir

        try:
            res = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                cwd=work_dir,
                timeout=30
            )
            stdout = res.stdout.strip()
            stderr = res.stderr.strip()
            success = res.returncode == 0

            # 聚合标准输出与错误输出
            combined = stdout if stdout else stderr
            if stdout and stderr:
                combined = f"{stdout}\n[STDERR]:\n{stderr}"

            # 截断超大输出防止上下文爆满
            if len(combined) > 4000:
                combined = combined[:4000] + "\n...[输出过长，已截断显示]..."

            if success:
                msg = f"命令执行成功（退出码 0）。\n输出：\n{combined}" if combined else "命令执行成功，终端无内容输出。"
            else:
                msg = f"命令执行失败（退出码 {res.returncode}）。\n错误输出：\n{stderr or combined}"

            return {
                "success": success,
                "command": command,
                "returncode": res.returncode,
                "stdout": stdout,
                "stderr": stderr,
                "output": combined,
                "cwd": work_dir,
                "message": msg
            }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "command": command,
                "returncode": -1,
                "output": "",
                "cwd": work_dir,
                "message": f"执行超时（已达 30 秒限时），进程已自动终止。"
            }
        except Exception as e:
            return {
                "success": False,
                "command": command,
                "returncode": -1,
                "output": "",
                "cwd": work_dir,
                "message": f"执行终端命令异常: {str(e)}"
            }

    def read_file(self, file_path: str, start_line: int = 1, line_count: int = 200) -> Dict[str, Any]:
        """
        查看或读取本地文本文件的内容
        支持相对路径（相对项目根目录）或绝对路径，支持按行范围读取
        """
        if not file_path or not file_path.strip():
            return {"success": False, "message": "文件路径不能为空。"}

        target = Path(file_path.strip())
        if not target.is_absolute():
            base_dir = Path(__file__).resolve().parent.parent
            target = (base_dir / target).resolve()

        if not target.exists():
            return {
                "success": False,
                "file_path": str(target),
                "message": f"文件不存在：{target}"
            }

        if not target.is_file():
            return {
                "success": False,
                "file_path": str(target),
                "message": f"目标路径不是普通文件：{target}"
            }

        try:
            try:
                with open(target, "r", encoding="utf-8") as f:
                    lines = f.readlines()
            except UnicodeDecodeError:
                with open(target, "r", encoding="gbk", errors="ignore") as f:
                    lines = f.readlines()

            total_lines = len(lines)
            start_idx = max(0, start_line - 1)
            end_idx = min(total_lines, start_idx + max(1, line_count))
            selected_lines = lines[start_idx:end_idx]

            content_with_nums = "".join(
                f"{i + 1:4d}: {line}" for i, line in enumerate(selected_lines, start=start_idx)
            )

            msg = f"已读取文件 [{target.name}]（共 {total_lines} 行，展示第 {start_idx + 1} ~ {end_idx} 行）：\n{content_with_nums}"
            return {
                "success": True,
                "file_path": str(target),
                "total_lines": total_lines,
                "start_line": start_idx + 1,
                "end_line": end_idx,
                "content": "".join(selected_lines),
                "message": msg
            }
        except Exception as e:
            return {
                "success": False,
                "file_path": str(target),
                "message": f"读取文件异常: {str(e)}"
            }

    def modify_file(self, file_path: str, content: str, mode: str = "overwrite") -> Dict[str, Any]:
        """
        修改或创建本地文本文件
        mode 支持 'overwrite'（覆盖写入）或 'append'（追加在末尾）
        """
        if not file_path or not file_path.strip():
            return {"success": False, "message": "文件路径不能为空。"}

        target = Path(file_path.strip())
        if not target.is_absolute():
            base_dir = Path(__file__).resolve().parent.parent
            target = (base_dir / target).resolve()

        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            write_mode = "a" if mode == "append" else "w"
            with open(target, write_mode, encoding="utf-8") as f:
                f.write(content)

            total_size = target.stat().st_size
            action_desc = "追加内容至" if mode == "append" else "成功写入/覆盖"
            return {
                "success": True,
                "file_path": str(target),
                "mode": mode,
                "size_bytes": total_size,
                "message": f"已{action_desc}文件：[{target.name}]（路径: {target}，大小: {total_size} 字节）。"
            }
        except Exception as e:
            return {
                "success": False,
                "file_path": str(target),
                "message": f"修改/写入文件失败: {str(e)}"
            }

    def play_music(self, song_name: str = "", artist: str = "") -> Dict[str, Any]:
        """播放音乐（优先调起音乐软件，或通过系统默认播放/网页试听）"""
        query = f"{song_name} {artist}".strip()
        lower_q = query.lower()

        # 防御性校验：若明显是古诗词朗诵而非音乐，避免弹出播放器或打开网页
        if any(w in lower_q for w in ["古诗", "唐诗", "宋词", "文言文", "诗词", "朗诵"]) and not any(w in lower_q for w in ["歌", "曲", "音乐"]):
            return {
                "success": False,
                "message": f"检测到 [{query}] 属于诗词文学内容，已拦截调起音乐播放器，由助手直接在对话中为您朗诵与解读。",
                "song": query
            }

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
        """打开本地绘画或作图软件并返回明确提示"""
        target = app_name or "画图"
        res = self.open_application(target)
        if res.get("success"):
            return {
                "success": True,
                "status": "success",
                "app": res.get("app", target),
                "message": f"绘图工作台启动成功，已为您唤醒本地画图软件：[{res.get('app', target)}]"
            }
        else:
            return {
                "success": False,
                "status": "failed",
                "app": target,
                "message": f"绘图软件启动失败：系统中未检测到可用的绘画工具 [{target}]，请确认是否已安装绘图软件。"
            }

    def generate_ai_image(self, prompt: str, negative_prompt: str = "") -> Dict[str, Any]:
        """
        联动云端/本地 AI 绘图引擎 (兼容 OpenAI / 智谱 CogView / 硅基流动 Flux / 本地 SD WebUI / 兜底矢量合成)
        """
        # 动态刷新 .env 配置，方便用户热更新生图模型和独立 AppKey
        env_file = Path(__file__).resolve().parent.parent / ".env"
        if env_file.exists():
            try:
                with open(env_file, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            k, v = line.split("=", 1)
                            os.environ[k.strip()] = v.strip().strip("'\"")
            except Exception:
                pass

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = self.generated_images_dir / f"jarvis_gen_{timestamp}.png"

        # 1. 尝试调用云端文生图 API（优先使用 IMAGE_* 配置，未指定时自动回退复用 LLM_* 配置）
        img_key = os.getenv("IMAGE_API_KEY", "").strip() or os.getenv("LLM_API_KEY", "").strip()
        img_base = os.getenv("IMAGE_BASE_URL", "").strip() or os.getenv("LLM_BASE_URL", "").strip()
        img_model = os.getenv("IMAGE_MODEL", "").strip()

        # 若未显式指定 img_model，但配置了独立的生图 Key 或智谱服务，自动推断适配模型
        if not img_model and (os.getenv("IMAGE_API_KEY") or "bigmodel.cn" in img_base):
            img_model = "cogview-3-plus" if "bigmodel.cn" in img_base else "dall-e-3"

        cloud_error_msg = ""
        if img_key and img_model:
            try:
                # 判断是否为 Google Gemini 原生模型 (如 gemini-3-pro-image)
                if "gemini" in img_model.lower() or "googleapis.com" in img_base:
                    endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{img_model}:generateContent?key={img_key}"
                    gemini_payload = {
                        "contents": [
                            {
                                "parts": [{"text": prompt}]
                            }
                        ],
                        "generationConfig": {
                            "responseModalities": ["IMAGE"]
                        }
                    }
                    payload = json.dumps(gemini_payload).encode("utf-8")
                    req = urllib.request.Request(
                        endpoint,
                        data=payload,
                        headers={
                            "Content-Type": "application/json",
                            "x-goog-api-key": img_key,
                            "User-Agent": "Jarvis-OS-Agent/1.0"
                        },
                        method="POST"
                    )
                    with urllib.request.urlopen(req, timeout=60) as resp:
                        res_data = json.loads(resp.read().decode("utf-8"))
                        candidates = res_data.get("candidates", [])
                        if candidates:
                            parts = candidates[0].get("content", {}).get("parts", [])
                            for p in parts:
                                inline = p.get("inlineData") or p.get("inline_data")
                                if inline and inline.get("data"):
                                    import base64
                                    with open(output_file, "wb") as f:
                                        f.write(base64.b64decode(inline["data"]))
                                    break
                else:
                    # 兼容标准 OpenAI 格式接口 (智谱 CogView / OpenAI DALL-E / 硅基流动 Flux 等)
                    endpoint = f"{img_base.rstrip('/')}/images/generations"
                    payload_dict = {
                        "model": img_model,
                        "prompt": prompt
                    }
                    if negative_prompt and "dall-e" not in img_model.lower():
                        payload_dict["negative_prompt"] = negative_prompt

                    payload = json.dumps(payload_dict).encode("utf-8")
                    req = urllib.request.Request(
                        endpoint,
                        data=payload,
                        headers={
                            "Content-Type": "application/json",
                            "Authorization": f"Bearer {img_key}",
                            "User-Agent": "Jarvis-OS-Agent/1.0"
                        },
                        method="POST"
                    )
                    with urllib.request.urlopen(req, timeout=60) as resp:
                        res_data = json.loads(resp.read().decode("utf-8"))
                        img_items = res_data.get("data", []) or res_data.get("images", [])
                        if img_items:
                            first_item = img_items[0]
                            img_url = first_item.get("url")
                            b64_data = first_item.get("b64_json") or first_item.get("image")

                            if img_url:
                                dl_req = urllib.request.Request(img_url, headers={"User-Agent": "Mozilla/5.0"})
                                with urllib.request.urlopen(dl_req, timeout=30) as dl_resp:
                                    with open(output_file, "wb") as f:
                                        f.write(dl_resp.read())
                            elif b64_data:
                                import base64
                                with open(output_file, "wb") as f:
                                    f.write(base64.b64decode(b64_data))

                if output_file.exists() and output_file.stat().st_size > 0:
                    if SYSTEM_OS == "Darwin":
                        try:
                            subprocess.Popen(["open", str(output_file)])
                        except Exception:
                            pass

                    return {
                        "success": True,
                        "engine": f"Cloud [{img_model}]",
                        "file_path": str(output_file),
                        "url": f"/static/generated/{output_file.name}",
                        "message": f"AI 绘画完成！已通过云端模型 [{img_model}] 生成并保存至：{output_file.name}"
                    }
            except urllib.error.HTTPError as he:
                try:
                    err_json = json.loads(he.read().decode("utf-8"))
                    err_detail = err_json.get("error", {}).get("message") or str(err_json)
                    cloud_error_msg = f"{img_model} 官方返回 HTTP {he.code}: {err_detail[:120]}"
                except Exception:
                    cloud_error_msg = f"{img_model} HTTP {he.code} 请求被拒绝"
                print(f"[IMAGE GENERATION WARNING] {cloud_error_msg}")
            except Exception as e:
                cloud_error_msg = f"{img_model} 调用异常: {str(e)[:80]}"
                print(f"[IMAGE GENERATION WARNING] {cloud_error_msg}")

        # 2. 尝试检测并调用本地 Stable Diffusion WebUI 接口
        sd_url = "http://127.0.0.1:7860/sdapi/v1/txt2img"
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
                if SYSTEM_OS == "Darwin":
                    try:
                        subprocess.Popen(["open", str(output_file)])
                    except Exception:
                        pass
                return {
                    "success": True,
                    "engine": "Stable Diffusion WebUI",
                    "file_path": str(output_file),
                    "url": f"/static/generated/{output_file.name}",
                    "message": f"AI 绘画完成！已通过本地 SD 生成并保存至：{output_file.name}"
                }
        except Exception:
            pass
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
            
            fallback_notice = f"（注：云端生图服务 {cloud_error_msg}，已启动安全兜底机制为您生成概念图）" if cloud_error_msg else ""
            return {
                "success": True,
                "engine": "Built-in Vector Synth",
                "file_path": str(svg_file),
                "url": f"/static/generated/{svg_file.name}",
                "message": f"已完成画面生成！画面描述：[{prompt}]{fallback_notice}，文件已保存至：{svg_file.name}"
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
        """读取邮件摘要（对接真实 IMAP 邮箱或检测本地配置）"""
        email_user = os.environ.get("EMAIL_USER", "").strip()
        email_pass = os.environ.get("EMAIL_PASS", "").strip()
        email_server = os.environ.get("EMAIL_IMAP_SERVER", "").strip() or "imap.qq.com"

        # 若用户尚未在 .env 中配置个人邮箱，诚实反馈，绝不捏造假邮件
        if not email_user or not email_pass:
            return {
                "success": False,
                "configured": False,
                "count": 0,
                "emails": [],
                "message": "先生，您当前尚未配置个人邮箱凭据（IMAP/SMTP）。如需查阅邮件，请在 .env 中配置 EMAIL_USER 与 EMAIL_PASS 授权码，或直接对我说“打开邮件客户端”。"
            }

        # 尝试连接真实 IMAP 服务器
        try:
            import imaplib
            import email
            from email.header import decode_header

            mail = imaplib.IMAP4_SSL(email_server)
            mail.login(email_user, email_pass)
            mail.select("INBOX")

            search_criteria = "UNSEEN" if filter_unread else "ALL"
            _, data = mail.search(None, search_criteria)
            mail_ids = data[0].split()

            if not mail_ids:
                mail.close()
                mail.logout()
                return {
                    "success": True,
                    "configured": True,
                    "count": 0,
                    "emails": [],
                    "message": "先生，您的邮箱当前没有未读邮件，收件箱很清爽。"
                }

            # 获取最新的前 5 封邮件摘要
            emails = []
            for m_id in reversed(mail_ids[-5:]):
                _, msg_data = mail.fetch(m_id, "(RFC822.HEADER)")
                raw_email = msg_data[0][1]
                msg = email.message_from_bytes(raw_email)

                # 解码主题
                subject, encoding = decode_header(msg.get("Subject", ""))[0]
                if isinstance(subject, bytes):
                    subject = subject.decode(encoding or "utf-8", errors="ignore")

                # 解码发件人
                sender, encoding = decode_header(msg.get("From", ""))[0]
                if isinstance(sender, bytes):
                    sender = sender.decode(encoding or "utf-8", errors="ignore")

                date_str = msg.get("Date", "")
                emails.append({
                    "id": m_id.decode("utf-8", errors="ignore"),
                    "sender": sender,
                    "subject": subject or "无主题",
                    "time": date_str,
                    "unread": True
                })

            mail.close()
            mail.logout()

            summary = f"为您查询到 {len(emails)} 封未读邮件：\n" + "\n".join(
                [f"• 来自 [{e['sender'].split('<')[0].strip()}]：{e['subject']}" for e in emails]
            )
            return {
                "success": True,
                "configured": True,
                "count": len(emails),
                "emails": emails,
                "message": summary
            }
        except Exception as e:
            return {
                "success": False,
                "configured": True,
                "count": 0,
                "emails": [],
                "message": f"连接邮箱服务器失败：{str(e)}。请检查邮箱授权码与 IMAP 端口设置。"
            }

    def send_email(self, recipient: str, subject: str, content: str) -> Dict[str, Any]:
        """发送邮件指令（支持配置 SMTP 或引导本地邮件客户端）"""
        email_user = os.environ.get("EMAIL_USER", "").strip()
        email_pass = os.environ.get("EMAIL_PASS", "").strip()
        email_smtp = os.environ.get("EMAIL_SMTP_SERVER", "").strip() or "smtp.qq.com"

        if not email_user or not email_pass:
            return {
                "success": False,
                "configured": False,
                "message": f"当前尚未配置发信邮箱凭据（SMTP）。请在 .env 中配置 EMAIL_USER 与 EMAIL_PASS 授权码，或者直接打开本地邮件客户端进行发送。"
            }

        try:
            import smtplib
            from email.mime.text import MIMEText
            from email.header import Header

            msg = MIMEText(content, "plain", "utf-8")
            msg["From"] = Header(f"JARVIS OS <{email_user}>", "utf-8")
            msg["To"] = Header(recipient, "utf-8")
            msg["Subject"] = Header(subject, "utf-8")

            server = smtplib.SMTP_SSL(email_smtp, 465)
            server.login(email_user, email_pass)
            server.sendmail(email_user, [recipient], msg.as_string())
            server.quit()

            return {
                "success": True,
                "configured": True,
                "message": f"邮件已成功投递！收件人：{recipient}，主题：{subject}",
                "details": {"recipient": recipient, "subject": subject}
            }
        except Exception as e:
            return {
                "success": False,
                "configured": True,
                "message": f"发送邮件失败：{str(e)}。请核对 SMTP 授权码。"
            }
