import assert from "node:assert/strict";
import test from "node:test";
import { applyWorkerSettings } from "./worker-settings.js";

for (const recording of ["idle", "recording"]) {
  test(`root change while ${recording} rejects without persistence or replacing the existing client`, async () => {
    let attached = 0;
    let persisted = 0;
    await assert.rejects(applyWorkerSettings({
      settings: { dataRoot: "/data/one" }, patch: { dataRoot: "/data/two" }, workerLocation: { dataRoot: "/data/one" },
      persistBootstrap: () => { persisted += 1; }, attach: () => { attached += 1; },
      supervisor: { socket: {}, sendCommand: async () => {} },
    }), /不可修改/);
    assert.equal(attached, 0);
    assert.equal(persisted, 0);
  });
}

test("existing idle config is persisted only by acknowledged worker command", async () => {
  let commands = 0;
  let persisted = 0;
  const result = await applyWorkerSettings({
    settings: { dataRoot: "/data/one", inputDevice: "old" }, patch: { inputDevice: "new" },
    workerLocation: { dataRoot: "/data/one" }, persistBootstrap: () => { persisted += 1; }, attach() {},
    supervisor: { socket: {}, async sendCommand(command) { assert.equal(command, "update_settings"); commands += 1; } },
  });
  assert.equal(result.settings.inputDevice, "new");
  assert.equal(commands, 1);
  assert.equal(persisted, 0);
});

test("recording rejection and disconnection leave Electron settings unchanged", async () => {
  const original = { dataRoot: "/data/one", inputDevice: "old" };
  for (const supervisor of [
    { socket: {}, sendCommand: async () => { throw new Error("录音中不允许变更运行设置"); } },
    { socket: null, sendCommand: async () => {} },
  ]) {
    await assert.rejects(applyWorkerSettings({
      settings: original, patch: { inputDevice: "new" }, workerLocation: { dataRoot: "/data/one" },
      persistBootstrap() { throw new Error("must not persist"); }, attach() {}, supervisor,
    }));
    assert.deepEqual(original, { dataRoot: "/data/one", inputDevice: "old" });
  }
});
