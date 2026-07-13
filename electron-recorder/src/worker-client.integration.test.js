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

test("Electron disconnect leaves real Python RecorderWorker capturing for the next client", { timeout: 10000 }, async () => {
  const runtimeDir = fs.mkdtempSync(path.join(os.tmpdir(), "recorder-control-"));
  let server = startHarness(runtimeDir);
  await waitForFile(path.join(runtimeDir, "worker-endpoint.json"));
  const endpoint = JSON.parse(fs.readFileSync(path.join(runtimeDir, "worker-endpoint.json"), "utf8"));
  const token = fs.readFileSync(path.join(runtimeDir, "worker-token"), "utf8").trim();
  assert.equal(endpoint.host, "127.0.0.1");
  assert.equal(Number.isInteger(endpoint.port), true);
  assert.equal(token.length >= 32, true);

  const snapshots = [];
  const clientA = new WorkerClient({ runtimeDir, launchWorker() {}, authenticationTimeoutMs: 200 });
  clientA.on("ready", (snapshot) => snapshots.push(snapshot));
  clientA.on("snapshot", (snapshot) => snapshots.push(snapshot));
  await clientA.connect();
  clientA.send("start");
  while (!snapshots.some((item) => item.recording === "recording")) await wait(10);
  clientA.disconnect();
  assert.equal(server.exitCode, null);

  let reconnectedSnapshot;
  const clientB = new WorkerClient({ runtimeDir, launchWorker() {}, authenticationTimeoutMs: 200 });
  clientB.on("ready", (snapshot) => { reconnectedSnapshot = snapshot; });
  await clientB.connect();
  assert.equal(reconnectedSnapshot.recording, "recording");
  clientB.disconnect();
  server.kill("SIGTERM");
});
