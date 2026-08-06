import {
  app,
  BrowserWindow,
  dialog,
  ipcMain,
  Menu,
  nativeImage,
  powerSaveBlocker,
  screen,
  session as electronSession,
  shell as electronShell,
  Tray,
} from "electron";
import electronUpdater from "electron-updater";
import path from "node:path";
import { spawn } from "node:child_process";
import { EventEmitter } from "node:events";
import { fileURLToPath } from "node:url";
import { WorkerClient } from "./worker-client.js";
import {
  bootstrapWorkerConfig,
  loadWorkerLocator,
} from "./worker-bootstrap.js";
import { applyWorkerSettings } from "./worker-settings.js";
import { createRuntimeState } from "./runtime-state.js";
import { configureSingleInstance } from "./single-instance.js";
import { writeDiagnosticFile } from "./diagnostics.js";
import {
  applyAutoLaunch,
  loadSettings,
  loadWorkerCoreSettings,
  saveSettings as persistSettings,
  validateAutoLaunchValue,
  validateSettingsPatch,
} from "./settings.js";
import { setAutoLaunchAfterBootstrap } from "./settings-save.js";
import { createBindingService } from "./binding-service.js";
import { BindingController } from "./binding-controller.js";
import {
  createPassportAuthenticator,
  getPassportWindowLayout,
} from "./passport-login.js";
import { resolveDeviceNo } from "./backend.js";
import { clampFloatingPosition } from "./floating-drag.js";
import { createUpdateController } from "./update-manager.js";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const rendererUrl = process.env.ELECTRON_RENDERER_URL;
const { autoUpdater } = electronUpdater;

let mainWindow;
let floatingBallWindow;
let tray;
let recorderState = "idle";
let floatingDragOffset = null;
let floatingBallReady = false;
let pendingFloatingShow = false;
let recordingPowerBlockerId = null;
let supervisor;
let workerSnapshot = {
  recording: "idle",
  upload: "clear",
  health: "healthy",
  pending: 0,
};
let settings = {
  autoLaunch: false,
  autoRecordEnabled: true,
  inputDevice: "default",
  dataRoot: "",
  apiRoutes: {},
};
let autoLaunchStatus = {
  desired: false,
  actual: null,
  status: "unverified",
  error: null,
};
let workerLocation = null;
const bindingServiceMode =
  process.env.BINDING_SERVICE_MODE === "mock" ? "mock" : "remote";
let bindingService;
let bindingController;
let updateController;
let updateState = {
  status: "unsupported",
  currentVersion: "",
  availableVersion: "",
  percent: 0,
  error: "",
};

function isScreenPoint(point) {
  return Number.isFinite(point?.x) && Number.isFinite(point?.y);
}

function initializeBindingController() {
  let authenticate;
  if (bindingServiceMode === "remote") {
    const passportSession = electronSession.fromPartition(
      "classroom-recorder-passport"
    );
    authenticate = createPassportAuthenticator({
      browserSession: passportSession,
      createWindow: () => {
        const parentBounds = mainWindow?.getBounds();
        const display = parentBounds
          ? screen.getDisplayMatching(parentBounds)
          : screen.getPrimaryDisplay();
        const passportLayout = getPassportWindowLayout(display.workAreaSize);

        return new BrowserWindow({
          width: passportLayout.width,
          height: passportLayout.height,
          useContentSize: true,
          resizable: true,
          maximizable: true,
          center: true,
          parent: mainWindow,
          modal: false,
          show: true,
          title: "登录众享教育 Passport",
          autoHideMenuBar: true,
          webPreferences: {
            partition: "classroom-recorder-passport",
            contextIsolation: true,
            nodeIntegration: false,
            sandbox: true,
            zoomFactor: passportLayout.zoomFactor,
          },
        });
      },
    });
  }
  bindingService = createBindingService({
    mode: bindingServiceMode,
    authenticate,
    getApiRoutes: () => settings.apiRoutes,
  });
  bindingController = new BindingController({
    service: bindingService,
    resolveDeviceNo: () =>
      process.env.ELECTRON_SMOKE_TEST ? "020000000001" : resolveDeviceNo(),
    getSnapshot: () => workerSnapshot,
    sendWorkerCommand: (command, payload) => {
      if (!supervisor) {
        const error = new Error("录音服务尚未连接，请先选择数据目录");
        error.code = "WORKER_UNAVAILABLE";
        throw error;
      }
      return supervisor.sendCommand(command, payload);
    },
  });
}
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
  if (app.isPackaged)
    return path.join(process.resourcesPath, "build", iconName);
  return path.join(__dirname, "../build", iconName);
}

function getTrayIcon() {
  const icon = nativeImage.createFromPath(getIconPath());
  return icon.isEmpty()
    ? nativeImage.createEmpty()
    : icon.resize({ width: 18, height: 18 });
}

function createMainWindow() {
  mainWindow = new BrowserWindow({
    width: 1024,
    height: 640,
    minWidth: 880,
    minHeight: 560,
    useContentSize: true,
    resizable: true,
    maximizable: true,
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
    floatingBallWindow.loadFile(
      path.join(__dirname, "../dist/renderer/index.html"),
      { hash: "floating-ball" }
    );
  }

  floatingBallWindow.webContents.once("did-finish-load", () => {
    floatingBallWindow?.setTitle("");
    floatingBallWindow?.setFocusable(false);
    floatingBallWindow?.setBackgroundColor("#00000000");
    applyFloatingBallShape();
    floatingBallWindow?.webContents
      .executeJavaScript("document.title = ''")
      .catch(() => {});
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
        focusedBounds.y + 128
      );
    } else {
      const { workArea } = screen.getPrimaryDisplay();
      floatingBallWindow.setPosition(
        workArea.x + workArea.width - FLOATING_BALL_SIZE - 22,
        workArea.y + 128
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
  if (!floatingBallWindow || typeof floatingBallWindow.setShape !== "function")
    return;
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
      {
        label: "开始录音",
        enabled: recorderState !== "recording",
        click: () => supervisor?.send("start"),
      },
      {
        label: "暂停录音",
        enabled: recorderState === "recording",
        click: () => supervisor?.send("pause"),
      },
      {
        label: "停止录音",
        enabled: recorderState !== "idle",
        click: () => supervisor?.send("stop"),
      },
      { label: "补传队列", click: () => supervisor?.send("flush_queue") },
      { type: "separator" },
      {
        label: "退出",
        click: () => {
          app.isQuitting = true;
          app.quit();
        },
      },
    ])
  );
}

function showFloatingBallMenu() {
  Menu.buildFromTemplate([
    { label: "打开主界面", click: showMainWindow },
    { type: "separator" },
    {
      label: "开始录音",
      enabled: recorderState !== "recording",
      click: () => supervisor?.send("start"),
    },
    {
      label: "暂停录音",
      enabled: recorderState === "recording",
      click: () => supervisor?.send("pause"),
    },
    {
      label: "停止录音",
      enabled: recorderState !== "idle",
      click: () => supervisor?.send("stop"),
    },
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
  if (!workerLocation?.configPath)
    throw new Error("worker configuration is not bootstrapped");
  const configPath = workerLocation.configPath;
  let child;
  if (app.isPackaged) {
    child = spawn(
      path.join(process.resourcesPath, "worker", "ClassroomRecorderWorker.exe"),
      [],
      {
        cwd: path.join(process.resourcesPath, "ffmpeg"),
        env: { ...process.env, RECORDER_CONFIG_PATH: configPath },
        detached: true,
        stdio: "ignore",
      }
    );
  } else {
    child = spawn(
      process.env.RECORDER_PYTHON ||
        (process.platform === "win32" ? "python" : "python3"),
      ["-m", "worker.recorder_worker"],
      {
        cwd: path.join(__dirname, ".."),
        env: { ...process.env, RECORDER_CONFIG_PATH: configPath },
        detached: true,
        stdio: "ignore",
      }
    );
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
  broadcast("recorder:snapshot", {
    ...workerSnapshot,
    runtime,
    settings,
    autoLaunchStatus,
    dataRootLocked: Boolean(workerLocation),
    bindingServiceMode,
    appVersion: app.getVersion(),
    update: updateState,
  });
}

function initializeUpdateController() {
  const supported =
    app.isPackaged &&
    process.platform === "win32" &&
    !process.env.PORTABLE_EXECUTABLE_FILE;
  updateController = createUpdateController({
    updater: autoUpdater,
    currentVersion: app.getVersion(),
    supported,
    publish: (nextState) => {
      updateState = nextState;
      publishSnapshot({});
    },
    canInstall: () =>
      ["idle", "paused"].includes(createRuntimeState(workerSnapshot).recording),
    prepareInstall: async () => {
      if (supervisor) await supervisor.sendCommand("shutdown");
      supervisor?.disconnect();
      app.isQuitting = true;
    },
  });
  updateState = updateController.getState();
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
    await Promise.all([
      waitForWindowLoad(mainWindow),
      waitForWindowLoad(floatingBallWindow),
    ]);

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

    const floatingResult = await floatingBallWindow.webContents
      .executeJavaScript(`
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

    let bindingResult = { skipped: true };
    if (bindingServiceMode === "mock") {
      bindingResult = await mainWindow.webContents.executeJavaScript(`
        new Promise(async (resolve) => {
          const waitFor = async (selector, timeout = 5000) => {
            const started = Date.now();
            while (Date.now() - started < timeout) {
              const node = document.querySelector(selector);
              if (node) return node;
              await new Promise((next) => setTimeout(next, 50));
            }
            return null;
          };
          const openButton = await waitFor('[data-testid="open-binding"]');
          openButton?.click();
          const wizard = await waitFor('[data-testid="binding-wizard"]');
          const identityIcon = wizard?.querySelector('.qr-frame svg');
          const mockBadge = Array.from(wizard?.querySelectorAll('*') || []).some((node) => node.textContent?.trim() === '模拟数据');
          const bindingTypeStep = await waitFor('[data-binding-step="bindingType"]');
          const geometry = Array.from(wizard?.querySelectorAll('.binding-modal, .binding-workbench, .binding-identity-panel, .binding-step-panel') || [])
            .map((node) => ({ className: node.className, ...node.getBoundingClientRect().toJSON() }));
          const overflowing = geometry.filter((rect) => rect.left < -1 || rect.right > innerWidth + 1 || rect.top < -1 || rect.bottom > innerHeight + 1);
          wizard?.querySelector('[aria-label="关闭绑定向导"]')?.click();
          resolve({
            skipped: false,
            hasOpenButton: Boolean(openButton),
            hasWizard: Boolean(wizard),
            hasIdentityIcon: Boolean(identityIcon),
            hasMockBadge: mockBadge,
            reachedBindingType: Boolean(bindingTypeStep),
            overflowing
          });
        })
      `);
    }

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
      mainResult.width > 0 &&
      mainResult.height > 0 &&
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
      (bindingResult.skipped ||
        (bindingResult.hasOpenButton &&
          bindingResult.hasWizard &&
          bindingResult.hasIdentityIcon &&
          bindingResult.hasMockBadge &&
          bindingResult.reachedBindingType &&
          bindingResult.overflowing.length === 0)) &&
      settingsResult.hasModal &&
      settingsResult.footerVisible;

    console.log(
      "[electron-smoke]",
      JSON.stringify({
        main: mainResult,
        floating: floatingResult,
        binding: bindingResult,
        settings: settingsResult,
        passed,
      })
    );
    app.isQuitting = true;
    if (passed) app.quit();
    else app.exit(1);
  } catch (error) {
    console.error("[electron-smoke]", error);
    app.isQuitting = true;
    app.exit(1);
  }
}

if (hasSingleInstanceLock)
  app.whenReady().then(() => {
    const userDataDir = app.getPath("userData");
    workerLocation = loadWorkerLocator(app.getPath("userData"));
    settings = {
      ...loadSettings(workerLocation?.configPath),
      ...(workerLocation
        ? loadWorkerCoreSettings(workerLocation.configPath)
        : {}),
      dataRoot: workerLocation?.dataRoot || "",
    };
    initializeBindingController();

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
        if (!app.isQuitting)
          publishSnapshot({ health: "blocked", latestError: error.message });
      });
    };

    if (process.env.ELECTRON_SMOKE_TEST) {
      const smokeBindingMode = bindingServiceMode === "mock";
      let smokeWorkerSnapshot = smokeBindingMode
        ? {
            recording: "error",
            health: "binding_required",
            binding: null,
            dataRoot: "D:/SmokeRecorderData",
          }
        : { recording: "idle", health: "healthy" };
      attachWorkerClient(
        new WorkerClient({
          runtimeDir: "",
          readEndpoint: async () => ({
            host: "127.0.0.1",
            port: 0,
            token: "smoke",
          }),
          openSocket: async () => {
            const socket = new EventEmitter();
            socket.write = (value) => {
              const message = JSON.parse(value);
              if (message.token) {
                queueMicrotask(() =>
                  socket.emit(
                    "data",
                    Buffer.from(
                      `${JSON.stringify({ event: "ready", payload: smokeWorkerSnapshot })}\n`
                    )
                  )
                );
              } else if (message.command) {
                if (message.command === "apply_binding") {
                  smokeWorkerSnapshot = {
                    ...smokeWorkerSnapshot,
                    recording: "idle",
                    health: "healthy",
                    binding: message.payload,
                  };
                  queueMicrotask(() =>
                    socket.emit(
                      "data",
                      Buffer.from(
                        `${JSON.stringify({ event: "snapshot", payload: smokeWorkerSnapshot })}\n`
                      )
                    )
                  );
                }
                queueMicrotask(() =>
                  socket.emit(
                    "data",
                    Buffer.from(
                      `${JSON.stringify({ event: "command_result", payload: { id: message.id, success: true } })}\n`
                    )
                  )
                );
              }
            };
            socket.end = () => socket.emit("close");
            return socket;
          },
          launchWorker: () => {},
        })
      );
    } else if (workerLocation) {
      attachWorkerClient(
        new WorkerClient({
          runtimeDir: workerLocation.runtimeDir,
          launchWorker: spawnRecorderWorker,
        })
      );
    }
    autoLaunchStatus = setAutoLaunchAfterBootstrap({
      workerLocation,
      desired: settings.autoLaunch,
      apply: (desired) => applyAutoLaunch({ desired, app }),
    });
    initializeUpdateController();

    createMainWindow();
    createFloatingBallWindow();
    createTray();
    showFloatingBallWindow();
    runSmokeTest();

    if (!supervisor)
      publishSnapshot({
        health: "blocked",
        latestError: "请先选择非系统盘录音目录",
      });

    ipcMain.handle("recorder:get-snapshot", () => ({
      ...workerSnapshot,
      runtime: createRuntimeState(workerSnapshot),
      settings,
      autoLaunchStatus,
      dataRootLocked: Boolean(workerLocation),
      bindingServiceMode,
      appVersion: app.getVersion(),
      update: updateState,
    }));
    ipcMain.handle("app:check-for-updates", () => updateController.check());
    ipcMain.handle("app:install-update", () => updateController.install());
    ipcMain.handle("binding:create-session", () =>
      bindingController.createSession()
    );
    ipcMain.handle("binding:create-replacement-session", () =>
      bindingController.createReplacementSession()
    );
    ipcMain.handle("binding:get-session", (_event, sessionId) =>
      bindingController.getSession(sessionId)
    );
    ipcMain.handle("binding:list-grades", (_event, sessionId) =>
      bindingController.listGrades(sessionId)
    );
    ipcMain.handle("binding:list-classes", (_event, sessionId, query) =>
      bindingController.listClasses(sessionId, query)
    );
    ipcMain.handle("binding:confirm", (_event, sessionId, selection) =>
      bindingController.confirmBinding(sessionId, selection)
    );
    ipcMain.handle("binding:unbind", () => bindingController.unbindDevice());
    ipcMain.handle("recorder:start", () => supervisor?.send("start") ?? false);
    ipcMain.handle("recorder:pause", () => supervisor?.send("pause") ?? false);
    ipcMain.handle("recorder:stop", () => supervisor?.send("stop") ?? false);
    ipcMain.handle(
      "recorder:recheck",
      () => supervisor?.send("check_device_auth") ?? false
    );
    ipcMain.handle("system:open-date-time", async () => {
      if (process.platform !== "win32") return false;
      await electronShell.openExternal("ms-settings:dateandtime");
      return true;
    });
    ipcMain.handle(
      "recorder:flush",
      () => supervisor?.send("flush_queue") ?? false
    );
    ipcMain.handle("recorder:update-settings", async (_event, patch) => {
      const validatedPatch = validateSettingsPatch(patch);
      const result = await applyWorkerSettings({
        settings,
        patch: validatedPatch,
        workerLocation,
        supervisor,
        persistBootstrap: (candidate) =>
          bootstrapWorkerConfig({
            userDataDir: app.getPath("userData"),
            patch: candidate,
          }),
        attach: (location) => {
          workerLocation = location;
          attachWorkerClient(
            new WorkerClient({
              runtimeDir: location.runtimeDir,
              launchWorker: spawnRecorderWorker,
            })
          );
        },
      });
      settings = result.settings;
      workerLocation = result.workerLocation;
      persistSettings(workerLocation.configPath, {
        autoLaunch: settings.autoLaunch,
        autoRecordEnabled: settings.autoRecordEnabled,
        inputDevice: settings.inputDevice,
        apiRoutes: settings.apiRoutes,
      });
      publishSnapshot({});
      return settings;
    });
    ipcMain.handle("app:set-auto-launch", async (_event, enabled) => {
      const desired = validateAutoLaunchValue(enabled);
      const guarded = setAutoLaunchAfterBootstrap({
        workerLocation,
        desired,
        apply: (value) => applyAutoLaunch({ desired: value, app }),
      });
      if (guarded.status === "failed" && !workerLocation) return guarded;
      settings = { ...settings, autoLaunch: desired };
      persistSettings(workerLocation.configPath, {
        autoLaunch: desired,
        autoRecordEnabled: settings.autoRecordEnabled,
        inputDevice: settings.inputDevice,
        apiRoutes: settings.apiRoutes,
      });
      autoLaunchStatus = guarded;
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
      if (result.canceled || !result.filePath)
        return { ok: false, canceled: true };
      try {
        writeDiagnosticFile(result.filePath, {
          snapshot: workerSnapshot,
          settings,
          autoLaunchStatus,
          workerLocation,
          exportedAt: new Date().toISOString(),
          appVersion: app.getVersion(),
        });
        await dialog.showMessageBox(mainWindow, {
          type: "info",
          message: "诊断信息导出成功",
          detail: result.filePath,
        });
        return { ok: true, filePath: result.filePath };
      } catch (error) {
        await dialog.showMessageBox(mainWindow, {
          type: "error",
          message: "诊断信息导出失败",
          detail: error.message,
        });
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
    ipcMain.handle("floating:drag-start", (_event, point) => {
      if (!floatingBallWindow || !isScreenPoint(point)) return false;
      const bounds = floatingBallWindow.getBounds();
      floatingDragOffset = { x: point.x - bounds.x, y: point.y - bounds.y };
      return true;
    });
    ipcMain.handle("floating:drag-move", (_event, point) => {
      if (!floatingBallWindow || !floatingDragOffset || !isScreenPoint(point))
        return false;
      const bounds = floatingBallWindow.getBounds();
      const workArea = screen.getDisplayNearestPoint(point).workArea;
      const position = clampFloatingPosition({
        point,
        offset: floatingDragOffset,
        bounds,
        workArea,
      });
      floatingBallWindow.setPosition(position.x, position.y, false);
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
