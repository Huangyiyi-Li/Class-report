import assert from "node:assert/strict";
import test from "node:test";

import {
  bindingFlowReducer,
  canRebind,
  canSimulateScan,
  initialBindingFlow,
  normalizeSelection,
} from "./binding-flow.js";

test("flow opens with a waiting QR session and advances after scan", () => {
  let state = bindingFlowReducer(initialBindingFlow, { type: "OPEN" });
  assert.equal(state.phase, "creating");

  state = bindingFlowReducer(state, {
    type: "SESSION_UPDATED",
    session: { id: "session-1", status: "waiting", qrPayload: "mock://session-1" },
  });
  assert.equal(state.phase, "waiting");

  state = bindingFlowReducer(state, {
    type: "SESSION_UPDATED",
    session: { ...state.session, status: "scanned" },
  });
  assert.equal(state.phase, "scanned");

  state = bindingFlowReducer(state, { type: "SCHOOLS_LOADED", schools: [{ id: 1001, name: "星河实验学校" }] });
  assert.equal(state.phase, "school");
});

test("selection flow reaches review for classroom and studio", () => {
  let state = { ...initialBindingFlow, phase: "school", schools: [{ id: 1001 }] };
  state = bindingFlowReducer(state, { type: "SELECT_SCHOOL", schoolId: 1001 });
  assert.equal(state.phase, "locationType");
  state = bindingFlowReducer(state, { type: "SELECT_LOCATION_TYPE", locationType: "classroom" });
  assert.equal(state.phase, "loadingLocations");
  state = bindingFlowReducer(state, { type: "LOCATIONS_LOADED", locations: [{ id: "room-101", classId: "class-101", className: "一年级一班" }] });
  assert.equal(state.phase, "location");
  state = bindingFlowReducer(state, { type: "SELECT_LOCATION", locationId: "room-101" });
  assert.equal(state.phase, "review");

  assert.deepEqual(normalizeSelection({ locationType: "studio", classId: "stale", className: "stale" }), {
    locationType: "studio",
    classId: "",
    className: "",
  });
});

test("expired session waits for an explicit restart", () => {
  const expired = bindingFlowReducer({ ...initialBindingFlow, phase: "waiting" }, {
    type: "SESSION_UPDATED",
    session: { id: "session-1", status: "expired" },
  });
  assert.equal(expired.phase, "expired");

  const restarted = bindingFlowReducer(expired, { type: "RESTART" });
  assert.equal(restarted.phase, "creating");
  assert.equal(restarted.session, null);
});

test("confirmed binding is retained until the wizard closes", () => {
  const confirmed = bindingFlowReducer({ ...initialBindingFlow, phase: "confirming" }, {
    type: "CONFIRMED",
    binding: { locationId: "room-101" },
  });
  assert.equal(confirmed.phase, "confirmed");
  assert.equal(confirmed.binding.locationId, "room-101");
  assert.deepEqual(bindingFlowReducer(confirmed, { type: "CLOSE" }), initialBindingFlow);
});

test("rebind is available only when the recorder is idle", () => {
  assert.equal(canRebind({ recording: "idle" }), true);
  assert.equal(canRebind({ recordingState: "recording" }), false);
  assert.equal(canRebind({ runtime: { recording: "paused" } }), false);
});

test("remote mode never exposes the simulated scan action", () => {
  assert.equal(canSimulateScan("mock"), true);
  assert.equal(canSimulateScan("remote"), false);
  const failed = bindingFlowReducer(initialBindingFlow, {
    type: "ERROR",
    error: { code: "BINDING_SERVICE_UNAVAILABLE", message: "绑定服务尚未接入" },
  });
  assert.equal(failed.phase, "error");
  assert.equal(failed.error.code, "BINDING_SERVICE_UNAVAILABLE");
});
