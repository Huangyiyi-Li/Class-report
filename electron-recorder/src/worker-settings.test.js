import assert from "node:assert/strict";
import test from "node:test";
import { applyWorkerSettings } from "./worker-settings.js";

for (const recording of ["idle", "recording"]) {
  test(`root change while ${recording} rejects without replacing the existing client`, () => {
    let attached = 0;
    const existing = { dataRoot: "/data/one" };
    assert.throws(() => applyWorkerSettings({
      settings: { dataRoot: "/data/one" }, patch: { dataRoot: "/data/two" }, workerLocation: existing,
      persist: () => { throw new Error("录音数据目录首次部署后不可修改，需重新部署"); },
      attach: () => { attached += 1; }, supervisor: { socket: {}, send() {} },
    }), /不可修改/);
    assert.equal(attached, 0);
  });
}
