import crypto from "node:crypto";
import { EventEmitter } from "node:events";
import fs from "node:fs/promises";
import net from "node:net";

const delay = (milliseconds) => new Promise((resolve) => setTimeout(resolve, milliseconds));

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
    launchWorker, retryDelayMs = 200, maxRetryDelayMs = 2000, maxAttempts = 25, authenticationTimeoutMs = 2000 }) {
    super();
    this.readEndpoint = readEndpoint;
    this.openSocket = openSocket;
    this.launchWorker = launchWorker;
    this.retryDelayMs = retryDelayMs;
    this.maxRetryDelayMs = maxRetryDelayMs;
    this.maxAttempts = maxAttempts;
    this.authenticationTimeoutMs = authenticationTimeoutMs;
    this.buffer = "";
    this.socket = null;
    this.explicitlyDisconnected = false;
    this.launchedWorker = false;
    this.connectPromise = null;
    this.on("error", () => {});
  }

  connect() {
    this.explicitlyDisconnected = false;
    if (!this.connectPromise) {
      this.connectPromise = this._connectLoop().finally(() => { this.connectPromise = null; });
    }
    return this.connectPromise;
  }

  async _connectLoop() {
    let lastError;
    for (let attempt = 0; attempt < this.maxAttempts && !this.explicitlyDisconnected; attempt += 1) {
      let socket;
      try {
        const endpoint = await this.readEndpoint();
        socket = await this.openSocket(endpoint);
        await this._authenticate(socket, endpoint.token);
        this.socket = socket;
        return;
      } catch (error) {
        lastError = error;
        socket?.destroy?.();
        socket?.end?.();
        if (!this.launchedWorker && !this.explicitlyDisconnected) {
          this.launchWorker({ detached: true, stdio: "ignore" });
          this.launchedWorker = true;
        }
        if (attempt + 1 < this.maxAttempts) {
          await delay(Math.min(this.retryDelayMs * (attempt + 1), this.maxRetryDelayMs));
        }
      }
    }
    if (!this.explicitlyDisconnected) throw lastError || new Error("worker connection stopped");
  }

  _authenticate(socket, token) {
    this.buffer = "";
    return new Promise((resolve, reject) => {
      let settled = false;
      const finish = (error) => {
        if (settled) return;
        settled = true;
        clearTimeout(timer);
        if (error) reject(error); else resolve();
      };
      const timer = setTimeout(() => finish(new Error("worker authentication timed out")), this.authenticationTimeoutMs);
      const onData = (chunk) => this._consume(chunk.toString("utf8"), (message) => {
        if (message.event === "ready") finish();
        else if (message.event === "error") finish(new Error(message.payload?.message || "worker authentication failed"));
      });
      socket.on("data", onData);
      socket.once("error", finish);
      socket.once("close", () => finish(new Error("worker closed before authentication")));
      socket.write(`${JSON.stringify({ token })}\n`);
      this._attachRuntimeSocket(socket);
    });
  }

  _attachRuntimeSocket(socket) {
    socket.on("error", (error) => {
      this.emit("error", error);
      if (this.socket === socket) {
        this.socket = null;
        socket.destroy?.();
        this._reconnectAfterLoss();
      }
    });
    socket.on("close", () => {
      if (this.socket === socket) {
        this.socket = null;
        this._reconnectAfterLoss();
      }
    });
  }

  _reconnectAfterLoss() {
    this.emit("disconnect");
    if (!this.explicitlyDisconnected) this.connect().catch((error) => this.emit("error", error));
  }

  _consume(text, observe = () => {}) {
    this.buffer += text;
    const lines = this.buffer.split("\n");
    this.buffer = lines.pop() || "";
    for (const line of lines.filter(Boolean)) {
      try {
        const message = JSON.parse(line);
        observe(message);
        this.emit(message.event, message.payload);
      } catch (error) {
        this.emit("error", error);
      }
    }
  }

  send(command, payload = {}) {
    if (!this.socket) throw new Error("worker is not connected");
    this.socket.write(`${JSON.stringify({ id: crypto.randomUUID(), command, payload })}\n`);
  }

  disconnect() {
    this.explicitlyDisconnected = true;
    const socket = this.socket;
    this.socket = null;
    socket?.end();
  }
}
