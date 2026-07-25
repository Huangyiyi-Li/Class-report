import assert from "node:assert/strict";
import test from "node:test";

import { BindingController } from "./binding-controller.js";

function createFixture(overrides = {}) {
  const calls = [];
  const binding = {
    deviceNo: "AABBCCDDEEFF",
    schoolId: 1001,
    schoolName: "星河实验学校",
    locationType: "classroom",
    locationId: "room-101",
    locationName: "一年级一班教室",
    classId: "class-101",
    className: "一年级一班",
    bindingSource: "mock",
    boundAt: "2026-07-15T08:00:00.000Z",
  };
  const service = {
    createSession: async (payload) => (calls.push(["createSession", payload]), { id: "session-1", status: "waiting" }),
    getSession: async (id) => (calls.push(["getSession", id]), { id, status: "scanned" }),
    simulateScan: async (id) => (calls.push(["simulateScan", id]), { id, status: "scanned" }),
    listSchools: async (id) => (calls.push(["listSchools", id]), [{ id: 1001, name: "星河实验学校" }]),
    listLocations: async (id, query) => (calls.push(["listLocations", id, query]), [{ id: "room-101" }]),
    confirmBinding: async (id, selection) => (calls.push(["confirmBinding", id, selection]), binding),
    ...overrides.service,
  };
  const workerCommands = [];
  const controller = new BindingController({
    service,
    resolveDeviceNo: () => "AABBCCDDEEFF",
    getSnapshot: () => ({ recording: "idle", binding: null }),
    sendWorkerCommand: async (command, payload) => workerCommands.push([command, payload]),
    ...overrides.controller,
  });
  return { controller, calls, workerCommands, binding };
}

test("controller creates a session for the resolved device identity", async () => {
  const { controller, calls } = createFixture();

  assert.deepEqual(await controller.createSession(), { id: "session-1", status: "waiting" });
  assert.deepEqual(calls, [["createSession", { deviceNo: "AABBCCDDEEFF" }]]);
});

test("rebind session reuses the persisted identity instead of following the current resolver", async () => {
  const { controller, calls } = createFixture({
    controller: {
      resolveDeviceNo: () => "112233445566",
      getSnapshot: () => ({
        recording: "idle",
        binding: { deviceNo: "AABBCCDDEEFF", locationId: "room-101" },
      }),
    },
  });

  await controller.createSession();

  assert.deepEqual(calls, [["createSession", { deviceNo: "AABBCCDDEEFF" }]]);
});

test("controller proxies session and catalog operations without exposing the worker", async () => {
  const { controller, calls } = createFixture();

  await controller.getSession("session-1");
  await controller.simulateScan("session-1");
  await controller.listSchools("session-1");
  await controller.listLocations("session-1", { schoolId: 1001, locationType: "classroom" });

  assert.deepEqual(calls, [
    ["getSession", "session-1"],
    ["simulateScan", "session-1"],
    ["listSchools", "session-1"],
    ["listLocations", "session-1", { schoolId: 1001, locationType: "classroom" }],
  ]);
});

test("confirmation sends exactly one canonical apply_binding command", async () => {
  const { controller, calls, workerCommands, binding } = createFixture();
  const selection = { schoolId: 1001, locationType: "classroom", locationId: "room-101" };

  const result = await controller.confirmBinding("session-1", selection);

  assert.deepEqual(result, binding);
  assert.deepEqual(calls, [["confirmBinding", "session-1", selection]]);
  assert.deepEqual(workerCommands, [["apply_binding", binding]]);
});

test("confirmation is rejected while recording before consuming the session", async () => {
  const { controller, calls, workerCommands } = createFixture({
    controller: { getSnapshot: () => ({ recording: "recording", binding: null }) },
  });

  await assert.rejects(controller.confirmBinding("session-1", {}), { code: "BINDING_REQUIRES_IDLE" });
  assert.deepEqual(calls, []);
  assert.deepEqual(workerCommands, []);
});

test("rebind requires idle but initial binding may proceed from binding_required", async () => {
  const blockedInitial = createFixture({
    controller: { getSnapshot: () => ({ recording: "error", health: "binding_required", binding: null }) },
  });
  await blockedInitial.controller.confirmBinding("session-1", {});

  const pausedRebind = createFixture({
    controller: { getSnapshot: () => ({ recording: "paused", binding: { locationId: "old" } }) },
  });
  await assert.rejects(pausedRebind.controller.confirmBinding("session-1", {}), { code: "BINDING_REQUIRES_IDLE" });
});

test("missing device identity and service failures propagate without fallback", async () => {
  const noDevice = createFixture({ controller: { resolveDeviceNo: () => "" } });
  await assert.rejects(noDevice.controller.createSession(), { code: "DEVICE_IDENTITY_UNAVAILABLE" });

  const unavailable = new Error("binding service is not configured");
  unavailable.code = "BINDING_SERVICE_UNAVAILABLE";
  const remote = createFixture({ service: { createSession: async () => { throw unavailable; } } });
  await assert.rejects(remote.controller.createSession(), { code: "BINDING_SERVICE_UNAVAILABLE" });
  assert.deepEqual(remote.calls, []);
});

test("worker command failures propagate instead of reporting a false confirmation", async () => {
  const workerError = new Error("worker rejected binding");
  const { controller } = createFixture({
    controller: { sendWorkerCommand: async () => { throw workerError; } },
  });

  await assert.rejects(controller.confirmBinding("session-1", {}), /worker rejected binding/);
});
