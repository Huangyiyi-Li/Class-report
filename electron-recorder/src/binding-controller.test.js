import assert from "node:assert/strict";
import test from "node:test";

import { BindingController } from "./binding-controller.js";

function createFixture(overrides = {}) {
  const calls = [];
  const binding = {
    deviceNo: "AABBCCDDEEFF",
    schoolId: 1001,
    schoolName: "星河实验学校",
    bindType: 1,
    classroom: "1.1班录音设备",
    classId: "101",
    className: "1.1班",
    bindingSource: "mock",
    boundAt: "2026-07-15T08:00:00.000Z",
  };
  const service = {
    createSession: async (payload) => (calls.push(["createSession", payload]), { id: "session-1", status: "authenticated" }),
    getSession: async (id) => (calls.push(["getSession", id]), { id, status: "authenticated" }),
    listGrades: async (id) => (calls.push(["listGrades", id]), [{ gradeCode: 1, gradeName: "一年级" }]),
    listClasses: async (id, query) => (calls.push(["listClasses", id, query]), [{ classId: 101, className: "1.1班" }]),
    confirmBinding: async (id, selection) => (calls.push(["confirmBinding", id, selection]), binding),
    unbindDevice: async (id) => (calls.push(["unbindDevice", id]), { success: true }),
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
  assert.equal((await controller.createSession()).status, "authenticated");
  assert.deepEqual(calls, [["createSession", { deviceNo: "AABBCCDDEEFF" }]]);
});

test("normal rebind keeps the persisted MAC when another adapter is available", async () => {
  const { controller, calls } = createFixture({
    controller: {
      resolveDeviceNo: () => "112233445566",
      getSnapshot: () => ({ recording: "idle", binding: { deviceNo: "AABBCCDDEEFF" } }),
    },
  });
  await controller.createSession();
  assert.deepEqual(calls, [["createSession", { deviceNo: "AABBCCDDEEFF" }]]);
});

test("explicit device replacement uses the currently resolved physical MAC", async () => {
  const { controller, calls } = createFixture({
    controller: {
      resolveDeviceNo: () => "112233445566",
      getSnapshot: () => ({ recording: "idle", binding: { deviceNo: "AABBCCDDEEFF" } }),
    },
  });
  await controller.createReplacementSession();
  assert.deepEqual(calls, [["createSession", { deviceNo: "112233445566" }]]);
});

test("controller proxies Passport-backed grade and class operations", async () => {
  const { controller, calls } = createFixture();
  await controller.getSession("session-1");
  await controller.listGrades("session-1");
  await controller.listClasses("session-1", { gradeCode: 1 });
  assert.deepEqual(calls, [
    ["getSession", "session-1"],
    ["listGrades", "session-1"],
    ["listClasses", "session-1", { gradeCode: 1 }],
  ]);
});

test("confirmation sends exactly one canonical apply_binding command", async () => {
  const { controller, calls, workerCommands, binding } = createFixture();
  const selection = { bindType: 1, classId: 101, className: "1.1班" };
  assert.deepEqual(await controller.confirmBinding("session-1", selection), binding);
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

test("unbind authenticates, calls the service, then clears the worker binding", async () => {
  const { controller, calls, workerCommands } = createFixture({
    controller: { getSnapshot: () => ({ recording: "idle", binding: { deviceNo: "AABBCCDDEEFF" } }) },
  });
  await controller.unbindDevice();
  assert.deepEqual(calls, [
    ["createSession", { deviceNo: "AABBCCDDEEFF" }],
    ["unbindDevice", "session-1"],
  ]);
  assert.deepEqual(workerCommands, [
    ["prepare_unbind", {}],
    ["clear_binding", {}],
  ]);
});

test("unbind failure leaves the worker in persisted safe-blocked state", async () => {
  const serviceError = Object.assign(new Error("server unavailable"), { code: "BINDING_REJECTED" });
  const { controller, workerCommands } = createFixture({
    service: { unbindDevice: async () => { throw serviceError; } },
    controller: { getSnapshot: () => ({ recording: "idle", binding: { deviceNo: "AABBCCDDEEFF" } }) },
  });
  await assert.rejects(controller.unbindDevice(), /server unavailable/);
  assert.deepEqual(workerCommands, [["prepare_unbind", {}]]);
});

test("rebind requires idle but initial binding may proceed from binding_required", async () => {
  const blockedInitial = createFixture({
    controller: { getSnapshot: () => ({ recording: "error", health: "binding_required", binding: null }) },
  });
  await blockedInitial.controller.confirmBinding("session-1", {});
  const pausedRebind = createFixture({
    controller: { getSnapshot: () => ({ recording: "paused", binding: { bindType: 1 } }) },
  });
  await assert.rejects(pausedRebind.controller.confirmBinding("session-1", {}), { code: "BINDING_REQUIRES_IDLE" });
});

test("missing identity and service failures propagate without fallback", async () => {
  const noDevice = createFixture({ controller: { resolveDeviceNo: () => "" } });
  await assert.rejects(noDevice.controller.createSession(), { code: "DEVICE_IDENTITY_UNAVAILABLE" });
  const unavailable = Object.assign(new Error("not configured"), { code: "BINDING_SERVICE_UNAVAILABLE" });
  const remote = createFixture({ service: { createSession: async () => { throw unavailable; } } });
  await assert.rejects(remote.controller.createSession(), { code: "BINDING_SERVICE_UNAVAILABLE" });
});
