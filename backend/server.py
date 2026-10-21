import os
import uvicorn
from pathlib import Path
from fastapi import FastAPI, HTTPException, Body
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import edge_tts
from pydantic import BaseModel
from typing import Dict, Any, Optional

from memory_manager import MemoryManager
from os_tools import OSTools
from agent_brain import AgentBrain

app = FastAPI(title="Jarvis / Aivy OS Agent API", version="1.0.0")

# 配置 CORS 允许桌面端与前端自由交互
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 依赖初始化
memory = MemoryManager()
tools = OSTools(memory)
brain = AgentBrain(memory, tools)

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"
DATA_DIR = BASE_DIR / "data"

# 挂载静态文件目录
if not (DATA_DIR / "generated_images").exists():
    (DATA_DIR / "generated_images").mkdir(parents=True, exist_ok=True)

app.mount("/static/generated", StaticFiles(directory=str(DATA_DIR / "generated_images")), name="generated_images")
app.mount("/app", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")

class ChatRequest(BaseModel):
    query: str
    wake_word: Optional[str] = "贾维斯"

class ToolDirectRequest(BaseModel):
    tool_name: str
    args: Dict[str, Any] = {}

@app.get("/")
def index():
    return {"status": "online", "agent": "Jarvis / Aivy Desktop Agent", "ui": "/app/"}

@app.post("/api/chat")
def handle_chat(req: ChatRequest):
    """核心对话与智能体指令分发接口"""
    if not req.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")
    result = brain.process_query(req.query.strip())
    return {
        "success": True,
        **result
    }

@app.get("/api/system_status")
def get_system_status():
    """实时系统硬件监测"""
    return tools.get_system_status()

@app.get("/api/calendar")
def get_calendar():
    """获取日程列表"""
    return tools.manage_calendar("list")

@app.post("/api/calendar")
def add_calendar(payload: Dict[str, Any] = Body(...)):
    """新增日程"""
    return tools.manage_calendar(
        action="add",
        title=payload.get("title", "新日程"),
        start_time=payload.get("start_time", ""),
        description=payload.get("description", "")
    )

@app.get("/api/emails")
def get_emails():
    """获取邮件摘要"""
    return tools.check_emails(filter_unread=True)

@app.post("/api/execute_tool")
def execute_direct_tool(req: ToolDirectRequest):
    """前端直接触发底层工具操作"""
    res = brain.execute_tool(req.tool_name, req.args)
    return {
        "success": True,
        "tool": req.tool_name,
        "result": res
    }

class TTSRequest(BaseModel):
    text: str
    voice: Optional[str] = "zh-CN-YunjianNeural"
    rate: Optional[str] = "+0%"
    pitch: Optional[str] = "-2Hz"

async def _stream_edge_tts(text: str, voice: str, rate: str, pitch: str):
    try:
        comm = edge_tts.Communicate(text, voice=voice, rate=rate, pitch=pitch)
        async for chunk in comm.stream():
            if chunk.get("type") == "audio":
                yield chunk.get("data", b"")
    except Exception as e:
        print(f"[TTS Error] Edge-TTS 语音流式合成异常: {e}")

@app.post("/api/tts")
async def generate_speech_post(req: TTSRequest):
    """微软 Edge-TTS 影视级神经网络语音合成（POST）"""
    clean_text = req.text.strip()
    if not clean_text:
        raise HTTPException(status_code=400, detail="Text cannot be empty")
    return StreamingResponse(
        _stream_edge_tts(clean_text, req.voice or "zh-CN-YunjianNeural", req.rate or "+0%", req.pitch or "-2Hz"),
        media_type="audio/mpeg"
    )

@app.get("/api/tts")
async def generate_speech_get(text: str, voice: str = "zh-CN-YunjianNeural", rate: str = "+0%", pitch: str = "-2Hz"):
    """微软 Edge-TTS 影视级神经网络语音合成（GET 流式音频）"""
    clean_text = text.strip()
    if not clean_text:
        raise HTTPException(status_code=400, detail="Text cannot be empty")
    return StreamingResponse(
        _stream_edge_tts(clean_text, voice, rate, pitch),
        media_type="audio/mpeg"
    )

if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=8765, reload=False)
