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
  constructor({
    runtimeDir,
    readEndpoint = () => defaultReadEndpoint(runtimeDir),
    openSocket = defaultOpenSocket,
    launchWorker,
    retryDelayMs = 200,
    maxAttempts = 25,
  }) {
    super();
    this.readEndpoint = readEndpoint;
    this.openSocket = openSocket;
    this.launchWorker = launchWorker;
    this.retryDelayMs = retryDelayMs;
    this.maxAttempts = maxAttempts;
    this.buffer = "";
    this.socket = null;
    this.on("error", () => {});
  }

  async connect() {
    let launched = false;
    let lastError;
    for (let attempt = 0; attempt < this.maxAttempts; attempt += 1) {
      try {
        const endpoint = await this.readEndpoint();
        this.socket = await this.openSocket(endpoint);
        this._attachSocket(this.socket);
        this.socket.write(`${JSON.stringify({ token: endpoint.token })}\n`);
        return;
      } catch (error) {
        lastError = error;
        if (!launched) {
          this.launchWorker({ detached: true, stdio: "ignore" });
          launched = true;
        }
        if (attempt + 1 < this.maxAttempts) await delay(this.retryDelayMs);
      }
    }
    throw lastError;
  }

  _attachSocket(socket) {
    socket.on("data", (chunk) => this._consume(chunk.toString("utf8")));
    socket.on("error", (error) => this.emit("error", error));
    socket.on("close", () => {
      if (this.socket === socket) this.socket = null;
      this.emit("disconnect");
    });
  }

  _consume(text) {
    this.buffer += text;
    const lines = this.buffer.split("\n");
    this.buffer = lines.pop() || "";
    for (const line of lines.filter(Boolean)) {
      try {
        const message = JSON.parse(line);
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
    const socket = this.socket;
    this.socket = null;
    socket?.end();
  }
}
