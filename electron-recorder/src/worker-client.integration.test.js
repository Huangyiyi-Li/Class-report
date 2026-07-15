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
  for (let index = 0; index < 500; index += 1) {
    if (fs.existsSync(target)) return;
    await wait(10);
  }
  throw new Error(`missing ${target}`);
}

function startHarness(runtimeDir) {
  const executable = process.env.RECORDER_PYTHON || (process.platform === "win32" ? "py" : "python3");
  const versionArgs = !process.env.RECORDER_PYTHON && process.platform === "win32" ? ["-3.11"] : [];
  return spawn(executable, [...versionArgs, "-m", "worker._control_harness", runtimeDir], {
    cwd: projectRoot, stdio: "ignore",
  });
}

async function stopHarness(server) {
  if (server.exitCode !== null || server.signalCode !== null) return;
  const exited = new Promise((resolve) => {
    server.once("exit", resolve);
    server.once("error", resolve);
  });
  server.kill("SIGTERM");
  await Promise.race([exited, wait(2000)]);
  if (server.exitCode === null && server.signalCode === null) {
    server.kill("SIGKILL");
    await Promise.race([exited, wait(2000)]);
  }
}

test("Electron disconnect leaves real Python RecorderWorker capturing for the next client", { timeout: 10000 }, async () => {
  const runtimeDir = fs.mkdtempSync(path.join(os.tmpdir(), "recorder-control-"));
  const server = startHarness(runtimeDir);
  try {
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
  } finally {
    await stopHarness(server);
  }
});

test("WorkerClient applies a binding through the real Python control protocol", { timeout: 10000 }, async () => {
  const runtimeDir = fs.mkdtempSync(path.join(os.tmpdir(), "recorder-binding-control-"));
  const server = startHarness(runtimeDir);
  let client;
  try {
    await waitForFile(path.join(runtimeDir, "worker-endpoint.json"));
    const snapshots = [];
    client = new WorkerClient({ runtimeDir, launchWorker() {}, authenticationTimeoutMs: 200 });
    client.on("snapshot", (snapshot) => snapshots.push(snapshot));
    await client.connect();

    const binding = {
      deviceNo: "AABBCCDDEEFF",
      schoolId: 1001,
      schoolName: "星河实验学校",
      locationType: "classroom",
      locationId: "room-101",
      locationName: "一年级一班教室",
      classId: "class-101",
      className: "一年级一班",
      bindingSource: "mock",
      boundAt: "2026-07-15T08:00:00.000Z",
    };
    const result = await client.sendCommand("apply_binding", binding);

    assert.equal(result.success, true);
    while (!snapshots.some((snapshot) => snapshot.binding?.locationId === "room-101")) await wait(10);
    assert.equal(snapshots.at(-1).binding.classId, "class-101");
    const persisted = JSON.parse(fs.readFileSync(path.join(runtimeDir, "worker-config.json"), "utf8"));
    assert.equal(persisted.device_no, "AABBCCDDEEFF");
    assert.equal(persisted.location_id, "room-101");
  } finally {
    client?.disconnect();
    await stopHarness(server);
  }
});
