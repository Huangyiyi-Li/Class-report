export async function applyWorkerSettings({ settings, patch, workerLocation, persistBootstrap, attach, supervisor }) {
  const allowed = ["autoRecordEnabled", "inputDevice", "dataRoot"];
  const candidate = { ...settings, ...Object.fromEntries(Object.entries(patch || {}).filter(([key]) => allowed.includes(key))) };
  if (!workerLocation) {
    const location = persistBootstrap(candidate);
    const nextSettings = { ...candidate, dataRoot: location.dataRoot };
    attach(location);
    return { settings: nextSettings, workerLocation: location };
  }
  if (candidate.dataRoot !== workerLocation.dataRoot) {
    throw new Error("录音数据目录首次部署后不可修改，需重新部署");
  }
  if (!supervisor?.socket) throw new Error("录音服务未连接，请稍后重试");
  await supervisor.sendCommand("update_settings", candidate);
  return { settings: candidate, workerLocation };
}
