const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("recorderShell", {
  getSnapshot: () => ipcRenderer.invoke("recorder:get-snapshot"),
  startRecording: () => ipcRenderer.invoke("recorder:start"),
  pauseRecording: () => ipcRenderer.invoke("recorder:pause"),
  stopRecording: () => ipcRenderer.invoke("recorder:stop"),
  flushQueue: () => ipcRenderer.invoke("recorder:flush"),
  updateSettings: (patch) => ipcRenderer.invoke("recorder:update-settings", patch),
  createBindingSession: () => ipcRenderer.invoke("binding:create-session"),
  getBindingSession: (sessionId) => ipcRenderer.invoke("binding:get-session", sessionId),
  simulateBindingScan: (sessionId) => ipcRenderer.invoke("binding:simulate-scan", sessionId),
  listBindingSchools: (sessionId) => ipcRenderer.invoke("binding:list-schools", sessionId),
  listBindingLocations: (sessionId, query) => ipcRenderer.invoke("binding:list-locations", sessionId, query),
  confirmBinding: (sessionId, selection) => ipcRenderer.invoke("binding:confirm", sessionId, selection),
  setAutoLaunch: (enabled) => ipcRenderer.invoke("app:set-auto-launch", enabled),
  openDataDir: () => ipcRenderer.invoke("recorder:open-data-dir"),
  exportDiagnostics: () => ipcRenderer.invoke("recorder:export-diagnostics"),
  minimizeToTray: () => ipcRenderer.invoke("window:minimize-to-tray"),
  showMain: () => ipcRenderer.invoke("window:show-main"),
  showFloat: () => ipcRenderer.invoke("window:show-float"),
  openSettings: () => ipcRenderer.invoke("settings:open"),
  startFloatingDrag: () => ipcRenderer.invoke("floating:drag-start"),
  moveFloatingDrag: () => ipcRenderer.invoke("floating:drag-move"),
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
