import { app, BrowserWindow, dialog, ipcMain, Menu, nativeImage, powerSaveBlocker, screen, shell as electronShell, Tray } from "electron";
import path from "node:path";
import { spawn } from "node:child_process";
import { EventEmitter } from "node:events";
import { fileURLToPath } from "node:url";
import { WorkerClient } from "./worker-client.js";
import { bootstrapWorkerConfig, loadWorkerLocator } from "./worker-bootstrap.js";
import { applyWorkerSettings } from "./worker-settings.js";
import { createRuntimeState } from "./runtime-state.js";
import { configureSingleInstance } from "./single-instance.js";
import { writeDiagnosticFile } from "./diagnostics.js";
import { applyAutoLaunch, loadSettings, loadWorkerCoreSettings, saveSettings as persistSettings, validateAutoLaunchValue, validateSettingsPatch } from "./settings.js";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const rendererUrl = process.env.ELECTRON_RENDERER_URL;

let mainWindow;
let floatingBallWindow;
let tray;
let recorderState = "idle";
let floatingDragOffset = null;
let floatingBallReady = false;
let pendingFloatingShow = false;
let recordingPowerBlockerId = null;
let supervisor;
let workerSnapshot = { recording: "idle", upload: "clear", health: "healthy", pending: 0 };
let settings = { autoLaunch: false, autoRecordEnabled: false, inputDevice: "default", dataRoot: "" };
let autoLaunchStatus = { desired: false, actual: null, status: "unverified", error: null };
let workerLocation = null;
const hasSingleInstanceLock = configureSingleInstance(app, () => {
  showMainWindow();
});

const STATE_LABELS = {
  idle: "未开始录音",
  recording: "录音中",
  paused: "已暂停",
  uploading: "上传中",
  network_error: "网络异常，等待补传",
  mic_error: "麦克风异常",
};

const FLOATING_BALL_SIZE = 62;

function getPreloadPath() {
  return path.join(__dirname, "preload.cjs");
}

function getIconPath() {
  const iconName = process.platform === "win32" ? "icon.ico" : "icon.png";
  if (app.isPackaged) return path.join(process.resourcesPath, "build", iconName);
  return path.join(__dirname, "../build", iconName);
}

function getTrayIcon() {
  const icon = nativeImage.createFromPath(getIconPath());
  return icon.isEmpty() ? nativeImage.createEmpty() : icon.resize({ width: 18, height: 18 });
}

function createMainWindow() {
  mainWindow = new BrowserWindow({
    width: 1180,
    height: 800,
    useContentSize: true,
    resizable: false,
    maximizable: false,
    title: "课堂录音采集助手",
    backgroundColor: "#f6f8fb",
    autoHideMenuBar: true,
    webPreferences: {
      preload: getPreloadPath(),
      contextIsolation: true,
      nodeIntegration: false,
      backgroundThrottling: false,
    },
  });
  if (rendererUrl) {
    mainWindow.loadURL(rendererUrl);
  } else {
    mainWindow.loadFile(path.join(__dirname, "../dist/renderer/index.html"));
  }

  mainWindow.on("close", (event) => {
    if (!app.isQuitting) {
      event.preventDefault();
      mainWindow.hide();
      showFloatingBallWindow();
    }
  });

}

function createFloatingBallWindow() {
  floatingBallReady = false;
  floatingBallWindow = new BrowserWindow({
    width: FLOATING_BALL_SIZE,
    height: FLOATING_BALL_SIZE,
    title: "",
    frame: false,
    transparent: true,
    focusable: false,
    resizable: false,
    alwaysOnTop: true,
    skipTaskbar: true,
    hasShadow: false,
    thickFrame: false,
    backgroundColor: "#00000000",
    show: false,
    webPreferences: {
      preload: getPreloadPath(),
      contextIsolation: true,
      nodeIntegration: false,
      backgroundThrottling: false,
    },
  });

  floatingBallWindow.on("page-title-updated", (event) => {
    event.preventDefault();
    floatingBallWindow?.setTitle("");
  });

  applyFloatingBallShape();

  if (rendererUrl) {
    floatingBallWindow.loadURL(`${rendererUrl}/#floating-ball`);
  } else {
    floatingBallWindow.loadFile(path.join(__dirname, "../dist/renderer/index.html"), { hash: "floating-ball" });
  }

  floatingBallWindow.webContents.once("did-finish-load", () => {
    floatingBallWindow?.setTitle("");
    floatingBallWindow?.setFocusable(false);
    floatingBallWindow?.setBackgroundColor("#00000000");
    applyFloatingBallShape();
    floatingBallWindow?.webContents.executeJavaScript("document.title = ''").catch(() => {});
    floatingBallReady = true;
    if (pendingFloatingShow) {
      pendingFloatingShow = false;
      floatingBallWindow?.showInactive();
    }
  });

  floatingBallWindow.on("closed", () => {
    floatingBallWindow = null;
    floatingBallReady = false;
    pendingFloatingShow = false;
  });
}

function showFloatingBallWindow() {
  if (!floatingBallWindow) createFloatingBallWindow();
  const focusedBounds = BrowserWindow.getFocusedWindow()?.getBounds();
  if (!floatingBallWindow.isVisible()) {
    if (focusedBounds) {
      floatingBallWindow.setPosition(
        focusedBounds.x + focusedBounds.width - FLOATING_BALL_SIZE - 22,
        focusedBounds.y + 128,
      );
    } else {
      const { workArea } = screen.getPrimaryDisplay();
      floatingBallWindow.setPosition(
        workArea.x + workArea.width - FLOATING_BALL_SIZE - 22,
        workArea.y + 128,
      );
    }
    applyFloatingBallShape();
    if (floatingBallReady) {
      floatingBallWindow.showInactive();
    } else {
      pendingFloatingShow = true;
    }
    updateTray();
  }
}

function applyFloatingBallShape() {
  if (!floatingBallWindow || typeof floatingBallWindow.setShape !== "function") return;
  const radius = Math.floor(FLOATING_BALL_SIZE / 2);
  const center = radius;
  const rects = [];
  for (let y = 0; y < FLOATING_BALL_SIZE; y += 1) {
    const dy = y - center + 0.5;
    const half = Math.sqrt(Math.max(0, radius * radius - dy * dy));
    const x = Math.max(0, Math.ceil(center - half));
    const right = Math.min(FLOATING_BALL_SIZE, Math.floor(center + half));
    rects.push({ x, y, width: Math.max(1, right - x), height: 1 });
  }
  try {
    floatingBallWindow.setShape(rects);
  } catch {
    // Some desktop compositors do not expose non-rectangular native windows.
  }
}

function showMainWindow() {
  mainWindow?.show();
  mainWindow?.focus();
  updateTray();
}

function hideFloatingBallWindow() {
  floatingBallWindow?.hide();
  updateTray();
}

function createTray() {
  tray = new Tray(getTrayIcon());
  tray.on("click", () => {
    showMainWindow();
  });
  tray.on("double-click", () => {
    showMainWindow();
  });
  updateTray();
}

function updateTray() {
  if (!tray) return;
  const stateLabel = STATE_LABELS[recorderState] || STATE_LABELS.idle;
  tray.setToolTip("课堂录音采集助手");
  tray.setContextMenu(
    Menu.buildFromTemplate([
      { label: `当前状态：${stateLabel}`, enabled: false },
      { type: "separator" },
      { label: "显示主窗口", click: showMainWindow },
      { label: "显示悬浮球", click: showFloatingBallWindow },
      {
        label: "隐藏悬浮球",
        enabled: Boolean(floatingBallWindow?.isVisible()),
        click: hideFloatingBallWindow,
      },
      {
        label: "维护设置",
        click: () => {
          showMainWindow();
          broadcast("settings:open", {});
        },
      },
      { type: "separator" },
      { label: "开始录音", enabled: recorderState !== "recording", click: () => supervisor?.send("start") },
      { label: "暂停录音", enabled: recorderState === "recording", click: () => supervisor?.send("pause") },
      { label: "停止录音", enabled: recorderState !== "idle", click: () => supervisor?.send("stop") },
      { label: "补传队列", click: () => supervisor?.send("flush_queue") },
      { type: "separator" },
      {
        label: "退出",
        click: () => {
          app.isQuitting = true;
          app.quit();
        },
      },
    ]),
  );
}

function showFloatingBallMenu() {
  Menu.buildFromTemplate([
    { label: "打开主界面", click: showMainWindow },
    { type: "separator" },
    { label: "开始录音", enabled: recorderState !== "recording", click: () => supervisor?.send("start") },
    { label: "暂停录音", enabled: recorderState === "recording", click: () => supervisor?.send("pause") },
    { label: "停止录音", enabled: recorderState !== "idle", click: () => supervisor?.send("stop") },
    { type: "separator" },
    {
      label: "退出",
      click: () => {
        app.isQuitting = true;
        app.quit();
      },
    },
  ]).popup({ window: floatingBallWindow || mainWindow });
}

function broadcast(channel, payload) {
  for (const win of [mainWindow, floatingBallWindow]) {
    if (win && !win.isDestroyed()) win.webContents.send(channel, payload);
  }
}

function keepRecordingAwake() {
  if (recordingPowerBlockerId !== null) return;
  recordingPowerBlockerId = powerSaveBlocker.start("prevent-app-suspension");
}

function releaseRecordingAwake() {
  if (recordingPowerBlockerId === null) return;
  if (powerSaveBlocker.isStarted(recordingPowerBlockerId)) {
    powerSaveBlocker.stop(recordingPowerBlockerId);
  }
  recordingPowerBlockerId = null;
}

function spawnRecorderWorker() {
  if (!workerLocation?.configPath) throw new Error("worker configuration is not bootstrapped");
  const configPath = workerLocation.configPath;
  let child;
  if (app.isPackaged) {
    child = spawn(path.join(process.resourcesPath, "worker", "ClassroomRecorderWorker.exe"), [], {
      cwd: path.join(process.resourcesPath, "ffmpeg"),
      env: { ...process.env, RECORDER_CONFIG_PATH: configPath },
      detached: true,
      stdio: "ignore",
    });
  } else {
    child = spawn(process.env.RECORDER_PYTHON || (process.platform === "win32" ? "python" : "python3"), ["-m", "worker.recorder_worker"], {
      cwd: path.join(__dirname, ".."),
      env: { ...process.env, RECORDER_CONFIG_PATH: configPath },
      detached: true,
      stdio: "ignore",
    });
  }
  child.unref();
  return child;
}

function publishSnapshot(snapshot) {
  workerSnapshot = { ...workerSnapshot, ...snapshot };
  const runtime = createRuntimeState(workerSnapshot);
  recorderState = runtime.recording;
  if (workerSnapshot.recording === "recording") keepRecordingAwake();
  else releaseRecordingAwake();
  updateTray();
  broadcast("recorder:snapshot", { ...workerSnapshot, runtime, settings, autoLaunchStatus, dataRootLocked: Boolean(workerLocation), appVersion: app.getVersion() });
}

function waitForWindowLoad(win) {
  return new Promise((resolve) => {
    if (!win || win.isDestroyed()) return resolve();
    if (!win.webContents.isLoading()) return resolve();
    win.webContents.once("did-finish-load", resolve);
  });
}

async function runSmokeTest() {
  if (!process.env.ELECTRON_SMOKE_TEST) return;

  try {
    await Promise.all([waitForWindowLoad(mainWindow), waitForWindowLoad(floatingBallWindow)]);

    const mainResult = await mainWindow.webContents.executeJavaScript(`
      Promise.resolve({
        bridge: Boolean(window.recorderShell),
        hasMainShell: Boolean(document.querySelector(".app-shell")),
        hasBubble: Boolean(document.querySelector(".floating-status-bubble")),
        hash: window.location.hash,
        width: window.innerWidth,
        height: window.innerHeight,
        scrollWidth: document.documentElement.scrollWidth,
        scrollHeight: document.documentElement.scrollHeight,
        overflowing: Array.from(document.querySelectorAll(".app-shell, .topbar, .layout, .record-card, .side-panel, .soft-card, .primary-actions, .top-actions"))
          .map((node) => {
            const rect = node.getBoundingClientRect();
            return {
              className: node.className,
              left: rect.left,
              right: rect.right,
              top: rect.top,
              bottom: rect.bottom
            };
          })
          .filter((rect) => rect.left < -1 || rect.right > window.innerWidth + 1 || rect.top < -1 || rect.bottom > window.innerHeight + 1)
      })
    `);

    const floatingResult = await floatingBallWindow.webContents.executeJavaScript(`
      Promise.resolve({
        bridge: Boolean(window.recorderShell),
        hasMainShell: Boolean(document.querySelector(".app-shell")),
        hasBubble: Boolean(document.querySelector(".floating-status-bubble")),
        hash: window.location.hash,
        width: window.innerWidth,
        height: window.innerHeight,
        htmlBackground: getComputedStyle(document.documentElement).backgroundColor,
        bodyBackground: getComputedStyle(document.body).backgroundColor,
        documentTitle: document.title,
        bubbleTag: document.querySelector(".floating-status-bubble")?.tagName || "",
        buttonTitle: document.querySelector(".floating-status-bubble")?.getAttribute("title") || "",
        buttonAriaLabel: document.querySelector(".floating-status-bubble")?.getAttribute("aria-label") || "",
        bubbleRole: document.querySelector(".floating-status-bubble")?.getAttribute("role") || "",
        scrollWidth: document.documentElement.scrollWidth,
        scrollHeight: document.documentElement.scrollHeight
      })
    `);

    const settingsResult = await mainWindow.webContents.executeJavaScript(`
      new Promise((resolve) => {
        document.querySelector('[aria-label="维护设置"]')?.click();
        setTimeout(() => {
          const details = document.querySelector(".diagnostics-panel");
          if (details) details.open = true;
          const footer = document.querySelector(".modal-footer");
          const modal = document.querySelector(".settings-modal");
          const footerRect = footer?.getBoundingClientRect();
          const modalRect = modal?.getBoundingClientRect();
          resolve({
            hasModal: Boolean(modal),
            hasFooter: Boolean(footer),
            footerVisible: Boolean(footerRect && modalRect && footerRect.bottom <= modalRect.bottom && footerRect.top >= modalRect.top),
            modalBottom: modalRect?.bottom || 0,
            footerBottom: footerRect?.bottom || 0
          });
        }, 120);
      })
    `);

    const passed =
      mainResult.bridge &&
      mainResult.hasMainShell &&
      !mainResult.hasBubble &&
      mainResult.width >= 1180 &&
      mainResult.height >= 800 &&
      mainResult.scrollWidth <= mainResult.width &&
      mainResult.scrollHeight <= mainResult.height &&
      mainResult.overflowing.length === 0 &&
      floatingResult.bridge &&
      floatingResult.hasBubble &&
      !floatingResult.hasMainShell &&
      floatingResult.width === FLOATING_BALL_SIZE &&
      floatingResult.height === FLOATING_BALL_SIZE &&
      floatingResult.htmlBackground === "rgba(0, 0, 0, 0)" &&
      floatingResult.bodyBackground === "rgba(0, 0, 0, 0)" &&
      floatingResult.documentTitle === "" &&
      floatingResult.bubbleTag === "DIV" &&
      floatingResult.buttonTitle === "" &&
      floatingResult.buttonAriaLabel === "" &&
      floatingResult.bubbleRole === "" &&
      floatingResult.scrollWidth <= FLOATING_BALL_SIZE &&
      floatingResult.scrollHeight <= FLOATING_BALL_SIZE &&
      settingsResult.hasModal &&
      settingsResult.footerVisible;

    console.log("[electron-smoke]", JSON.stringify({ main: mainResult, floating: floatingResult, settings: settingsResult, passed }));
    app.isQuitting = true;
    if (passed) app.quit();
    else app.exit(1);
  } catch (error) {
    console.error("[electron-smoke]", error);
    app.isQuitting = true;
    app.exit(1);
  }
}

if (hasSingleInstanceLock) app.whenReady().then(() => {
  const userDataDir = app.getPath("userData");
  workerLocation = loadWorkerLocator(app.getPath("userData"));
  settings = {
    ...loadSettings(workerLocation?.configPath),
    ...(workerLocation ? loadWorkerCoreSettings(workerLocation.configPath) : {}),
    dataRoot: workerLocation?.dataRoot || "",
  };

  const attachWorkerClient = (client) => {
    supervisor?.disconnect();
    supervisor = client;
    supervisor.on("ready", publishSnapshot);
    supervisor.on("snapshot", publishSnapshot);
    supervisor.on("error", (error) => {
      workerSnapshot = { ...workerSnapshot, latestError: error.message };
      publishSnapshot({});
    });
    publishSnapshot({ health: "blocked", latestError: "正在连接录音服务" });
    supervisor.start().catch((error) => {
      if (!app.isQuitting) publishSnapshot({ health: "blocked", latestError: error.message });
    });
  };

  if (process.env.ELECTRON_SMOKE_TEST) {
    attachWorkerClient(new WorkerClient({
        runtimeDir: "",
        readEndpoint: async () => ({ host: "127.0.0.1", port: 0, token: "smoke" }),
        openSocket: async () => {
          const socket = new EventEmitter();
          socket.write = (value) => {
            if (JSON.parse(value).token) queueMicrotask(() => socket.emit("data", Buffer.from('{"event":"ready","payload":{"recording":"idle","health":"healthy"}}\n')));
          };
          socket.end = () => socket.emit("close");
          return socket;
        },
        launchWorker: () => {},
      }));
  } else if (workerLocation) {
    attachWorkerClient(new WorkerClient({
        runtimeDir: workerLocation.runtimeDir,
        launchWorker: spawnRecorderWorker,
      }));
  }
  autoLaunchStatus = applyAutoLaunch({ desired: settings.autoLaunch, app });

  createMainWindow();
  createFloatingBallWindow();
  createTray();
  showFloatingBallWindow();
  runSmokeTest();

  if (!supervisor) publishSnapshot({ health: "blocked", latestError: "请先选择非系统盘录音目录" });

  ipcMain.handle("recorder:get-snapshot", () => ({ ...workerSnapshot, runtime: createRuntimeState(workerSnapshot), settings, autoLaunchStatus, dataRootLocked: Boolean(workerLocation), appVersion: app.getVersion() }));
  ipcMain.handle("recorder:start", () => supervisor?.send("start") ?? false);
  ipcMain.handle("recorder:pause", () => supervisor?.send("pause") ?? false);
  ipcMain.handle("recorder:stop", () => supervisor?.send("stop") ?? false);
  ipcMain.handle("recorder:flush", () => supervisor?.send("flush_queue") ?? false);
  ipcMain.handle("recorder:update-settings", async (_event, patch) => {
    const validatedPatch = validateSettingsPatch(patch);
    const result = await applyWorkerSettings({
      settings, patch: validatedPatch, workerLocation, supervisor,
      persistBootstrap: (candidate) => bootstrapWorkerConfig({ userDataDir: app.getPath("userData"), patch: candidate }),
      attach: (location) => {
        workerLocation = location;
        attachWorkerClient(new WorkerClient({ runtimeDir: location.runtimeDir, launchWorker: spawnRecorderWorker }));
      },
    });
    settings = result.settings;
    workerLocation = result.workerLocation;
    persistSettings(workerLocation.configPath, {
      autoLaunch: settings.autoLaunch,
      autoRecordEnabled: settings.autoRecordEnabled,
      inputDevice: settings.inputDevice,
    });
    publishSnapshot({});
    return settings;
  });
  ipcMain.handle("app:set-auto-launch", async (_event, enabled) => {
    const desired = validateAutoLaunchValue(enabled);
    settings = { ...settings, autoLaunch: desired };
    persistSettings(workerLocation.configPath, {
      autoLaunch: desired,
      autoRecordEnabled: settings.autoRecordEnabled,
      inputDevice: settings.inputDevice,
    });
    autoLaunchStatus = applyAutoLaunch({ desired, app });
    publishSnapshot({});
    return autoLaunchStatus;
  });
  ipcMain.handle("recorder:open-data-dir", () => {
    const dataDir = workerSnapshot.dataRoot || settings.dataRoot;
    if (dataDir) electronShell.openPath(dataDir);
    return true;
  });
  ipcMain.handle("recorder:export-diagnostics", async () => {
    const result = await dialog.showSaveDialog(mainWindow, {
      title: "导出诊断信息",
      defaultPath: `classroom-recorder-diagnostics-${new Date().toISOString().slice(0, 10)}.json`,
      filters: [{ name: "JSON", extensions: ["json"] }],
    });
    if (result.canceled || !result.filePath) return { ok: false, canceled: true };
    try {
      writeDiagnosticFile(result.filePath, {
        snapshot: workerSnapshot,
        settings,
        autoLaunchStatus,
        workerLocation,
        exportedAt: new Date().toISOString(),
        appVersion: app.getVersion(),
      });
      await dialog.showMessageBox(mainWindow, { type: "info", message: "诊断信息导出成功", detail: result.filePath });
      return { ok: true, filePath: result.filePath };
    } catch (error) {
      await dialog.showMessageBox(mainWindow, { type: "error", message: "诊断信息导出失败", detail: error.message });
      return { ok: false, error: error.message };
    }
  });
  ipcMain.handle("window:minimize-to-tray", () => {
    mainWindow?.hide();
    showFloatingBallWindow();
    return true;
  });
  ipcMain.handle("window:show-main", () => {
    showMainWindow();
    return true;
  });
  ipcMain.handle("window:show-float", () => {
    showFloatingBallWindow();
    return true;
  });
  ipcMain.handle("settings:open", () => {
    broadcast("settings:open", {});
    return true;
  });
  ipcMain.handle("floating:show-menu", () => {
    showFloatingBallMenu();
    return true;
  });
  ipcMain.handle("floating:drag-start", () => {
    if (!floatingBallWindow) return false;
    const cursor = screen.getCursorScreenPoint();
    const bounds = floatingBallWindow.getBounds();
    floatingDragOffset = { x: cursor.x - bounds.x, y: cursor.y - bounds.y };
    return true;
  });
  ipcMain.handle("floating:drag-move", () => {
    if (!floatingBallWindow || !floatingDragOffset) return false;
    const cursor = screen.getCursorScreenPoint();
    floatingBallWindow.setPosition(cursor.x - floatingDragOffset.x, cursor.y - floatingDragOffset.y);
    return true;
  });
  ipcMain.handle("floating:drag-end", () => {
    floatingDragOffset = null;
    return true;
  });

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createMainWindow();
    mainWindow?.show();
  });
});

app.on("window-all-closed", (event) => {
  event.preventDefault();
});

app.on("before-quit", () => {
  app.isQuitting = true;
  releaseRecordingAwake();
  supervisor?.disconnect();
});
