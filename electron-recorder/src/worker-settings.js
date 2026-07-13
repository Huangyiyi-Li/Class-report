import { validateSettingsPatch } from "./settings.js";

export async function applyWorkerSettings({ settings, patch, workerLocation, persistBootstrap, attach, supervisor }) {
  const validatedPatch = validateSettingsPatch(patch);
  const candidate = { ...settings, ...validatedPatch };
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
