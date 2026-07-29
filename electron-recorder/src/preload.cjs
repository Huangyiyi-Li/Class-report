const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("recorderShell", {
  getSnapshot: () => ipcRenderer.invoke("recorder:get-snapshot"),
  startRecording: () => ipcRenderer.invoke("recorder:start"),
  pauseRecording: () => ipcRenderer.invoke("recorder:pause"),
  stopRecording: () => ipcRenderer.invoke("recorder:stop"),
  recheckRecording: () => ipcRenderer.invoke("recorder:recheck"),
  openSystemTimeSettings: () => ipcRenderer.invoke("system:open-date-time"),
  flushQueue: () => ipcRenderer.invoke("recorder:flush"),
  updateSettings: (patch) =>
    ipcRenderer.invoke("recorder:update-settings", patch),
  createBindingSession: () => ipcRenderer.invoke("binding:create-session"),
  createReplacementBindingSession: () =>
    ipcRenderer.invoke("binding:create-replacement-session"),
  getBindingSession: (sessionId) =>
    ipcRenderer.invoke("binding:get-session", sessionId),
  listBindingGrades: (sessionId) =>
    ipcRenderer.invoke("binding:list-grades", sessionId),
  listBindingClasses: (sessionId, query) =>
    ipcRenderer.invoke("binding:list-classes", sessionId, query),
  confirmBinding: (sessionId, selection) =>
    ipcRenderer.invoke("binding:confirm", sessionId, selection),
  unbindDevice: () => ipcRenderer.invoke("binding:unbind"),
  setAutoLaunch: (enabled) =>
    ipcRenderer.invoke("app:set-auto-launch", enabled),
  openDataDir: () => ipcRenderer.invoke("recorder:open-data-dir"),
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
