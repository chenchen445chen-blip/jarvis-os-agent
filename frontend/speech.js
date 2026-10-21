/**
 * JARVIS / AIVY OS - 语音与感知管道 (STT, TTS, 唤醒词, Web Audio 频谱)
 */

class SpeechPipeline {
  constructor(options = {}) {
    this.apiBase = options.apiBase ?? window.JARVIS_CONFIG?.apiBase ?? "http://127.0.0.1:8765";
    this.wakeWord = options.wakeWord || "贾维斯·陈";
    this.onWake = options.onWake || (() => {});
    this.onTranscript = options.onTranscript || (() => {});
    this.onAudioFrame = options.onAudioFrame || (() => {});

    this.isListening = false;
    this.isPlayingTTS = false;
    this.audioContext = null;
    this.analyser = null;
    this.microphoneStream = null;
    this.currentAudio = null;
    this.currentAudioUrl = null;
    this.recognition = null;
    this.synth = window.speechSynthesis;
    this.synth?.getVoices?.();
    if (this.synth) {
      this.synth.onvoiceschanged = () => this.synth?.getVoices?.();
    }

    this.initRecognition();
  }

  // 初始化语音识别 (STT)
  initRecognition() {
    const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRec) {
      console.warn("当前浏览器不支持 Web Speech API，建议使用 Chrome/Edge 或 Electron");
      return;
    }

    this.recognition = new SpeechRec();
    this.recognition.continuous = true;
    this.recognition.interimResults = true;
    this.recognition.lang = "zh-CN";

    this.recognition.onresult = (event) => {
      let finalTranscript = "";
      let interimTranscript = "";

      for (let i = event.resultIndex; i < event.results.length; ++i) {
        const text = event.results[i][0].transcript;
        if (event.results[i].isFinal) {
          finalTranscript += text;
        } else {
          interimTranscript += text;
        }
      }

      const currentText = (finalTranscript || interimTranscript).trim();
      if (!currentText) return;

      // 检查唤醒词（支持“贾维斯·陈”、“贾维斯陈”、“贾维斯”）
      if (currentText.includes("贾维斯·陈") || currentText.includes("贾维斯陈") || currentText.includes(this.wakeWord) || currentText.includes("贾维斯")) {
        this.onWake(currentText);
        // 剥离唤醒词得到用户指令
        const cleaned = currentText.replace(/^(嘿|你好)?(贾维斯·陈|贾维斯陈|贾维斯)/i, "").trim();
        if (cleaned && finalTranscript) {
          this.onTranscript(cleaned);
        }
      } else if (finalTranscript) {
        this.onTranscript(finalTranscript);
      }
    };

    this.recognition.onerror = (e) => {
      console.error("STT Error:", e.error);
    };

    this.recognition.onend = () => {
      if (this.isListening) {
        // 持续保活监听
        try { this.recognition.start(); } catch (err) {}
      }
    };
  }

  // 开启全双工音频采集与频谱分析
  async startListening() {
    this.isListening = true;
    if (this.recognition) {
      try { this.recognition.start(); } catch (e) {}
    }

    // 挂载 Web Audio Analyser
    if (!this.audioContext) {
      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      this.audioContext = new AudioCtx();
    }
    if (this.audioContext.state === 'suspended') {
      await this.audioContext.resume();
    }

    try {
      this.microphoneStream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
      const source = this.audioContext.createMediaStreamSource(this.microphoneStream);
      this.analyser = this.audioContext.createAnalyser();
      this.analyser.fftSize = 64;
      source.connect(this.analyser);

      this.processAudioLoop();
    } catch (err) {
      console.warn("麦克风流捕获受限:", err.message);
    }
  }

  stopListening() {
    this.isListening = false;
    if (this.recognition) {
      try { this.recognition.stop(); } catch (e) {}
    }
    if (this.microphoneStream) {
      this.microphoneStream.getTracks().forEach(t => t.stop());
    }
  }

  // 频谱轮询回传
  processAudioLoop() {
    if ((!this.isListening && !this.isPlayingTTS) || !this.analyser) {
      this.onAudioFrame?.(0, Array(24).fill(0));
      return;
    }

    const dataArray = new Uint8Array(this.analyser.frequencyBinCount);
    this.analyser.getByteFrequencyData(dataArray);

    // 计算平均音量（归一化为 0.0 ~ 1.0）
    let sum = 0;
    for (let i = 0; i < dataArray.length; i++) {
      sum += dataArray[i];
    }
    const avg = sum / dataArray.length;
    const intensity = Math.min(1.0, avg / 128);

    this.onAudioFrame(intensity, Array.from(dataArray.slice(0, 24)));

    requestAnimationFrame(() => this.processAudioLoop());
  }

  // 纯文本兜底清洗：保护技术符号（如 *.txt、乘号），仅精准剥离 Markdown 加粗与排版标签
  cleanTextForSpeech(text) {
    if (!text) return "";
    return text
      // 去除长代码块 ```code```
      .replace(/```[\s\S]*?```/g, "相关内容已在屏幕展示。")
      // 行内代码 `code` -> 仅保留 code 文本本身
      .replace(/`([^`]+)`/g, "$1")
      // 精准剥离 Markdown 加粗与斜体语法标记：**重点** -> 重点（仅去外层标记，绝不误伤技术符号）
      .replace(/(^|[^\\])\*\*([^*]+)\*\*/g, "$1$2")
      .replace(/(^|[^\\])__([^_]+)__/g, "$1$2")
      // 智能保护并转写通配符，如 *.txt -> 星号点 txt
      .replace(/\*\.([a-zA-Z0-9_-]+)/g, "星号点$1")
      // 智能保护数学乘号 2 * 3 -> 2 乘以 3
      .replace(/(\d+)\s*\*\s*(\d+)/g, "$1 乘以 $2")
      // 去除 Markdown 标题符号 # 
      .replace(/^#{1,6}\s+/gm, "")
      // 去除列表前缀符号
      .replace(/^[\s]*[-+*]\s+/gm, "")
      // 去除表格分隔线与竖线
      .replace(/\|[-:\s|]+\|/g, "")
      .replace(/\|/g, "，")
      // 去除引用符 >
      .replace(/^>\s+/gm, "")
      // 去除链接语法 [文字](url) -> 仅保留文字
      .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1")
      // 将连续多换行转化为口语停顿
      .replace(/\n{2,}/g, "。")
      .replace(/\n/g, "，")
      .trim();
  }

  // 停止正在播放的语音
  stopSpeech() {
    if (this.currentAudio) {
      this.currentAudio.pause();
      this.currentAudio = null;
    }
    if (this.currentAudioUrl) {
      URL.revokeObjectURL(this.currentAudioUrl);
      this.currentAudioUrl = null;
    }
    this.synth?.cancel();
    this.isPlayingTTS = false;
    this.simulateTTSAudioActivity(false);
    this.onAudioFrame?.(0, Array(24).fill(0));
  }

  // 贾维斯·陈 语音播报（优先微软 Edge-TTS 影视级神经网络男声，支持本地兜底）
  async speak(text, onStart, onEnd) {
    this.stopSpeech();

    const cleanText = this.cleanTextForSpeech(text);
    if (!cleanText) return;

    // 优先调用后端微软 Edge-TTS 影视男声 (zh-CN-YunjianNeural)
    try {
      const res = await fetch(`${this.apiBase}/api/tts`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          text: cleanText,
          voice: "zh-CN-YunjianNeural",
          rate: "+0%",
          pitch: "-2Hz"
        })
      });

      if (!res.ok) {
        throw new Error(`TTS HTTP ${res.status}`);
      }

      const audioBlob = await res.blob();
      const audioUrl = URL.createObjectURL(audioBlob);
      this.currentAudioUrl = audioUrl;

      const audio = new Audio(audioUrl);
      this.currentAudio = audio;

      // 绑定 Web Audio 频谱分析器进行真实波形分析
      this.attachAudioElementToAnalyser(audio);

      audio.onplay = () => {
        this.isPlayingTTS = true;
        onStart?.();
        this.simulateTTSAudioActivity(true);
        this.processAudioLoop();
      };

      audio.onended = () => {
        this.isPlayingTTS = false;
        this.simulateTTSAudioActivity(false);
        if (this.currentAudioUrl) {
          URL.revokeObjectURL(this.currentAudioUrl);
          this.currentAudioUrl = null;
        }
        this.currentAudio = null;
        onEnd?.();
      };

      audio.onerror = () => {
        this.speakLocalFallback(cleanText, onStart, onEnd);
      };

      await audio.play();
    } catch (e) {
      // 网络或接口异常时，平滑降级至本地语音合成
      console.warn("[TTS Fallback] 云端合成暂不可用，降级至端侧语音:", e?.message);
      this.speakLocalFallback(cleanText, onStart, onEnd);
    }
  }

  // 挂载 Audio 到 Web Audio 频谱
  attachAudioElementToAnalyser(audio) {
    try {
      if (!this.audioContext) {
        const AudioCtx = window.AudioContext || window.webkitAudioContext;
        this.audioContext = new AudioCtx();
      }
      if (this.audioContext.state === "suspended") {
        this.audioContext.resume();
      }
      if (!this.analyser) {
        this.analyser = this.audioContext.createAnalyser();
        this.analyser.fftSize = 64;
      }
      const source = this.audioContext.createMediaElementSource(audio);
      source.connect(this.analyser);
      source.connect(this.audioContext.destination);
    } catch (err) {
      // 单源限制或静默由 simulateTTSAudioActivity 兜底
    }
  }

  // 本地 Web Speech 降级兜底方案
  speakLocalFallback(cleanText, onStart, onEnd) {
    if (!this.synth) {
      onEnd?.();
      return;
    }
    const utter = new SpeechSynthesisUtterance(cleanText);
    utter.lang = "zh-CN";
    utter.rate = 1.02;
    utter.pitch = 0.82;

    const voices = this.synth.getVoices();
    const preferredVoice = voices.find(v => 
      v.name.includes("Reed") || 
      v.name.includes("Rocko") || 
      v.name.includes("Eddy") ||
      v.name.includes("Yunxi")
    ) ?? voices.find(v => v.lang.includes("zh"));

    if (preferredVoice) {
      utter.voice = preferredVoice;
    }

    utter.onstart = () => {
      this.isPlayingTTS = true;
      onStart?.();
      this.simulateTTSAudioActivity(true);
    };

    utter.onend = () => {
      this.isPlayingTTS = false;
      this.simulateTTSAudioActivity(false);
      onEnd?.();
    };

    utter.onerror = () => {
      this.isPlayingTTS = false;
      this.simulateTTSAudioActivity(false);
      onEnd?.();
    };

    this.synth.speak(utter);
  }

  simulateTTSAudioActivity(active) {
    clearInterval(this._ttsTimer);
    if (!active) {
      this.onAudioFrame?.(0, Array(24).fill(0));
      return;
    }
    this._ttsTimer = setInterval(() => {
      const mockIntensity = 0.3 + Math.random() * 0.5;
      const mockBars = Array.from({ length: 24 }, () => Math.floor(Math.random() * 180));
      this.onAudioFrame?.(mockIntensity, mockBars);
    }, 80);
  }
}

