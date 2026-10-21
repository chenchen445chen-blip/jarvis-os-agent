const { app, BrowserWindow, globalShortcut, nativeImage } = require("electron");
const path = require("path");

let mainWindow = null;
const iconPngPath = path.join(__dirname, "assets", "icon.png");

function createWindow() {
  const appIcon = nativeImage.createFromPath(iconPngPath);
  if (process.platform === "darwin" && app.dock) {
    app.dock.setIcon(appIcon);
  }

  mainWindow = new BrowserWindow({
    width: 1280,
    height: 820,
    minWidth: 1024,
    minHeight: 700,
    title: "JARVIS · CHEN // OS - 桌面私人助理",
    icon: appIcon,
    titleBarStyle: "hiddenInset", // macOS 融合标题栏
    frame: true,
    transparent: false,
    backgroundColor: "#050b14",
    hasShadow: true,
    show: false,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      nodeIntegration: false,
      contextIsolation: true
    }
  });

  mainWindow.once("ready-to-show", () => {
    mainWindow.show();
    mainWindow.focus();
  });

  // 纯前端加载：开发模式加载上层 frontend，打包模式加载 extraResources 内置的前端
  const frontendPath = app.isPackaged
    ? path.join(process.resourcesPath, "frontend", "index.html")
    : path.resolve(__dirname, "../frontend/index.html");

  console.log("[Electron Frontend] 加载前端页面路径:", frontendPath);
  mainWindow.loadFile(frontendPath);

  // 注册全局呼出/隐藏快捷键：Command + Shift + J (Mac) 或 Ctrl + Shift + J (Win)
  globalShortcut.register("CommandOrControl+Shift+J", () => {
    if (!mainWindow) return;
    if (mainWindow.isVisible()) {
      mainWindow.hide();
    } else {
      mainWindow.show();
      mainWindow.focus();
    }
  });

  mainWindow.on("closed", () => {
    mainWindow = null;
  });
}

app.whenReady().then(() => {
  createWindow();

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    } else if (mainWindow) {
      mainWindow.show();
    }
  });
});

app.on("will-quit", () => {
  globalShortcut.unregisterAll();
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});
