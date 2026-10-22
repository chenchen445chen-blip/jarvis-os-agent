/**
 * JARVIS / AIVY OS - 桌面级私有智能体主调度逻辑
 */

// DOM 元素引用
const clockEl = document.getElementById("hudClock");
const modeBadgeEl = document.getElementById("coreModeBadge");
const cpuBarEl = document.getElementById("cpuBar");
const cpuValEl = document.getElementById("cpuVal");
const memBarEl = document.getElementById("memBar");
const memValEl = document.getElementById("memVal");
const batteryValEl = document.getElementById("batteryVal");
const osValEl = document.getElementById("osVal");
const visualizerContainer = document.getElementById("audioVisualizer");
const speechBubbleEl = document.getElementById("speechBubble");
const bubbleTagEl = document.getElementById("bubbleTag");
const bubbleTextEl = document.getElementById("bubbleText");
const actionLogsEl = document.getElementById("actionLogs");
const eventListEl = document.getElementById("eventList");
const micBtnEl = document.getElementById("micBtn");
const micLabelEl = document.getElementById("micLabel");
const commandInputEl = document.getElementById("commandInput");
const sendBtnEl = document.getElementById("sendBtn");

// 前后端分离 API 基地址：优先读取全局配置，未配置时默认对齐本地独立后端服务
const API_BASE = window.JARVIS_CONFIG?.apiBase ?? (
  location.origin.startsWith("http") && location.port === "8765"
    ? ""
    : "http://127.0.0.1:8765"
);

// 1. 初始化 24 根频域柱
const BAR_COUNT = 24;
const bars = [];
for (let i = 0; i < BAR_COUNT; i++) {
  const bar = document.createElement("div");
  bar.className = "v-bar";
  visualizerContainer.appendChild(bar);
  bars.push(bar);
}

// 2. 实例化 3D 反应堆核心
const reactor = new JarvisReactor("particleCanvasContainer");

// 3. 实例化全双工语音管道
const speech = new SpeechPipeline({
  apiBase: API_BASE,
  wakeWord: "贾维斯·陈",
  onWake: (rawText) => {
    appendLog("INFO", `[WAKE-WORD] 探测到唤醒指令: "${rawText}"`);
    setAgentState("listening", "LISTENING 聆听指令中...");
  },
  onTranscript: (userText) => {
    if (!userText.trim()) return;
    appendLog("INFO", `[VOICE-IN] 用户指令: "${userText}"`);
    handleUserCommand(userText);
  },
  onAudioFrame: (intensity, freqBins) => {
    // 驱动 3D 反应堆粒子形变
    reactor.updateAudioIntensity(intensity);

    // 驱动 HUD 声波柱高度（使用 GPU 合成层 scaleY，杜绝引发任何父级与周围 DOM 抖动）
    for (let i = 0; i < BAR_COUNT; i++) {
      const val = freqBins[i] ?? 0;
      const scale = Math.max(0.12, Math.min(1.0, val / 255));
      bars[i].style.transform = `scaleY(${scale})`;
    }
  }
});

// 状态流转机
function setAgentState(state, label) {
  reactor.setState(state);
  modeBadgeEl.textContent = label;
  
  if (state === "listening") {
    modeBadgeEl.style.color = "#00ff66";
    modeBadgeEl.style.borderColor = "#00ff66";
  } else if (state === "thinking") {
    modeBadgeEl.style.color = "#bd00ff";
    modeBadgeEl.style.borderColor = "#bd00ff";
  } else if (state === "executing") {
    modeBadgeEl.style.color = "#ff9100";
    modeBadgeEl.style.borderColor = "#ff9100";
  } else {
    modeBadgeEl.style.color = "#00f3ff";
    modeBadgeEl.style.borderColor = "rgba(0, 243, 255, 0.4)";
  }
}

// 添加行动日志记录
function appendLog(type, message) {
  const timeStr = new Date().toTimeString().split(" ")[0];
  const item = document.createElement("div");
  item.className = `log-item ${type.toLowerCase()}`;
  item.innerHTML = `<span class="log-time">[${timeStr}]</span><span class="log-msg">${message}</span>`;
  actionLogsEl.appendChild(item);
  actionLogsEl.scrollTop = actionLogsEl.scrollHeight;
}

// 核心指令处理流程
async function handleUserCommand(command) {
  command = command?.trim() ?? "";
  if (!command) return;

  commandInputEl.value = "";
  setAgentState("thinking", "THINKING 规划分析中...");
  bubbleTagEl.textContent = "USER QUERY";
  bubbleTextEl.textContent = `“${command}”`;

  try {
    const res = await fetch(`${API_BASE}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query: command })
    });
    const data = await res.json();

    const reply = data?.reply ?? "指令已执行。";
    const toolCall = data?.tool_call;

    // 如果触发了本地底层工具调用
    if (toolCall) {
      setAgentState("executing", `EXECUTING 执行 [${toolCall.name}]`);
      appendLog("SUCCESS", `[TOOL CALL] 调度系统工具: ${toolCall.name} | 参数: ${JSON.stringify(toolCall.args)}`);
      
      const toolRes = toolCall.result ?? {};
      if (toolRes.file_path) {
        appendLog("SUCCESS", `[FILE] 目标文件: ${toolRes.file_path}`);
      }
      
      // 打开应用类工具专用状态提示
      if (["open_application", "open_wechat", "launch_drawing_app"].includes(toolCall.name)) {
        if (toolRes.success) {
          appendLog("SUCCESS", `[APP OPENED] ${toolRes.message ?? `已成功打开应用: ${toolRes.app ?? toolCall.args?.app_name}`}`);
        } else {
          appendLog("WARN", `[APP FAILED] ${toolRes.message ?? `未能启动应用: ${toolRes.app ?? toolCall.args?.app_name}`}`);
        }
      }

      if (toolCall.name === "execute_command" && toolRes.command) {
        appendLog("INFO", `[TERMINAL] $ ${toolRes.command}`);
        if (toolRes.output) {
          const firstLine = toolRes.output.split("\n")[0];
          appendLog(toolRes.success ? "SUCCESS" : "WARN", `[OUTPUT] ${firstLine}`);
        }
      }
    }

    // 贾维斯·陈汇报与语音播报（屏幕展示视觉富文本，语音朗读 AI 结合语境润化后的地道发音文本）
    const isAppFailure = Boolean(toolCall && ["open_application", "open_wechat", "launch_drawing_app"].includes(toolCall.name) && !toolCall.result?.success);
    bubbleTagEl.textContent = isAppFailure ? "JARVIS · CHEN 异常提示" : "JARVIS · CHEN 响应";
    bubbleTagEl.style.color = isAppFailure ? "#ff0055" : "";
    bubbleTextEl.textContent = reply;

    const speechSpokenText = data?.speech_text ?? reply;
    speech.speak(
      speechSpokenText,
      () => {
        // 播报中
        setAgentState("listening", "VOICE 语音汇报中...");
      },
      () => {
        // 播报完毕回到待机
        setAgentState("standby", "STANDBY 待机监控中");
      }
    );

    // 同步更新系统与日程
    if (data?.system_state) {
      updateSystemMetrics(data.system_state);
    }
    loadCalendarEvents();
  } catch (err) {
    appendLog("WARN", `通信异常: ${err?.message ?? "未知错误"}`);
    setAgentState("standby", "STANDBY 待机监控中");
  }
}

// 系统指标更新
function updateSystemMetrics(status) {
  if (!status) return;
  if (cpuBarEl) cpuBarEl.style.width = status.cpu_usage ?? "0%";
  if (cpuValEl) cpuValEl.textContent = status.cpu_usage ?? "--";
  if (memBarEl) memBarEl.style.width = (status.memory_usage?.split("%")[0] ?? "0") + "%";
  if (memValEl) memValEl.textContent = status.memory_usage ?? "--";
  if (batteryValEl) batteryValEl.textContent = status.battery ?? "正常";
  if (osValEl) osValEl.textContent = status.os ?? "System Active";
}

// 刷新日历日程
async function loadCalendarEvents() {
  try {
    const res = await fetch(`${API_BASE}/api/calendar`);
    const data = await res.json();
    const events = data?.events ?? [];

    if (events.length === 0) {
      eventListEl.innerHTML = `<div class="event-placeholder">暂无紧急日程</div>`;
      return;
    }

    eventListEl.innerHTML = events.map(e => `
      <div class="event-item">
        <div style="font-weight: bold; color: #00f3ff;">${e.title}</div>
        <div style="font-size: 11px; color: #7e9bb5;">${e.start_time} ${e.description ? '· ' + e.description : ''}</div>
      </div>
    `).join("");
  } catch (e) {}
}

// 快捷操作按钮触发
window.triggerQuickAction = function(action) {
  const actionsMap = {
    play_music: "播放周杰伦的流行音乐",
    draw: "帮我打开本地画图软件",
    calendar: "查看今天所有的日程安排",
    emails: "帮我读一下未读邮件",
    ai_paint: "帮我画一张具有未来感的光子反应堆概念图",
    status: "检查当前的电脑硬件系统状态",
    terminal: "执行命令 ls -la 查看当前项目文件"
  };
  const cmd = actionsMap[action] ?? action;
  handleUserCommand(cmd);
};

// 麦克风按键交互
let isMicActive = false;
micBtnEl.addEventListener("click", () => {
  isMicActive = !isMicActive;
  if (isMicActive) {
    micBtnEl.classList.add("active");
    micLabelEl.textContent = "全双工拾音中...";
    speech.startListening();
    setAgentState("listening", "LISTENING 聆听环境声...");
  } else {
    micBtnEl.classList.remove("active");
    micLabelEl.textContent = "语音拾音 (待命)";
    speech.stopListening();
    setAgentState("standby", "STANDBY 待机监控中");
  }
});

// 文字输入交互
sendBtnEl.addEventListener("click", () => {
  handleUserCommand(commandInputEl.value);
});
commandInputEl.addEventListener("keydown", (e) => {
  if (e.key === "Enter") {
    handleUserCommand(commandInputEl.value);
  }
});

// 时钟与硬件定时拉取
setInterval(() => {
  const now = new Date();
  clockEl.textContent = now.toTimeString().split(" ")[0];
}, 1000);

// 检测后端连接状态与拉取初始硬件状态
function checkBackendConnection() {
  fetch(`${API_BASE}/api/system_status`)
    .then(res => res.json())
    .then(status => {
      updateSystemMetrics(status);
      appendLog("SUCCESS", `[CORE ONLINE] 成功连接至独立智能体后端: ${API_BASE}`);
    })
    .catch(() => {
      appendLog("WARN", `[CORE OFFLINE] 未探测到后端服务 (${API_BASE})，请在终端独立运行: python3 start.py`);
    });
}

checkBackendConnection();
loadCalendarEvents();
