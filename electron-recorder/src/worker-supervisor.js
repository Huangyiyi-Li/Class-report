import crypto from "node:crypto";
import { EventEmitter } from "node:events";

export class WorkerSupervisor extends EventEmitter {
  constructor({ spawnWorker, restartDelayMs = 3000 }) {
    super();
    this.spawnWorker = spawnWorker;
    this.restartDelayMs = restartDelayMs;
    this.buffer = "";
    this.stopping = false;
    this.restartTimer = null;
    this.childExited = false;
    this.on("error", () => {});
  }

  start() {
    this.child = this.spawnWorker();
    this.childExited = false;
    this.child.stdout.on("data", (chunk) =>
      this.consume(chunk.toString("utf8")),
    );
    this.child.on("exit", (code) => {
      this.childExited = true;
      this.emit("exit", code);
      if (!this.stopping) {
        this.restartTimer = setTimeout(() => {
          this.restartTimer = null;
          if (!this.stopping) {
            this.start();
          }
        }, this.restartDelayMs);
      }
    });
  }

  consume(text) {
    this.buffer += text;
    const lines = this.buffer.split("\n");
    this.buffer = lines.pop() || "";
    for (const line of lines.filter(Boolean)) {
      let message;
      try {
        message = JSON.parse(line);
      } catch (error) {
        this.emit("error", error);
        continue;
      }
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
    if (this.restartTimer) {
      clearTimeout(this.restartTimer);
      this.restartTimer = null;
    }
    if (!this.childExited) {
      this.send("shutdown");
    }
  }
}
