export function applyWorkerSettings({ settings, patch, workerLocation, persist, attach, supervisor }) {
  const allowed = ["autoRecordEnabled", "inputDevice", "dataRoot"];
  const candidate = { ...settings, ...Object.fromEntries(Object.entries(patch || {}).filter(([key]) => allowed.includes(key))) };
  const firstBootstrap = !workerLocation;
  const location = persist(candidate);
  const nextSettings = { ...candidate, dataRoot: location.dataRoot };
  if (firstBootstrap) attach(location);
  else if (supervisor?.socket) supervisor.send("update_settings", nextSettings);
  return { settings: nextSettings, workerLocation: location };
}
