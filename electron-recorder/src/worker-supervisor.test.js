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

test("reports malformed worker output and continues parsing later lines", () => {
  const child = new EventEmitter();
  child.stdout = new EventEmitter();
  child.stdin = { write() {} };
  const supervisor = new WorkerSupervisor({ spawnWorker: () => child });
  let error;
  let snapshot;
  supervisor.on("error", (value) => {
    error = value;
  });
  supervisor.on("snapshot", (value) => {
    snapshot = value;
  });
  supervisor.start();

  assert.doesNotThrow(() => {
    child.stdout.emit(
      "data",
      Buffer.from('not-json\n{"event":"snapshot","payload":{"recording":"paused"}}\n'),
    );
  });
  assert.ok(error instanceof Error);
  assert.equal(snapshot.recording, "paused");
});

test("stop cancels a queued restart without writing to an exited child", async () => {
  let spawnCount = 0;
  let writeCount = 0;
  let child;
  const supervisor = new WorkerSupervisor({
    spawnWorker: () => {
      spawnCount += 1;
      child = new EventEmitter();
      child.stdout = new EventEmitter();
      child.stdin = {
        write() {
          writeCount += 1;
        },
      };
      return child;
    },
    restartDelayMs: 10,
  });
  supervisor.start();
  child.emit("exit", 1);

  supervisor.stop();
  await new Promise((resolve) => setTimeout(resolve, 30));

  assert.equal(writeCount, 0);
  assert.equal(spawnCount, 1);
});
