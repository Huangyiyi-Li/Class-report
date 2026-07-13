import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { atomicWriteJson, bootstrapWorkerConfig, loadWorkerLocator, validateBootstrapDataRoot } from "./worker-bootstrap.js";

test("first settings save writes full config outside userData and a secret-free locator", () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "recorder-data-"));
  const userData = fs.mkdtempSync(path.join(os.tmpdir(), "recorder-user-"));
  const result = bootstrapWorkerConfig({ userDataDir: userData, patch: { dataRoot: root, autoRecordEnabled: true, inputDevice: "mic-1" } });
  assert.equal(result.runtimeDir, path.join(result.dataRoot, "runtime"));
  assert.equal(result.configPath.startsWith(result.dataRoot), true);
  assert.equal(result.configPath.startsWith(userData), false);
  const config = JSON.parse(fs.readFileSync(result.configPath, "utf8"));
  assert.equal(config.data_root, result.dataRoot);
  assert.equal(config.auto_record_enabled, true);
  assert.equal(config.base_url, "https://rest.xxt.cn");
  const locatorText = fs.readFileSync(path.join(userData, "worker-config-locator.json"), "utf8");
  assert.deepEqual(JSON.parse(locatorText), { configPath: result.configPath, dataRoot: result.dataRoot });
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
  assert.throws(() => validateBootstrapDataRoot("\\\\server\\share\\Recorder", { platform: "win32", systemDrive: "C:" }));
  assert.doesNotThrow(() => validateBootstrapDataRoot("D:\\Recorder", { platform: "win32", systemDrive: "C:" }));
});

for (const state of ["idle", "recording"]) {
  test(`data root migration is rejected while ${state}`, () => {
    const firstRoot = fs.mkdtempSync(path.join(os.tmpdir(), "recorder-data-"));
    const nextRoot = fs.mkdtempSync(path.join(os.tmpdir(), "recorder-data-"));
    const userData = fs.mkdtempSync(path.join(os.tmpdir(), "recorder-user-"));
    const original = bootstrapWorkerConfig({ userDataDir: userData, patch: { dataRoot: firstRoot } });
    assert.throws(
      () => bootstrapWorkerConfig({ userDataDir: userData, patch: { dataRoot: nextRoot } }),
      /首次部署后不可修改/,
    );
    assert.deepEqual(loadWorkerLocator(userData), original);
    assert.equal(fs.existsSync(path.join(nextRoot, ".classroom-recorder", "worker-config.json")), false);
  });
}

test("locator rejects relative, mismatched and escaped config paths before use", () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "recorder-data-"));
  const userData = fs.mkdtempSync(path.join(os.tmpdir(), "recorder-user-"));
  const locatorPath = path.join(userData, "worker-config-locator.json");
  fs.writeFileSync(locatorPath, JSON.stringify({ dataRoot: root, configPath: "relative.json" }));
  assert.equal(loadWorkerLocator(userData), null);
  fs.writeFileSync(locatorPath, JSON.stringify({ dataRoot: root, configPath: path.join(root, "other.json") }));
  assert.equal(loadWorkerLocator(userData), null);
  fs.writeFileSync(locatorPath, JSON.stringify({ dataRoot: root, configPath: path.join(root, ".classroom-recorder", "worker-config.json") }));
  fs.mkdirSync(path.join(root, ".classroom-recorder"), { recursive: true });
  fs.writeFileSync(path.join(root, ".classroom-recorder", "worker-config.json"), JSON.stringify({ data_root: `${root}-other` }));
  assert.equal(loadWorkerLocator(userData), null);
});

test("Windows locator rejects system-drive and UNC roots before config access", () => {
  const userData = fs.mkdtempSync(path.join(os.tmpdir(), "recorder-user-"));
  const locatorPath = path.join(userData, "worker-config-locator.json");
  const options = { platform: "win32", systemDrive: "C:" };
  fs.writeFileSync(locatorPath, JSON.stringify({ dataRoot: "C:\\Recorder", configPath: "C:\\Recorder\\.classroom-recorder\\worker-config.json" }));
  assert.equal(loadWorkerLocator(userData, options), null);
  fs.writeFileSync(locatorPath, JSON.stringify({ dataRoot: "\\\\server\\share", configPath: "\\\\server\\share\\.classroom-recorder\\worker-config.json" }));
  assert.equal(loadWorkerLocator(userData, options), null);
});

test("failed atomic replace removes its exclusive random temporary file", () => {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), "recorder-atomic-"));
  const target = path.join(directory, "target");
  fs.mkdirSync(target);
  assert.throws(() => atomicWriteJson(target, { value: true }));
  assert.deepEqual(fs.readdirSync(directory), ["target"]);
});

for (const canonical of ["C:\\Recorder", "\\\\server\\share\\Recorder"]) {
  test(`canonicalized bootstrap root ${canonical} is rejected before file writes`, () => {
    const userData = fs.mkdtempSync(path.join(os.tmpdir(), "recorder-user-"));
    let mkdirs = 0;
    assert.throws(() => bootstrapWorkerConfig({
      userDataDir: userData, patch: { dataRoot: "D:\\Recorder" },
      validationOptions: { platform: "win32", systemDrive: "C:" },
      mkdirRoot: () => { mkdirs += 1; }, realpath: () => canonical,
    }));
    assert.equal(mkdirs, 1);
    assert.deepEqual(fs.readdirSync(userData), []);
  });
}
