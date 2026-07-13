import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";
import { WorkerClient } from "./worker-client.js";

const projectRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

async function waitForFile(target) {
  for (let index = 0; index < 100; index += 1) {
    if (fs.existsSync(target)) return;
    await wait(10);
  }
  throw new Error(`missing ${target}`);
}

function startHarness(runtimeDir) {
  return spawn(process.env.RECORDER_PYTHON || "python3", ["-m", "worker._control_harness", runtimeDir], {
    cwd: projectRoot, stdio: "ignore",
  });
}

test("Node client authenticates Python server and recovers the same snapshot", { timeout: 10000 }, async () => {
  const runtimeDir = fs.mkdtempSync(path.join(os.tmpdir(), "recorder-control-"));
  let server = startHarness(runtimeDir);
  await waitForFile(path.join(runtimeDir, "worker-endpoint.json"));
  const endpoint = JSON.parse(fs.readFileSync(path.join(runtimeDir, "worker-endpoint.json"), "utf8"));
  const token = fs.readFileSync(path.join(runtimeDir, "worker-token"), "utf8").trim();
  assert.equal(endpoint.host, "127.0.0.1");
  assert.equal(Number.isInteger(endpoint.port), true);
  assert.equal(token.length >= 32, true);

  const snapshots = [];
  const client = new WorkerClient({ runtimeDir, launchWorker() {}, retryDelayMs: 10, maxRetryDelayMs: 30, maxAttempts: 2, authenticationTimeoutMs: 200 });
  client.on("ready", (snapshot) => snapshots.push(snapshot));
  client.on("snapshot", (snapshot) => snapshots.push(snapshot));
  await client.connect();
  client.send("start");
  while (!snapshots.some((item) => item.recording === "recording")) await wait(10);

  server.kill("SIGTERM");
  await new Promise((resolve) => server.once("exit", resolve));
  server = startHarness(runtimeDir);
  await waitForFile(path.join(runtimeDir, "worker-endpoint.json"));
  for (let index = 0; index < 200 && client.socket === null; index += 1) await wait(10);
  assert.equal(client.socket !== null, true);
  assert.equal(snapshots.at(-1).recording, "recording");
  client.disconnect();
  server.kill("SIGTERM");
});
