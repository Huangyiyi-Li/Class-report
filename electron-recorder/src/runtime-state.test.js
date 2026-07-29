import assert from "node:assert/strict";
import test from "node:test";
import { createRuntimeState } from "./runtime-state.js";

test("offline upload does not replace recording state", () => {
  const state = createRuntimeState({
    recording: "recording",
    upload: "waiting_network",
    health: "healthy",
    pending: 12,
  });
  assert.equal(state.recording, "recording");
  assert.equal(state.upload, "waiting_network");
  assert.equal(state.pending, 12);
});

test("unsafe storage prevents recording label", () => {
  const state = createRuntimeState({
    recording: "recording",
    upload: "clear",
    health: "storage_unavailable",
  });
  assert.equal(state.recording, "recording_error");
  assert.equal(state.safe, false);
});

test("preserves worker binding and normalizes invalid pending count", () => {
  const binding = { schoolName: "示例学校", classroom: "一班录音设备" };
  const state = createRuntimeState({ binding, pending: "not-a-number" });
  assert.deepEqual(state.binding, binding);
  assert.equal(state.pending, 0);
});

test("disk health prevents recording even when service health is healthy", () => {
  const state = createRuntimeState({
    recording: "recording",
    health: "healthy",
    diskHealth: "disk_low",
  });
  assert.equal(state.health, "disk_low");
  assert.equal(state.recording, "recording_error");
});

test("unknown, disconnected, blocked and error health never infer recording safety", () => {
  for (const health of ["unknown", "disconnected", "blocked", "error"]) {
    const state = createRuntimeState({ recording: "recording", health });
    assert.equal(state.safe, false);
    assert.equal(state.recording, "recording_error");
  }
});
