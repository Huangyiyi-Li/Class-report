import assert from "node:assert/strict";
import test from "node:test";
import { SETTINGS_SAVE_UNCONFIRMED, saveSettings } from "./settings-save.js";

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
    updateSettings: async () => {}, setAutoLaunch: async () => {}, workerSettings: {}, autoLaunch: true,
    onClose: () => { closed += 1; }, onUnconfirmed: () => {},
  });
  assert.equal(saved, true);
  assert.equal(closed, 1);
});
