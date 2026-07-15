import assert from "node:assert/strict";
import test from "node:test";

import {
  MOCK_BINDING_TTL_MS,
  createBindingService,
} from "./binding-service.js";

const NOW = Date.parse("2026-07-15T08:00:00.000Z");

function createMock(overrides = {}) {
  let now = NOW;
  const service = createBindingService({
    mode: "mock",
    now: () => now,
    createId: () => "session-1",
    ...overrides,
  });
  return { service, advance: (milliseconds) => { now += milliseconds; } };
}

async function scannedSession(service) {
  await service.createSession({ deviceNo: "AABBCCDDEEFF" });
  await service.simulateScan("session-1");
}

test("mock session moves from waiting to scanned and confirmed", async () => {
  const { service } = createMock();
  const created = await service.createSession({ deviceNo: "AABBCCDDEEFF" });

  assert.equal(created.status, "waiting");
  assert.match(created.qrPayload, /session-1/);
  assert.equal((await service.simulateScan("session-1")).status, "scanned");

  const binding = await service.confirmBinding("session-1", {
    schoolId: 1001,
    locationType: "classroom",
    locationId: "room-101",
  });

  assert.deepEqual(binding, {
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
  });
  assert.equal((await service.getSession("session-1")).status, "confirmed");
});

test("studio binding has no class identity", async () => {
  const { service } = createMock();
  await scannedSession(service);

  const binding = await service.confirmBinding("session-1", {
    schoolId: 1001,
    locationType: "studio",
    locationId: "studio-main",
  });

  assert.equal(binding.locationName, "公共录播教室");
  assert.equal(binding.classId, "");
  assert.equal(binding.className, "");
});

test("catalog is available only after scan and filters by school and type", async () => {
  const { service } = createMock();
  await service.createSession({ deviceNo: "AABBCCDDEEFF" });

  await assert.rejects(service.listSchools("session-1"), { code: "BINDING_SESSION_NOT_SCANNED" });
  await service.simulateScan("session-1");

  const schools = await service.listSchools("session-1");
  assert.deepEqual(schools.map(({ id }) => id), [1001, 1002]);
  assert.deepEqual(
    (await service.listLocations("session-1", { schoolId: 1001, locationType: "classroom" })).map(({ id }) => id),
    ["room-101", "room-202"],
  );
  assert.deepEqual(
    (await service.listLocations("session-1", { schoolId: 1002, locationType: "studio" })).map(({ id }) => id),
    ["studio-west"],
  );
});

test("session expires without silently creating a replacement", async () => {
  const { service, advance } = createMock();
  await service.createSession({ deviceNo: "AABBCCDDEEFF" });
  advance(MOCK_BINDING_TTL_MS + 1);

  assert.equal((await service.getSession("session-1")).status, "expired");
  await assert.rejects(service.simulateScan("session-1"), { code: "BINDING_SESSION_EXPIRED" });
  await assert.rejects(service.listSchools("session-1"), { code: "BINDING_SESSION_EXPIRED" });
});

test("unknown sessions and illegal transitions have stable errors", async () => {
  const { service } = createMock();

  await assert.rejects(service.getSession("missing"), { code: "BINDING_SESSION_NOT_FOUND" });
  await scannedSession(service);
  await assert.rejects(service.simulateScan("session-1"), { code: "BINDING_SESSION_INVALID_STATE" });
  await service.confirmBinding("session-1", {
    schoolId: 1001,
    locationType: "studio",
    locationId: "studio-main",
  });
  await assert.rejects(service.confirmBinding("session-1", {
    schoolId: 1001,
    locationType: "studio",
    locationId: "studio-main",
  }), { code: "BINDING_SESSION_INVALID_STATE" });
});

test("selection must reference the mock catalog", async () => {
  const { service } = createMock();
  await scannedSession(service);

  await assert.rejects(service.confirmBinding("session-1", {
    schoolId: 9999,
    locationType: "classroom",
    locationId: "room-101",
  }), { code: "BINDING_SELECTION_INVALID" });
  await assert.rejects(service.confirmBinding("session-1", {
    schoolId: 1001,
    locationType: "classroom",
    locationId: "studio-main",
  }), { code: "BINDING_SELECTION_INVALID" });
});

test("service returns defensive copies", async () => {
  const { service } = createMock();
  const created = await service.createSession({ deviceNo: "AABBCCDDEEFF" });
  created.status = "confirmed";

  assert.equal((await service.getSession("session-1")).status, "waiting");
});

test("default remote mode fails closed and never exposes mock data", async () => {
  const service = createBindingService();

  await assert.rejects(service.createSession({ deviceNo: "AABBCCDDEEFF" }), {
    code: "BINDING_SERVICE_UNAVAILABLE",
  });
  await assert.rejects(service.listSchools("anything"), {
    code: "BINDING_SERVICE_UNAVAILABLE",
  });
  assert.equal(service.mode, "remote");
});
