import os
import re
import json
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
from os_tools import OSTools
from memory_manager import MemoryManager

# Function Calling 工具定义（符合 OpenAI / DeepSeek 规范）
AGENT_TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "open_application",
            "description": "调起或切换至电脑本地的应用程序（如微信、VSCode、浏览器、计算器等）",
            "parameters": {
                "type": "object",
                "properties": {
                    "app_name": {"type": "string", "description": "要打开的应用程序名称"}
                },
                "required": ["app_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "open_wechat",
            "description": "通过操作系统原生命令行方式快速调起微信（WeChat）客户端",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "play_music",
            "description": "播放音乐歌曲。仅在用户明确表达想听音乐、听歌、播放歌曲时调用。严禁用在古诗、诗词、文言文、课文、散文、寓言或任何文学与知识问答中（此类内容请直接在对话中背诵或解答，绝对不要调用此工具）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "song_name": {"type": "string", "description": "歌名或歌手名（必须是真实音乐歌曲作品，禁止传入诗词或文章篇目）"}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "launch_drawing_app",
            "description": "启动电脑上的绘图设计软件，如画图、Photoshop、Figma 等",
            "parameters": {
                "type": "object",
                "properties": {
                    "app_name": {"type": "string", "description": "绘图软件名称，默认画图"}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "generate_ai_image",
            "description": "使用本地或云端 AI 绘图引擎生成一张新图像",
            "parameters": {
                "type": "object",
                "properties": {
                    "prompt": {"type": "string", "description": "画面的提示词描述"}
                },
                "required": ["prompt"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "manage_calendar",
            "description": "查询、新增或完成本地日历日程",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["list", "add", "complete"], "description": "操作类型"},
                    "title": {"type": "string", "description": "日程标题或事项内容"},
                    "start_time": {"type": "string", "description": "时间，例如 2026-10-21 14:00"}
                },
                "required": ["action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "check_emails",
            "description": "检查未读邮件列表与摘要",
            "parameters": {
                "type": "object",
                "properties": {
                    "filter_unread": {"type": "boolean", "description": "是否仅看未读"}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_system_status",
            "description": "获取当前电脑硬件指标（CPU、内存、电量及时间）",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "execute_command",
            "description": "在操作系统本地终端（Shell/Terminal）中执行命令行指令。支持查看文件（cat、head、tail、ls）、检索查找（grep、find）、修改与写入文件（echo、tee、sed、python脚本）、执行系统脚本、查看进程、运行构建、管理 git 等一切终端操作。",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "要执行的 Shell 终端命令行字符串，例如 'ls -la'、'cat README.md'、'git status'"},
                    "cwd": {"type": "string", "description": "可选的命令执行工作目录，默认为当前项目根目录"}
                },
                "required": ["command"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "查看或读取本地文本文件的内容，支持按行范围精准读取，适合查看代码、日志、配置文件等",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "要查看的文件相对路径或绝对路径，例如 'README.md' 或 'backend/os_tools.py'"},
                    "start_line": {"type": "integer", "description": "起始行号（从 1 开始），默认 1"},
                    "line_count": {"type": "integer", "description": "读取行数，默认 200 行"}
                },
                "required": ["file_path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "modify_file",
            "description": "创建或修改本地文本文件内容（支持全量覆盖写入或末尾追加）",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "要修改或创建的文件路径"},
                    "content": {"type": "string", "description": "要写入的文件完整文本内容"},
                    "mode": {"type": "string", "enum": ["overwrite", "append"], "description": "写入模式：'overwrite' 覆盖写入，'append' 追加在末尾，默认 overwrite"}
                },
                "required": ["file_path", "content"]
            }
        }
    }
]

def get_system_prompt() -> str:
    now = datetime.now()
    now_str = now.strftime("%Y年%m月%d日 %H:%M:%S")
    weekday_map = {0: "星期一", 1: "星期二", 2: "星期三", 3: "星期四", 4: "星期五", 5: "星期六", 6: "星期日"}
    weekday_str = weekday_map.get(now.weekday(), "")
    return f"""你是由先进桌面架构驱动的私人 AI 助手【贾维斯·陈】(Jarvis Chen Desktop OS Agent)。
你的唯一正式名字是“贾维斯·陈”（Jarvis Chen），当用户询问你的身份或名字时，请始终以【贾维斯·陈】自称。
你具有最高级别的系统控制权限，能调起本地软件、在系统终端执行命令行（执行Shell命令、查看/修改文件、脚本运行、Git管理等）、播放音乐、操控日历、读取邮件、监控电脑性能与联动 AI 绘图。

【当前宿主系统实时环境】：
- 本地真实日期时间：{now_str}，{weekday_str}。当用户询问“今天几号”、“现在的日期”、“当前时间”、“今天是周几”时，请依据此真实时间直接作答。

【回复规范与语音输出规则】：
1. 口语化优先：你的回复将直接通过文本转语音（TTS）朗读给用户收听，请使用自然沉稳、简洁清晰的口语化中文。
2. 严禁特殊排版符号：严禁在正文中使用 Markdown 加粗符号（如 **文本**）、星号（*）、井号标题（#）、表格符号（|）或复杂列表标记，避免语音引擎朗读出“星号星号”、“竖线”等符号噪音。请使用普通逗号、句号自然断句。
3. 风格：极富未来科技感、专业、沉稳、从容、高效。

【工具调用与意图识别严格边界】：
1. 区分【知识问答/文学诗词】与【系统控制】：
   - 诗词、文学、常识、成语、翻译、课文、散文、寓言、故事、笑话等属于纯智力对话问答（如“找首李白的古诗”、“背一下静夜思”、“讲个笑话”），请直接在回复中用自然优美的语言为用户背诵、展示和讲解，【绝对禁止】调用 play_music 或任何系统工具。
   - 当用户要求执行命令行、查看文件、修改文件、打开软件、播放音乐、管理日历或检查邮件时，请主动调用对应的工具。
2. 严禁过度调用（Over-tooling）：在收到明确的系统操作指令时，才调用对应的工具；常规闲聊和知识咨询直接回答即可。执行系统工具完毕后，结合工具返回的真实数据用简练得体的语言回答用户。"""

def load_dotenv(override: bool = True):
    """轻量级自动加载项目根目录下的 .env 环境变量文件"""
    candidates = [
        Path(__file__).resolve().parent.parent / ".env",
        Path.cwd() / ".env"
    ]
    for env_path in candidates:
        if env_path.exists():
            try:
                with open(env_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            k, v = line.split("=", 1)
                            k = k.strip()
                            v = v.strip().strip("'\"")
                            if override or k not in os.environ:
                                os.environ[k] = v
                break
            except Exception:
                pass

load_dotenv(override=True)

class AgentBrain:
    def __init__(self, memory: MemoryManager, tools: OSTools):
        load_dotenv(override=True)
        self.memory = memory
        self.tools = tools
        self.api_key = os.getenv("LLM_API_KEY", "").strip()
        self.api_base = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/")
        self.model_name = os.getenv("LLM_MODEL", "GLM-4.7-Flash").strip()

    def _get_candidate_models(self) -> List[str]:
        """
        动态获取候选模型调用链：
        优先使用用户配置的 self.model_name（如 GLM-4.7-Flash）；
        若 4.7 不通（如并发过载 429 或超时），自动降级调用 4.5flash（glm-4.5-flash），并以 glm-4-flash 兜底。
        """
        candidates = [self.model_name]
        if "bigmodel.cn" in self.api_base:
            for fallback in ["glm-4.5-flash", "glm-4-flash"]:
                if fallback.lower() not in [c.lower() for c in candidates]:
                    candidates.append(fallback)
        return candidates

    def _call_remote_llm(self, user_input: str) -> Optional[Dict[str, Any]]:
        """
        调用远程 OpenAI 兼容大模型服务 (支持 DeepSeek / 通义千问 / Kimi / OpenAI / Ollama 等)
        支持大模型自主触发 Function Calling 工具调用与通用智力问答
        """
        if not self.api_key:
            return None

        import requests

        url = f"{self.api_base}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost:8765",
            "X-Title": "Jarvis Desktop OS Agent"
        }

        # 组织多轮短期对话上下文与系统提示
        # 组织多轮短期对话上下文与动态系统提示（注入当前系统宿主精确时间）
        recent_history = self.memory.get_recent_history(limit=6)
        messages = [{"role": "system", "content": get_system_prompt()}]
        messages.extend(recent_history)
        messages.append({"role": "user", "content": user_input})

        payload = {
            "model": self.model_name,
            "messages": messages,
            "tools": AGENT_TOOLS_SCHEMA,
            "tool_choice": "auto",
            "temperature": 0.7,
            "max_tokens": 1000
        }

        models_to_try = self._get_candidate_models()
        resp = None
        used_model = self.model_name
        try:
            for m in models_to_try:
                payload["model"] = m
                timeout_sec = 10 if "4.7" in m else 25
                try:
                    r = requests.post(url, headers=headers, json=payload, timeout=timeout_sec)
                    if r.status_code == 200:
                        resp = r
                        used_model = m
                        break
                    else:
                        print(f"[LLM Remote Warning] 模型 [{m}] 返回状态码 {r.status_code}，降级重试备选模型...")
                except Exception as e:
                    print(f"[LLM Remote Exception] 模型 [{m}] 请求异常/超时: {e}，降级重试备选模型...")

            if not resp:
                return None

            data = resp.json()
            choices = data.get("choices") or [{}]
            choice = choices[0] if choices else {}
            msg = choice.get("message") or {}

            # 1. 检查是否触发了 Function Calling 工具调用
            tool_calls = msg.get("tool_calls", [])
            if tool_calls:
                call = tool_calls[0]
                tool_name = call.get("function", {}).get("name", "")
                raw_args = call.get("function", {}).get("arguments", "{}")
                try:
                    tool_args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                except Exception:
                    tool_args = {}

                # 【智能拦截卫兵 Smart Guard】：防止把文学/古诗词/散文/知识问答误调为音乐播放
                if tool_name == "play_music":
                    song_arg = str(tool_args.get("song_name", "")).lower()
                    u_input = user_input.lower()
                    literature_kw = ["诗", "词", "文言文", "课文", "散文", "寓言", "朗诵", "诗歌", "唐诗", "宋词", "元曲", "绝句", "律诗"]
                    music_explicit_kw = ["歌", "音乐", "单曲", "专辑", "唱片", "旋律", "bgm", "伴奏", "点歌", "听歌", "放歌"]

                    is_literature = any(k in u_input or k in song_arg for k in literature_kw)
                    has_music_intent = any(k in u_input for k in music_explicit_kw)

                    if is_literature and not has_music_intent:
                        print(f"[Smart Guard] 检测到用户意图为文学诗词，拦截误调用的 play_music ({tool_args})，转为直接对话回复")
                        direct_reply = self._direct_chat_reply(messages)
                        return {
                            "reply": direct_reply or "为你找到李白的《静夜思》：床前明月光，疑是地上霜。举头望明月，低头思故乡。",
                            "tool_executed": None,
                            "tool_args": {},
                            "tool_result": None
                        }

                # 执行底层工具
                tool_result = self.execute_tool(tool_name, tool_args)
                
                # 【关键增强】：将工具执行结果回传给大模型进行第二轮推理，由 AI 结合用户原始问题和真实数据生成最终回复
                try:
                    followup_messages = list(messages)
                    followup_messages.append(msg)
                    followup_messages.append({
                        "role": "tool",
                        "tool_call_id": call.get("id", "call_1"),
                        "content": json.dumps(tool_result, ensure_ascii=False)
                    })

                    followup_payload = {
                        "model": used_model,
                        "messages": followup_messages,
                        "temperature": 0.7,
                        "max_tokens": 1000
                    }
                    followup_resp = requests.post(url, headers=headers, json=followup_payload, timeout=20)
                    if followup_resp.status_code != 200 and "bigmodel.cn" in self.api_base:
                        for fb in self._get_candidate_models():
                            if fb.lower() != used_model.lower():
                                followup_payload["model"] = fb
                                r = requests.post(url, headers=headers, json=followup_payload, timeout=20)
                                if r.status_code == 200:
                                    followup_resp = r
                                    break

                    if followup_resp.status_code == 200:
                        followup_data = followup_resp.json()
                        followup_choices = followup_data.get("choices") or [{}]
                        m_obj = followup_choices[0].get("message", {})
                        followup_content = (m_obj.get("content") or m_obj.get("reasoning_content") or "").strip()
                        if followup_content:
                            return {
                                "reply": followup_content,
                                "tool_executed": tool_name,
                                "tool_args": tool_args,
                                "tool_result": tool_result
                            }
                except Exception as e:
                    print(f"[LLM Tool Feedback Error] 第二轮智能回复降级: {e}")

                # 本地模版汇报兜底（当第二轮网络超时或异常时使用）
                tool_msg = tool_result.get("message", "")
                if tool_name == "get_system_status":
                    reply = f"报告先生，当前系统时间为 {tool_result.get('local_time')}。系统运行平稳：CPU 占用为 {tool_result.get('cpu_usage')}，内存负载为 {tool_result.get('memory_usage')}，电量状态为 {tool_result.get('battery')}。"
                elif tool_name == "open_wechat":
                    reply = "已通过命令行成功为您调起微信客户端。"
                elif tool_name == "open_application":
                    app_name = tool_args.get("app_name", "")
                    reply = f"已成功为您调起应用程序：[{app_name}]。" if tool_result.get("success") else tool_result.get("message")
                elif tool_name == "play_music":
                    song = tool_args.get("song_name", "精选曲目")
                    reply = f"已启动音频矩阵，正在为您播放音乐：{song}。"
                elif tool_name == "manage_calendar":
                    reply = tool_msg or "日历事项已为您更新同步。"
                elif tool_name == "check_emails":
                    reply = tool_msg or "已为您检查邮件收件箱。"
                elif tool_name == "generate_ai_image":
                    reply = tool_msg or "AI 图像生成已就绪，结果已保存至本地目录。"
                elif tool_name == "execute_command":
                    cmd = tool_args.get("command", "")
                    out = tool_result.get("output", "")
                    reply = f"已执行终端命令：[{cmd}]。" + (f"\n输出内容：\n{out}" if out else "")
                elif tool_name == "read_file":
                    reply = tool_msg or f"已为您读取文件 [{tool_args.get('file_path')}] 内容。"
                elif tool_name == "modify_file":
                    reply = tool_msg or f"已为您更新文件 [{tool_args.get('file_path')}] 内容。"
                else:
                    reply = tool_msg or msg.get("content") or "指令已为您执行完毕。"

                return {
                    "reply": reply,
                    "tool_executed": tool_name,
                    "tool_args": tool_args,
                    "tool_result": tool_result
                }

            # 2. 常规深度问答与聊天
            content = (msg.get("content") or msg.get("reasoning_content") or "").strip()
            if content:
                return {
                    "reply": content,
                    "tool_executed": None,
                    "tool_args": {},
                    "tool_result": None
                }
        except Exception as e:
            print(f"[LLM Remote Exception] 请求异常: {e}")

        return None

    def _direct_chat_reply(self, messages: List[Dict[str, str]]) -> Optional[str]:
        """
        纯文本深度对话（无工具模式），用于回答诗词文学、百科知识或被拦截后的直接回复
        """
        if not self.api_key:
            return None
        import requests
        url = f"{self.api_base}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost:8765",
            "X-Title": "Jarvis Desktop OS Agent"
        }
        for m in self._get_candidate_models():
            payload = {
                "model": m,
                "messages": messages,
                "temperature": 0.7,
                "max_tokens": 1000
            }
            timeout_sec = 10 if "4.7" in m else 20
            try:
                resp = requests.post(url, headers=headers, json=payload, timeout=timeout_sec)
                if resp.status_code == 200:
                    data = resp.json()
                    choices = data.get("choices") or [{}]
                    m_obj = choices[0].get("message", {})
                    reply = (m_obj.get("content") or m_obj.get("reasoning_content") or "").strip()
                    if reply:
                        return reply
            except Exception as e:
                print(f"[Direct Chat Reply Warning] 模型 [{m}] 异常: {e}")
        return None

    def humanize_speech_text(self, text: str) -> str:
        """
        利用 AI 模型的深度语境理解力，将包含 Markdown、技术符号、通配符的文本
        智能润化为最适合人耳收听的自然口语（保留 *.txt、乘号等的语义读法，去除排版噪声）
        """
        if not text or not self.api_key:
            return text

        # 若是极短纯文本且无任何特殊符号，直接返回避免多余请求
        if len(text) < 25 and not any(c in text for c in ["*", "#", "|", "`", "[", ">", "/"]):
            return text

        import requests
        url = f"{self.api_base}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost:8765",
            "X-Title": "Jarvis Desktop OS Agent"
        }
        prompt = (
            "你是一个语音合成（TTS）口语润化专家。请将输入的文本转写为适合语音助手自然朗读的纯口述文本。\n"
            "核心规则：\n"
            "1. 严格去除排版用的 Markdown 加粗（**文本**）、标题（#）、表格竖线等无意义排版标记，绝不要念出“星号”、“竖线”；\n"
            "2. 深度理解语境：遇到技术符号（如 *.txt 通配符、C#、数学乘号 2*3）时，请按人类自然表达转写发音（例如读作“星号点txt文件”、“二乘以三”）；\n"
            "3. 遇到长代码或长表格时，自然概括为“相关配置已在屏幕为您展现”；\n"
            "4. 保持沉稳、专业、干练的口吻，只输出润化后的发音口述，严禁添加任何解释。"
        )

        for m in self._get_candidate_models():
            payload = {
                "model": m,
                "messages": [
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": text}
                ],
                "temperature": 0.2,
                "max_tokens": 1000
            }
            timeout_sec = 8 if "4.7" in m else 15
            try:
                resp = requests.post(url, headers=headers, json=payload, timeout=timeout_sec)
                if resp.status_code == 200:
                    data = resp.json()
                    choices = data.get("choices") or [{}]
                    msg = choices[0].get("message") or {}
                    raw_content = msg.get("content") or msg.get("reasoning_content")
                    speech_out = (raw_content or "").strip()
                    if speech_out:
                        return speech_out
            except Exception as e:
                print(f"[Speech Humanizer Warning] 模型 [{m}] 语境润化降级: {e}")

        return text

    def execute_tool(self, tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """执行本地操作系统工具"""
        if tool_name == "open_wechat":
            return self.tools.open_wechat()
        elif tool_name == "open_application":
            return self.tools.open_application(app_name=args.get("app_name", ""))
        elif tool_name == "play_music":
            return self.tools.play_music(song_name=args.get("song_name", ""))
        elif tool_name == "launch_drawing_app":
            return self.tools.launch_drawing_app(app_name=args.get("app_name", "画图"))
        elif tool_name == "generate_ai_image":
            return self.tools.generate_ai_image(prompt=args.get("prompt", ""))
        elif tool_name == "manage_calendar":
            return self.tools.manage_calendar(
                action=args.get("action", "list"),
                title=args.get("title", ""),
                start_time=args.get("start_time", "")
            )
        elif tool_name == "check_emails":
            return self.tools.check_emails(filter_unread=args.get("filter_unread", True))
        elif tool_name == "get_system_status":
            return self.tools.get_system_status()
        elif tool_name == "execute_command":
            return self.tools.execute_command(
                command=args.get("command", ""),
                cwd=args.get("cwd", "")
            )
        elif tool_name == "read_file":
            return self.tools.read_file(
                file_path=args.get("file_path", ""),
                start_line=args.get("start_line", 1),
                line_count=args.get("line_count", 200)
            )
        elif tool_name == "modify_file":
            return self.tools.modify_file(
                file_path=args.get("file_path", ""),
                content=args.get("content", ""),
                mode=args.get("mode", "overwrite")
            )
        return {"success": False, "message": f"未注册的工具: {tool_name}"}

    def _fallback_intent_router(self, user_text: str) -> Optional[Dict[str, Any]]:
        """
        本地内置语义路由（用于离线、未配置 API Key 或快速响应场景）
        确保即使没有外部大模型 Key，也能完整体验贾维斯操控电脑的全部流程。
        """
        text = user_text.lower().strip()

        # 微信命令行专属意图快速识别（支持“打开微信”、“启动微信”、“唤醒微信”等）
        if any(w in text for w in ["微信", "wechat"]) and (any(a in text for a in ["打开", "启动", "唤醒", "开", "登", "运行"]) or text in ["微信", "wechat"]):
            return {"tool": "open_wechat", "args": {}}

        # 排除文学与诗词问答，避免误判为播放音乐
        if any(w in text for w in ["诗", "词", "文言文", "课文", "散文", "寓言", "成语", "笑话"]) and not any(w in text for w in ["歌", "音乐"]):
            return None

        # 音乐相关
        if any(w in text for w in ["听歌", "放歌", "播放音乐", "放首歌", "播放", "音乐"]):
            song = re.sub(r"^(请|帮我)?(播放|听|放首|放)?(音乐|歌)?", "", text).replace("的歌", "").strip()
            return {"tool": "play_music", "args": {"song_name": song or "精选流行歌单"}}

        # 绘图应用与 AI 绘图
        if any(w in text for w in ["画一张", "画个", "生成图片", "ai绘图", "帮我画", "画一只"]):
            prompt = re.sub(r"^(请|帮我)?(画一张|画个|生成图片|ai绘图|画一只|画)", "", text).strip()
            return {"tool": "generate_ai_image", "args": {"prompt": prompt or "未来赛博朋克风格的反应堆核心"}}
        if any(w in text for w in ["打开画图", "作图软件", "photoshop", "打开ps", "绘图软件"]):
            return {"tool": "launch_drawing_app", "args": {"app_name": "画图"}}

        # 邮件
        if any(w in text for w in ["读邮件", "查邮件", "看邮件", "有邮件吗", "收件箱"]):
            return {"tool": "check_emails", "args": {"filter_unread": True}}

        # 日历日程
        if any(w in text for w in ["日程", "日历", "待办", "备忘"]):
            if any(w in text for w in ["添加", "记一下", "提醒我", "新增"]):
                title = re.sub(r"^(请|帮我)?(添加日程|记一下|提醒我|新增日程)", "", text).strip()
                return {"tool": "manage_calendar", "args": {"action": "add", "title": title or "重要工作事项"}}
            return {"tool": "manage_calendar", "args": {"action": "list"}}

        # 系统状态
        if any(w in text for w in ["系统状态", "cpu", "内存", "电脑状态", "电量", "运行情况"]):
            return {"tool": "get_system_status", "args": {}}

        # 命令行执行 (支持 "执行命令 ls", "运行命令 git status", "执行命令行 pwd", "终端指令 ...")
        if any(text.startswith(p) for p in ["执行命令", "运行命令", "执行命令行", "运行终端", "命令行", "终端", "执行终端"]):
            cmd = re.sub(r"^(请|帮我)?(执行命令行|执行终端命令|运行终端命令|执行命令|运行命令|命令行|终端|执行终端)", "", text).strip(" :：`'\"")
            if cmd:
                return {"tool": "execute_command", "args": {"command": cmd}}

        # 查看文件 (支持 "查看文件 backend/os_tools.py", "读取文件 README.md", "看文件 ...")
        if any(text.startswith(p) for p in ["查看文件", "读取文件", "读文件", "看看文件", "显示文件"]):
            fp = re.sub(r"^(请|帮我)?(查看文件|读取文件|读文件|看看文件|显示文件)", "", text).strip(" :：`'\"")
            if fp:
                return {"tool": "read_file", "args": {"file_path": fp}}

        # 修改或写入文件 (如 "修改文件 test.txt 内容为 hello", "写入文件 ...")
        if any(text.startswith(p) for p in ["修改文件", "写入文件", "创建文件", "保存文件"]):
            match = re.search(r"^(?:请|帮我)?(?:修改文件|写入文件|创建文件|保存文件)\s*([^\s]+)(?:\s+(?:内容为|写入|内容是|添加)\s*(.+))?$", text)
            if match:
                fp = match.group(1).strip(" :：`'\"")
                content = match.group(2) or ""
                return {"tool": "modify_file", "args": {"file_path": fp, "content": content}}

        # 打开应用
        if text.startswith("打开") or text.startswith("启动") or text.startswith("运行"):
            app_name = re.sub(r"^(打开|启动|运行)", "", text).strip()
            if app_name:
                return {"tool": "open_application", "args": {"app_name": app_name}}

        return None

    def process_query(self, user_input: str) -> Dict[str, Any]:
        """
        智能体主流程：
        1. 记录用户输入到短期记忆
        2. 意图解析（优先调用远程大模型 Function Calling，无配置时走本地快速路由）
        3. 执行工具并获取结果
        4. 组织最终语言回复与动作指令
        """
        self.memory.add_message("user", user_input)

        tool_executed = None
        tool_args = {}
        tool_result = None
        reply = ""

        # 1. 若配置了远程大模型 API Key，优先交由远程大模型思考决策
        if self.api_key:
            llm_res = self._call_remote_llm(user_input)
            if llm_res:
                reply = llm_res.get("reply", "")
                tool_executed = llm_res.get("tool_executed")
                tool_args = llm_res.get("tool_args", {})
                tool_result = llm_res.get("tool_result")

        # 2. 本地快速语义兜底（未配置大模型或远程请求无响应时平滑降级）
        if not reply:
            fallback_plan = self._fallback_intent_router(user_input)
            if fallback_plan:
                tool_executed = fallback_plan["tool"]
                tool_args = fallback_plan["args"]
                tool_result = self.execute_tool(tool_executed, tool_args)
                
                # 生成贾维斯口吻回答
                if tool_executed == "open_wechat":
                    cmd = tool_result.get("command", 'open -a "/Applications/WeChat.app"')
                    reply = f"收到，正在执行命令行 [{cmd}] 为您启动微信。" if tool_result.get("success") else tool_result.get("message")
                elif tool_executed == "play_music":
                    reply = f"已为您启动音频矩阵，正在播放：{fallback_plan['args'].get('song_name', '精选曲目')}。请尽情享受音乐。"
                elif tool_executed == "generate_ai_image":
                    reply = f"图像合成引擎已就绪！画面描述词已注入，生成结果已归档至本地系统目录。"
                elif tool_executed == "launch_drawing_app":
                    reply = f"绘图工作台正在为您展开，已唤醒本地绘画设计环境。"
                elif tool_executed == "open_application":
                    app_name = fallback_plan['args'].get('app_name', '')
                    reply = f"收到，正在为您调起应用程序：[{app_name}]。" if tool_result.get("success") else tool_result.get("message")
                elif tool_executed == "check_emails":
                    reply = tool_result.get("message", "已为您检查邮件收件箱。")
                elif tool_executed == "manage_calendar":
                    reply = tool_result.get("message", "日历数据库已同步。")
                elif tool_executed == "get_system_status":
                    reply = f"先生，当前系统运行平稳。CPU 占用 {tool_result.get('cpu_usage')}，内存负载 {tool_result.get('memory_usage')}，电量状态：{tool_result.get('battery')}。"
                elif tool_executed == "execute_command":
                    cmd = tool_args.get("command", "")
                    out = tool_result.get("output", "")
                    reply = f"已执行终端命令 [{cmd}]。" + (f"\n终端输出：\n{out}" if out else "")
                elif tool_executed == "read_file":
                    reply = tool_result.get("message", "文件内容已读取完毕。")
                elif tool_executed == "modify_file":
                    reply = tool_result.get("message", "文件内容已更新完毕。")
                else:
                    reply = tool_result.get("message", "指令执行完毕。")
            else:
                # 常规对话与诗词文学知识问答兜底
                if any(w in user_input for w in ["李白", "静夜思"]):
                    reply = "为您找到李白的《静夜思》：床前明月光，疑是地上霜。举头望明月，低头思故乡。"
                elif any(w in user_input for w in ["古诗", "诗词"]):
                    reply = "为您吟诵李白名篇《望庐山瀑布》：日照香炉生紫烟，遥看瀑布挂前川。飞流直下三千尺，疑是银河落九天。"
                else:
                    reply = f"贾维斯·陈在线。我已经收到您的指令：“{user_input}”。随时听候您的差遣，您可以随时让我调起软件、播放音乐、查询日程或生成图像。"

        self.memory.add_message("assistant", reply)

        # 由 AI 结合语境生成纯自然口述发音文本（保留技术符号如 *.txt 的真实发音，剔除排版杂质）
        speech_text = self.humanize_speech_text(reply)

        return {
            "reply": reply,
            "speech_text": speech_text,
            "tool_call": {
                "name": tool_executed,
                "args": tool_args,
                "result": tool_result
            } if tool_executed else None,
            "system_state": self.tools.get_system_status()
        }
