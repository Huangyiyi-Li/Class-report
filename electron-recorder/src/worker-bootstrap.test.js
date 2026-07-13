import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { bootstrapWorkerConfig, loadWorkerLocator, validateBootstrapDataRoot } from "./worker-bootstrap.js";

test("first settings save writes full config outside userData and a secret-free locator", () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "recorder-data-"));
  const userData = fs.mkdtempSync(path.join(os.tmpdir(), "recorder-user-"));
  const result = bootstrapWorkerConfig({ userDataDir: userData, patch: { dataRoot: root, autoRecordEnabled: true, inputDevice: "mic-1" } });
  assert.equal(result.runtimeDir, path.join(root, "runtime"));
  assert.equal(result.configPath.startsWith(root), true);
  assert.equal(result.configPath.startsWith(userData), false);
  const config = JSON.parse(fs.readFileSync(result.configPath, "utf8"));
  assert.equal(config.data_root, root);
  assert.equal(config.auto_record_enabled, true);
  assert.equal(config.base_url, "https://rest.xxt.cn");
  const locatorText = fs.readFileSync(path.join(userData, "worker-config-locator.json"), "utf8");
  assert.deepEqual(JSON.parse(locatorText), { configPath: result.configPath });
  assert.equal(locatorText.includes("password"), false);
});

test("restart resolves the non-system config through locator", () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "recorder-data-"));
  const userData = fs.mkdtempSync(path.join(os.tmpdir(), "recorder-user-"));
  const created = bootstrapWorkerConfig({ userDataDir: userData, patch: { dataRoot: root } });
  assert.deepEqual(loadWorkerLocator(userData), created);
});

test("Windows bootstrap rejects missing and system-drive roots", () => {
  assert.throws(() => validateBootstrapDataRoot("", { platform: "win32", systemDrive: "C:" }));
  assert.throws(() => validateBootstrapDataRoot("C:\\Recorder", { platform: "win32", systemDrive: "C:" }));
  assert.doesNotThrow(() => validateBootstrapDataRoot("D:\\Recorder", { platform: "win32", systemDrive: "C:" }));
});
