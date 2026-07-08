const UNSAFE_HEALTH = new Set([
  "storage_unavailable",
  "disk_low",
  "microphone_unavailable",
  "binding_required",
]);

export function createRuntimeState(snapshot = {}) {
  const serviceHealth = snapshot.health || "healthy";
  const health = serviceHealth === "healthy" && snapshot.diskHealth && snapshot.diskHealth !== "healthy"
    ? snapshot.diskHealth
    : serviceHealth;
  const safe = !UNSAFE_HEALTH.has(health);
  const pending = Number(snapshot.pending || 0);
  return {
    recording: safe ? (snapshot.recording || "idle") : "recording_error",
    upload: snapshot.upload || "clear",
    health,
    pending: Number.isFinite(pending) ? pending : 0,
    location: snapshot.location || null,
    safe,
  };
}
