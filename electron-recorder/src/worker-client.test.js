import assert from "node:assert/strict";
import { EventEmitter } from "node:events";
import test from "node:test";
import { WorkerClient } from "./worker-client.js";

class FakeSocket extends EventEmitter {
  constructor() {
    super();
    this.writes = [];
  }
  write(value) { this.writes.push(JSON.parse(value)); }
  end() { this.emit("close"); }
}

const endpoint = { host: "127.0.0.1", port: 43123, token: "secret" };

test("connects to an existing worker without launching another", async () => {
  const socket = new FakeSocket();
  let launches = 0;
  const client = new WorkerClient({
    readEndpoint: async () => endpoint,
    openSocket: async () => socket,
    launchWorker: () => { launches += 1; },
  });
  await client.connect();
  assert.equal(launches, 0);
  assert.deepEqual(socket.writes, [{ token: "secret" }]);
});

test("launches detached worker only after existing endpoint connection fails", async () => {
  const socket = new FakeSocket();
  let attempts = 0;
  let launchOptions;
  const client = new WorkerClient({
    readEndpoint: async () => endpoint,
    openSocket: async () => {
      attempts += 1;
      if (attempts === 1) throw new Error("worker unavailable");
      return socket;
    },
    launchWorker: (options) => { launchOptions = options; },
    retryDelayMs: 1,
  });
  await client.connect();
  assert.equal(attempts, 2);
  assert.deepEqual(launchOptions, { detached: true, stdio: "ignore" });
});

test("retries until the launched worker publishes its endpoint", async () => {
  const socket = new FakeSocket();
  let reads = 0;
  const client = new WorkerClient({
    readEndpoint: async () => {
      reads += 1;
      if (reads < 3) throw new Error("endpoint absent");
      return endpoint;
    },
    openSocket: async () => socket,
    launchWorker() {},
    retryDelayMs: 1,
    maxAttempts: 4,
  });
  await client.connect();
  assert.equal(reads, 3);
});

test("disconnect closes control socket without sending shutdown", async () => {
  const socket = new FakeSocket();
  const client = new WorkerClient({
    readEndpoint: async () => endpoint,
    openSocket: async () => socket,
    launchWorker() {},
  });
  await client.connect();
  client.send("start");
  client.disconnect();
  assert.equal(socket.writes.some((message) => message.command === "shutdown"), false);
  assert.equal(socket.writes.some((message) => message.command === "start"), true);
});
