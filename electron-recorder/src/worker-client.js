import crypto from "node:crypto";
import { EventEmitter } from "node:events";
import fs from "node:fs/promises";
import net from "node:net";

class ConnectionCancelled extends Error {}

async function defaultReadEndpoint(runtimeDir) {
  const endpoint = JSON.parse(await fs.readFile(`${runtimeDir}/worker-endpoint.json`, "utf8"));
  const token = (await fs.readFile(`${runtimeDir}/worker-token`, "utf8")).trim();
  if (endpoint.host !== "127.0.0.1") throw new Error("worker endpoint is not loopback");
  return { ...endpoint, token };
}

function defaultOpenSocket({ host, port }) {
  return new Promise((resolve, reject) => {
    const socket = net.createConnection({ host, port });
    socket.once("connect", () => resolve(socket));
    socket.once("error", reject);
  });
}

export class WorkerClient extends EventEmitter {
  constructor({ runtimeDir, readEndpoint = () => defaultReadEndpoint(runtimeDir), openSocket = defaultOpenSocket,
    launchWorker, retryDelayMs = 200, maxRetryDelayMs = 2000, maxAttempts = 25,
    authenticationTimeoutMs = 2000, launchCooldownMs = 5000 }) {
    super();
    this.readEndpoint = readEndpoint;
    this.openSocket = openSocket;
    this.launchWorker = launchWorker;
    this.retryDelayMs = retryDelayMs;
    this.maxRetryDelayMs = maxRetryDelayMs;
    this.maxAttempts = maxAttempts;
    this.authenticationTimeoutMs = authenticationTimeoutMs;
    this.launchCooldownMs = launchCooldownMs;
    this.socket = null;
    this.pendingSocket = null;
    this.terminal = false;
    this.generation = 0;
    this.recoveryPromise = null;
    this.cancelSleeps = new Set();
    this.nextLaunchAt = 0;
    this.on("error", () => {});
  }

  connect() {
    if (this.terminal) return Promise.reject(new ConnectionCancelled("worker client is disconnected"));
    if (this.socket) return Promise.resolve();
    if (!this.recoveryPromise) {
      const generation = this.generation;
      const recovery = this._recoveryLoop(generation).finally(() => {
        if (this.recoveryPromise === recovery) this.recoveryPromise = null;
      });
      this.recoveryPromise = recovery;
    }
    return this.recoveryPromise;
  }

  start() { return this.resume(); }

  resume() {
    if (this.terminal) {
      this.terminal = false;
      this.generation += 1;
    }
    return this.connect();
  }

  _assertActive(generation) {
    if (this.terminal || generation !== this.generation) throw new ConnectionCancelled("worker connection cancelled");
  }

  async _recoveryLoop(generation) {
    let cycle = 0;
    while (true) {
      this._assertActive(generation);
      for (let attempt = 0; attempt < this.maxAttempts; attempt += 1) {
        let socket;
        try {
          const endpoint = await this.readEndpoint();
          this._assertActive(generation);
          socket = await this.openSocket(endpoint);
          this._assertActive(generation);
          this.pendingSocket = socket;
          const snapshot = await this._authenticate(socket, endpoint.token, generation);
          this._assertActive(generation);
          this.pendingSocket = null;
          this.socket = socket;
          this.nextLaunchAt = 0;
          this._attachRuntimeSocket(socket, generation);
          this.emit("ready", snapshot);
          return;
        } catch (error) {
          if (this.pendingSocket === socket) this.pendingSocket = null;
          socket?.destroy?.();
          socket?.end?.();
          this._assertActive(generation);
          const now = Date.now();
          if (now >= this.nextLaunchAt) {
            const child = this.launchWorker({ detached: true, stdio: "ignore" });
            child?.once?.("error", (launchError) => this.emit("error", launchError));
            this.nextLaunchAt = now + this.launchCooldownMs;
          }
          await this._sleep(Math.min(this.retryDelayMs * (attempt + 1), this.maxRetryDelayMs), generation);
        }
      }
      cycle += 1;
      await this._sleep(Math.min(this.maxRetryDelayMs * cycle, this.maxRetryDelayMs), generation);
    }
  }

  _sleep(milliseconds, generation) {
    return new Promise((resolve, reject) => {
      const cancel = () => { clearTimeout(timer); this.cancelSleeps.delete(cancel); reject(new ConnectionCancelled("worker connection cancelled")); };
      const timer = setTimeout(() => { this.cancelSleeps.delete(cancel); resolve(); }, milliseconds);
      this.cancelSleeps.add(cancel);
      if (this.terminal || generation !== this.generation) cancel();
    });
  }

  _authenticate(socket, token, generation) {
    let buffer = "";
    return new Promise((resolve, reject) => {
      const cleanup = () => {
        clearTimeout(timer);
        socket.removeListener("data", onData);
        socket.removeListener("error", onError);
        socket.removeListener("close", onClose);
      };
      const finish = (error, snapshot) => { cleanup(); error ? reject(error) : resolve(snapshot); };
      const onError = (error) => finish(error);
      const onClose = () => finish(new Error("worker closed before authentication"));
      const onData = (chunk) => {
        buffer += chunk.toString("utf8");
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";
        for (const line of lines.filter(Boolean)) {
          try {
            const message = JSON.parse(line);
            if (message.event === "ready") return finish(null, message.payload);
            if (message.event === "error") return finish(new Error(message.payload?.message || "worker authentication failed"));
          } catch (error) { return finish(error); }
        }
      };
      const timer = setTimeout(() => finish(new Error("worker authentication timed out")), this.authenticationTimeoutMs);
      socket.on("data", onData);
      socket.once("error", onError);
      socket.once("close", onClose);
      try {
        this._assertActive(generation);
        socket.write(`${JSON.stringify({ token })}\n`);
      } catch (error) { finish(error); }
    });
  }

  _attachRuntimeSocket(socket, generation) {
    let buffer = "";
    const onData = (chunk) => {
      buffer += chunk.toString("utf8");
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";
      for (const line of lines.filter(Boolean)) {
        try {
          const message = JSON.parse(line);
          this.emit(message.event, message.payload);
        } catch (error) { this.emit("error", error); }
      }
    };
    const lost = (error) => {
      if (error) this.emit("error", error);
      if (this.socket !== socket) return;
      this.socket = null;
      socket.removeListener("data", onData);
      this.emit("disconnect");
      if (!this.terminal && generation === this.generation) this.connect().catch((failure) => {
        if (!(failure instanceof ConnectionCancelled)) this.emit("error", failure);
      });
    };
    socket.on("data", onData);
    socket.on("error", lost);
    socket.on("close", () => lost());
  }

  send(command, payload = {}) {
    if (!this.socket) throw new Error("worker is not connected");
    this.socket.write(`${JSON.stringify({ id: crypto.randomUUID(), command, payload })}\n`);
  }

  disconnect() {
    if (this.terminal) return;
    this.terminal = true;
    this.generation += 1;
    this.recoveryPromise = null;
    for (const cancel of [...this.cancelSleeps]) cancel();
    const pending = this.pendingSocket;
    this.pendingSocket = null;
    pending?.destroy?.();
    pending?.end?.();
    const socket = this.socket;
    this.socket = null;
    socket?.end();
  }
}
