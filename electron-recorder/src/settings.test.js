import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import {
  applyAutoLaunch,
  loadSettings,
  loadWorkerCoreSettings,
  saveSettings,
  validateAutoLaunchValue,
  validateSettingsPatch,
} from "./settings.js";
import { PRODUCTION_API_ROUTES, TEST_API_ROUTES } from "./api-routes.js";

test("settings default to auto-launch disabled", () => {
  assert.equal(loadSettings(null).autoLaunch, false);
  assert.deepEqual(loadSettings(null).apiRoutes, TEST_API_ROUTES);
});

test("API routes persist with settings and are accepted by the worker patch boundary", () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "recorder-routes-"));
  const configPath = path.join(root, "worker-config.json");
  saveSettings(configPath, {
    autoLaunch: false,
    autoRecordEnabled: true,
    inputDevice: "default",
    apiRoutes: PRODUCTION_API_ROUTES,
  });
  assert.deepEqual(loadSettings(configPath).apiRoutes, PRODUCTION_API_ROUTES);
  assert.deepEqual(
    validateSettingsPatch({ apiRoutes: PRODUCTION_API_ROUTES }),
    { apiRoutes: PRODUCTION_API_ROUTES }
  );
});

test("preferences stay default before bootstrap and persist beside worker config", () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "recorder-data-"));
  const configPath = path.join(
    root,
    ".classroom-recorder",
    "worker-config.json"
  );
  fs.mkdirSync(path.dirname(configPath), { recursive: true });
  fs.writeFileSync(configPath, "{}", "utf8");
  assert.deepEqual(loadSettings(null), {
    autoLaunch: false,
    autoRecordEnabled: true,
    inputDevice: "default",
    apiRoutes: TEST_API_ROUTES,
  });
  saveSettings(configPath, {
    autoLaunch: true,
    autoRecordEnabled: false,
    inputDevice: "default",
  });
  assert.equal(
    fs.existsSync(path.join(path.dirname(configPath), "settings.json")),
    true
  );
  assert.equal(loadSettings(configPath).autoLaunch, true);
});

test("settings persist across a fresh load without worker or binding fields", () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "recorder-settings-"));
  const configPath = path.join(root, "worker-config.json");
  saveSettings(configPath, {
    autoLaunch: true,
    autoRecordEnabled: true,
    inputDevice: "mic-2",
  });
  assert.deepEqual(loadSettings(configPath), {
    autoLaunch: true,
    autoRecordEnabled: true,
    inputDevice: "mic-2",
    apiRoutes: TEST_API_ROUTES,
  });
  assert.equal(
    JSON.parse(fs.readFileSync(path.join(root, "settings.json"), "utf8"))
      .deviceNo,
    undefined
  );
});

test("invalid or corrupt persisted settings fall back safely", () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "recorder-settings-"));
  fs.writeFileSync(
    path.join(root, "settings.json"),
    JSON.stringify({ autoLaunch: "yes", inputDevice: { id: 1 } })
  );
  assert.deepEqual(loadSettings(path.join(root, "worker-config.json")), {
    autoLaunch: false,
    autoRecordEnabled: true,
    inputDevice: "default",
    apiRoutes: TEST_API_ROUTES,
  });
});

test("worker core settings are loaded as authority instead of stale Electron defaults", () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "recorder-settings-"));
  const configPath = path.join(root, "worker.json");
  fs.writeFileSync(
    configPath,
    JSON.stringify({
      auto_record_enabled: true,
      input_device: "mic-authoritative",
      device_no: "binding-secret",
      school_id: 9,
    })
  );
  assert.deepEqual(loadWorkerCoreSettings(configPath), {
    autoRecordEnabled: true,
    inputDevice: "mic-authoritative",
    apiRoutes: TEST_API_ROUTES,
  });
});

test("runtime patch accepts only strict core setting values", () => {
  assert.deepEqual(
    validateSettingsPatch(
      {
        autoRecordEnabled: true,
        inputDevice: " mic-2 ",
        dataRoot: "D:\\Recorder",
      },
      { platform: "win32" }
    ),
    {
      autoRecordEnabled: true,
      inputDevice: "mic-2",
      dataRoot: "D:\\Recorder",
    }
  );
  for (const patch of [
    null,
    [],
    { autoRecordEnabled: "true" },
    { inputDevice: {} },
    { inputDevice: "x".repeat(257) },
    { dataRoot: {} },
    { dataRoot: "relative" },
    { dataRoot: "\\\\server\\share" },
    { dataRoot: "C:\\Recorder" },
    { deviceNo: "attacker" },
    { schoolId: 1 },
    { locationId: "other" },
    { baseUrl: "https://evil.invalid" },
  ])
    assert.throws(() =>
      validateSettingsPatch(patch, { platform: "win32", systemDrive: "C:" })
    );
});

test("auto-launch value must be boolean", () => {
  assert.equal(validateAutoLaunchValue(false), false);
  for (const value of ["false", 0, null, {}, []])
    assert.throws(() => validateAutoLaunchValue(value), /boolean/i);
});

test("auto-launch reports verified, unverified, and failed states", () => {
  const verified = applyAutoLaunch({
    desired: true,
    platform: "win32",
    app: {
      setLoginItemSettings() {},
      getLoginItemSettings: () => ({ openAtLogin: true }),
    },
  });
  assert.deepEqual(verified, {
    desired: true,
    actual: true,
    status: "verified",
    error: null,
  });

  const unverified = applyAutoLaunch({
    desired: true,
    platform: "win32",
    app: {
      setLoginItemSettings() {},
      getLoginItemSettings: () => ({ openAtLogin: false }),
    },
  });
  assert.deepEqual(unverified, {
    desired: true,
    actual: false,
    status: "unverified",
    error: null,
  });

  const failed = applyAutoLaunch({
    desired: true,
    platform: "win32",
    app: {
      setLoginItemSettings() {
        throw new Error("registry denied");
      },
      getLoginItemSettings() {
        throw new Error("unreachable");
      },
    },
  });
  assert.deepEqual(failed, {
    desired: true,
    actual: null,
    status: "failed",
    error: "Windows 开机自启设置失败: registry denied",
  });
});

test("non-Windows auto-launch is explicitly unverifiable without calling Electron login APIs", () => {
  const result = applyAutoLaunch({
    desired: false,
    platform: "darwin",
    app: {
      setLoginItemSettings() {
        throw new Error("must not call");
      },
      getLoginItemSettings() {
        throw new Error("must not call");
      },
    },
  });
  assert.deepEqual(result, {
    desired: false,
    actual: null,
    status: "unverified",
    error: "仅支持在 Windows 上验证开机自启状态",
  });
});
