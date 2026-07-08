import assert from "node:assert/strict";
import test from "node:test";
import { createRuntimeState } from "./runtime-state.js";

test("offline upload does not replace recording state", () => {
  const state = createRuntimeState({ recording: "recording", upload: "waiting_network", health: "healthy", pending: 12 });
  assert.equal(state.recording, "recording");
  assert.equal(state.upload, "waiting_network");
  assert.equal(state.pending, 12);
});

test("unsafe storage prevents recording label", () => {
  const state = createRuntimeState({ recording: "recording", upload: "clear", health: "storage_unavailable" });
  assert.equal(state.recording, "recording_error");
  assert.equal(state.safe, false);
});

test("preserves worker location and normalizes invalid pending count", () => {
  const location = { school_name: "示例学校", location_name: "一班" };
  const state = createRuntimeState({ location, pending: "not-a-number" });
  assert.deepEqual(state.location, location);
  assert.equal(state.pending, 0);
});

test("disk health prevents recording even when service health is healthy", () => {
  const state = createRuntimeState({ recording: "recording", health: "healthy", diskHealth: "disk_low" });
  assert.equal(state.health, "disk_low");
  assert.equal(state.recording, "recording_error");
});
