const { contextBridge, ipcRenderer } = require("electron");

// Sandboxed Electron preloads cannot require local modules. Keep this small
// decoder in the preload while the matching encoder remains in ipc-result.cjs.
const IPC_RESULT_MARKER = "classroom-recorder-ipc-result";

const unwrapResult = (result) => {
  if (result?.marker !== IPC_RESULT_MARKER) return result;
  if (result.ok) return result.value;
  const error = new Error(result.error?.message || "操作没有完成");
  Object.assign(error, result.error || {});
  throw error;
};

const invokeStructured = (channel, ...args) =>
  ipcRenderer.invoke(channel, ...args).then(unwrapResult);

contextBridge.exposeInMainWorld("recorderShell", {
  getSnapshot: () => ipcRenderer.invoke("recorder:get-snapshot"),
  startRecording: () => ipcRenderer.invoke("recorder:start"),
  pauseRecording: () => ipcRenderer.invoke("recorder:pause"),
  stopRecording: () => ipcRenderer.invoke("recorder:stop"),
  recheckRecording: () => ipcRenderer.invoke("recorder:recheck"),
  openSystemTimeSettings: () => ipcRenderer.invoke("system:open-date-time"),
  calibrateSystemTime: () => invokeStructured("system:calibrate-date-time"),
  flushQueue: () => ipcRenderer.invoke("recorder:flush"),
  listInputDevices: () => ipcRenderer.invoke("recorder:list-input-devices"),
  updateSettings: (patch) =>
    ipcRenderer.invoke("recorder:update-settings", patch),
  createBindingSession: () => invokeStructured("binding:create-session"),
  createReplacementBindingSession: () =>
    invokeStructured("binding:create-replacement-session"),
  resetBindingAuthentication: () =>
    invokeStructured("binding:reset-authentication"),
  getBindingSession: (sessionId) =>
    invokeStructured("binding:get-session", sessionId),
  listBindingGrades: (sessionId) =>
    invokeStructured("binding:list-grades", sessionId),
  listBindingClasses: (sessionId, query) =>
    invokeStructured("binding:list-classes", sessionId, query),
  confirmBinding: (sessionId, selection) =>
    invokeStructured("binding:confirm", sessionId, selection),
  replaceBinding: (sessionId, selection) =>
    invokeStructured("binding:replace", sessionId, selection),
  unbindDevice: () => invokeStructured("binding:unbind"),
  setAutoLaunch: (enabled) =>
    ipcRenderer.invoke("app:set-auto-launch", enabled),
  checkForUpdates: () => ipcRenderer.invoke("app:check-for-updates"),
  installUpdate: () => ipcRenderer.invoke("app:install-update"),
  openDataDir: () => ipcRenderer.invoke("recorder:open-data-dir"),
  chooseDataRoot: () => ipcRenderer.invoke("recorder:choose-data-root"),
  exportDiagnostics: () => ipcRenderer.invoke("recorder:export-diagnostics"),
  minimizeToTray: () => ipcRenderer.invoke("window:minimize-to-tray"),
  showMain: () => ipcRenderer.invoke("window:show-main"),
  showFloat: () => ipcRenderer.invoke("window:show-float"),
  openSettings: () => ipcRenderer.invoke("settings:open"),
  startFloatingDrag: (point) =>
    ipcRenderer.invoke("floating:drag-start", point),
  moveFloatingDrag: (point) => ipcRenderer.invoke("floating:drag-move", point),
  endFloatingDrag: () => ipcRenderer.invoke("floating:drag-end"),
  showFloatingMenu: () => ipcRenderer.invoke("floating:show-menu"),
  onOpenSettings: (callback) => {
    const listener = () => callback();
    ipcRenderer.on("settings:open", listener);
    return () => ipcRenderer.removeListener("settings:open", listener);
  },
  onSnapshot: (callback) => {
    const listener = (_event, payload) => callback(payload);
    ipcRenderer.on("recorder:snapshot", listener);
    return () => ipcRenderer.removeListener("recorder:snapshot", listener);
  },
});
