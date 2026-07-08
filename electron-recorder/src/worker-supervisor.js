import crypto from "node:crypto";
import { EventEmitter } from "node:events";

export class WorkerSupervisor extends EventEmitter {
  constructor({ spawnWorker, restartDelayMs = 3000 }) {
    super();
    this.spawnWorker = spawnWorker;
    this.restartDelayMs = restartDelayMs;
    this.buffer = "";
    this.stopping = false;
  }

  start() {
    this.child = this.spawnWorker();
    this.child.stdout.on("data", (chunk) =>
      this.consume(chunk.toString("utf8")),
    );
    this.child.on("exit", (code) => {
      this.emit("exit", code);
      if (!this.stopping) {
        setTimeout(() => this.start(), this.restartDelayMs);
      }
    });
  }

  consume(text) {
    this.buffer += text;
    const lines = this.buffer.split("\n");
    this.buffer = lines.pop() || "";
    for (const line of lines.filter(Boolean)) {
      const message = JSON.parse(line);
      this.emit(message.event, message.payload);
    }
  }

  send(command, payload = {}) {
    this.child.stdin.write(
      `${JSON.stringify({ id: crypto.randomUUID(), command, payload })}\n`,
    );
  }

  stop() {
    this.stopping = true;
    this.send("shutdown");
  }
}
