import assert from "node:assert/strict";
import { EventEmitter } from "node:events";
import test from "node:test";
import { WorkerSupervisor } from "./worker-supervisor.js";

test("parses worker snapshot events", () => {
  const child = new EventEmitter();
  child.stdout = new EventEmitter();
  child.stdin = { write() {} };
  const supervisor = new WorkerSupervisor({
    spawnWorker: () => child,
    restartDelayMs: 1,
  });
  let snapshot;
  supervisor.on("snapshot", (value) => {
    snapshot = value;
  });
  supervisor.start();
  child.stdout.emit(
    "data",
    Buffer.from('{"event":"snapshot","payload":{"recording":"recording"}}\n'),
  );
  assert.equal(snapshot.recording, "recording");
});
