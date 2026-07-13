import assert from "node:assert/strict";
import { EventEmitter } from "node:events";
import test from "node:test";
import { WorkerClient } from "./worker-client.js";

class FakeSocket extends EventEmitter {
  constructor() {
    super();
    this.writes = [];
  }
  write(value) {
    const message = JSON.parse(value);
    this.writes.push(message);
    if (message.token) queueMicrotask(() => this.emit("data", Buffer.from('{"event":"ready","payload":{"recording":"idle"}}\n')));
  }
  end() { this.ended = true; this.emit("close"); }
  destroy() { this.destroyed = true; }
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

test("authentication rejection does not resolve connect and triggers retry", async () => {
  const rejected = new FakeSocket();
  rejected.write = function(value) {
    this.writes.push(JSON.parse(value));
    queueMicrotask(() => this.emit("data", Buffer.from('{"event":"error","payload":{"message":"authentication failed"}}\n')));
  };
  const accepted = new FakeSocket();
  let attempts = 0;
  const client = new WorkerClient({
    readEndpoint: async () => endpoint,
    openSocket: async () => (++attempts === 1 ? rejected : accepted),
    launchWorker() {}, retryDelayMs: 1, authenticationTimeoutMs: 20,
  });
  await client.connect();
  assert.equal(attempts, 2);
});

test("unexpected socket close reconnects without launching twice", async () => {
  const first = new FakeSocket();
  const second = new FakeSocket();
  let attempts = 0;
  let launches = 0;
  const client = new WorkerClient({
    readEndpoint: async () => endpoint,
    openSocket: async () => (++attempts === 1 ? first : second),
    launchWorker() { launches += 1; }, retryDelayMs: 1,
  });
  await client.connect();
  first.emit("close");
  await new Promise((resolve) => setTimeout(resolve, 10));
  assert.equal(client.socket, second);
  assert.equal(launches, 0);
  client.disconnect();
  second.emit("close");
  await new Promise((resolve) => setTimeout(resolve, 10));
  assert.equal(attempts, 2);
});

test("authentication timeout retries a stale endpoint", async () => {
  const silent = new FakeSocket();
  silent.write = function(value) { this.writes.push(JSON.parse(value)); };
  const accepted = new FakeSocket();
  let attempts = 0;
  const client = new WorkerClient({
    readEndpoint: async () => endpoint,
    openSocket: async () => (++attempts === 1 ? silent : accepted),
    launchWorker() {}, retryDelayMs: 1, authenticationTimeoutMs: 5,
  });
  await client.connect();
  assert.equal(attempts, 2);
  client.disconnect();
});

test("runtime socket error reconnects even before close", async () => {
  const first = new FakeSocket();
  const second = new FakeSocket();
  let attempts = 0;
  const client = new WorkerClient({
    readEndpoint: async () => endpoint,
    openSocket: async () => (++attempts === 1 ? first : second),
    launchWorker() {}, retryDelayMs: 1,
  });
  await client.connect();
  first.emit("error", new Error("reset"));
  await new Promise((resolve) => setTimeout(resolve, 10));
  assert.equal(client.socket, second);
  client.disconnect();
});

test("disconnect during authentication cancels pending socket and late ready cannot resurrect it", async () => {
  const pending = new FakeSocket();
  pending.write = function(value) { this.writes.push(JSON.parse(value)); };
  const client = new WorkerClient({
    readEndpoint: async () => endpoint, openSocket: async () => pending,
    launchWorker() {}, authenticationTimeoutMs: 1000,
  });
  const connecting = client.connect().catch((error) => error);
  await new Promise((resolve) => setTimeout(resolve, 1));
  client.disconnect();
  pending.emit("data", Buffer.from('{"event":"ready","payload":{"recording":"idle"}}\n'));
  await connecting;
  assert.equal(pending.ended || pending.destroyed, true);
  assert.equal(client.socket, null);
});

test("late recovery can relaunch after a previously connected worker crashes", async () => {
  const first = new FakeSocket();
  const recovered = new FakeSocket();
  let available = true;
  let launches = 0;
  const client = new WorkerClient({
    readEndpoint: async () => endpoint,
    openSocket: async () => {
      if (available && launches === 0) return first;
      if (available && launches > 0) return recovered;
      throw new Error("down");
    },
    launchWorker() { launches += 1; available = true; },
    retryDelayMs: 1, maxRetryDelayMs: 2, maxAttempts: 2, launchCooldownMs: 2,
  });
  await client.connect();
  available = false;
  first.emit("close");
  await new Promise((resolve) => setTimeout(resolve, 15));
  assert.equal(client.socket, recovered);
  assert.equal(launches, 1);
  client.disconnect();
});

test("quit cancels queued retry timers without later connection work", async () => {
  let reads = 0;
  const client = new WorkerClient({
    readEndpoint: async () => { reads += 1; throw new Error("offline"); },
    openSocket: async () => { throw new Error("offline"); },
    launchWorker() {}, retryDelayMs: 50, maxRetryDelayMs: 50, maxAttempts: 2,
  });
  const recovery = client.connect().catch((error) => error);
  await new Promise((resolve) => setTimeout(resolve, 2));
  client.disconnect();
  await recovery;
  const readsAtQuit = reads;
  await new Promise((resolve) => setTimeout(resolve, 70));
  assert.equal(reads, readsAtQuit);
  await assert.rejects(client.connect(), /disconnected/);
});

test("resume starts a new generation after explicit disconnect", async () => {
  const first = new FakeSocket();
  first.write = function(value) { this.writes.push(JSON.parse(value)); };
  const second = new FakeSocket();
  let attempts = 0;
  const client = new WorkerClient({
    readEndpoint: async () => endpoint,
    openSocket: async () => (++attempts === 1 ? first : second),
    launchWorker() {}, retryDelayMs: 1,
  });
  const firstAttempt = client.connect().catch((error) => error);
  await new Promise((resolve) => setTimeout(resolve, 1));
  client.disconnect();
  await firstAttempt;
  await client.resume();
  assert.equal(client.socket, second);
  client.disconnect();
});
