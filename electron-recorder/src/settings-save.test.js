import assert from "node:assert/strict";
import test from "node:test";
import { SETTINGS_SAVE_UNCONFIRMED, saveSettings, setAutoLaunchAfterBootstrap } from "./settings-save.js";

test("auto-launch before bootstrap fails without mutation or registration", () => {
  let applied = 0;
  const result = setAutoLaunchAfterBootstrap({ workerLocation: null, desired: true, apply: () => { applied += 1; } });
  assert.equal(result.status, "failed");
  assert.match(result.error, /请先配置非系统盘数据目录/);
  assert.equal(applied, 0);
});

test("failed settings save keeps modal open and shows fixed confirmation warning", async () => {
  let closed = 0;
  let warning = "";
  const saved = await saveSettings({
    updateSettings: async () => { throw new Error("IPC disconnected"); },
    setAutoLaunch: async () => {}, workerSettings: {}, autoLaunch: true,
    onClose: () => { closed += 1; }, onUnconfirmed: (message) => { warning = message; },
  });
  assert.equal(saved, false);
  assert.equal(closed, 0);
  assert.equal(warning, SETTINGS_SAVE_UNCONFIRMED);
});

test("successful settings save closes modal", async () => {
  let closed = 0;
  const saved = await saveSettings({
    updateSettings: async () => {}, setAutoLaunch: async () => ({ status: "verified", desired: true, actual: true, error: null }), workerSettings: {}, autoLaunch: true,
    onClose: () => { closed += 1; }, onUnconfirmed: () => {},
  });
  assert.equal(saved, true);
  assert.equal(closed, 1);
});

for (const result of [
  { status: "failed", error: "Windows 开机自启设置失败：注册表被拒绝" },
  { status: "unverified", error: "仅支持在 Windows 上验证开机自启状态" },
  { status: "unverified", error: null },
]) {
  test(`auto-launch ${result.status} keeps modal open and reports a concrete reason`, async () => {
    let closed = 0;
    let warning = "";
    const saved = await saveSettings({
      updateSettings: async () => {}, setAutoLaunch: async () => result, workerSettings: {}, autoLaunch: true,
      onClose: () => { closed += 1; }, onUnconfirmed: (message) => { warning = message; },
    });
    assert.equal(saved, false);
    assert.equal(closed, 0);
    assert.equal(warning, result.error || "开机自启状态未验证，请重试");
  });
}
