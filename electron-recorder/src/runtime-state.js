const SAFE_HEALTH = new Set(["healthy"]);

export function createRuntimeState(snapshot = {}) {
  const serviceHealth = snapshot.health || "healthy";
  const health =
    serviceHealth === "healthy" &&
    snapshot.diskHealth &&
    snapshot.diskHealth !== "healthy"
      ? snapshot.diskHealth
      : serviceHealth;
  const safe = SAFE_HEALTH.has(health);
  const pending = Number(snapshot.pending || 0);
  return {
    recording: safe ? snapshot.recording || "idle" : "recording_error",
    upload: snapshot.upload || "clear",
    health,
    pending: Number.isFinite(pending) ? pending : 0,
    binding: snapshot.binding || null,
    safe,
  };
}
