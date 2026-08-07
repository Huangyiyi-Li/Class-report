import assert from "node:assert/strict";
import { EventEmitter } from "node:events";
import test from "node:test";

let createUpdateController;
let canInstallWorkerUpdate;
try {
  ({ createUpdateController, canInstallWorkerUpdate } =
    await import("./update-manager.js"));
} catch {
  createUpdateController = undefined;
  canInstallWorkerUpdate = undefined;
}

class FakeUpdater extends EventEmitter {
  constructor() {
    super();
    this.checks = 0;
    this.downloads = 0;
    this.installs = 0;
  }

  async checkForUpdates() {
    this.checks += 1;
  }

  async downloadUpdate() {
    this.downloads += 1;
  }

  quitAndInstall() {
    this.installs += 1;
  }
}

test("packaged updater checks prereleases and downloads an available update", async () => {
  assert.equal(typeof createUpdateController, "function");
  const updater = new FakeUpdater();
  const states = [];
  const controller = createUpdateController({
    updater,
    currentVersion: "0.2.0-codex.5",
    supported: true,
    publish: (state) => states.push(state),
  });

  await controller.check();
  assert.equal(updater.checks, 1);
  assert.equal(updater.allowPrerelease, true);
  assert.equal(updater.autoDownload, false);
  assert.equal(updater.channel, "codex");

  updater.emit("update-available", { version: "0.2.0-codex.6" });
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(updater.downloads, 1);
  assert.equal(states.at(-1).status, "downloading");
  assert.equal(states.at(-1).availableVersion, "0.2.0-codex.6");
});

test("download progress and completion expose a restart-ready state", () => {
  assert.equal(typeof createUpdateController, "function");
  const updater = new FakeUpdater();
  const states = [];
  createUpdateController({
    updater,
    currentVersion: "0.2.0-codex.5",
    supported: true,
    publish: (state) => states.push(state),
  });

  updater.emit("download-progress", { percent: 42.4 });
  assert.equal(states.at(-1).status, "downloading");
  assert.equal(states.at(-1).percent, 42);

  updater.emit("update-downloaded", { version: "0.2.0-codex.6" });
  assert.equal(states.at(-1).status, "ready");
  assert.equal(states.at(-1).availableVersion, "0.2.0-codex.6");
});

test("install is blocked while recording and never stops the worker", async () => {
  assert.equal(typeof createUpdateController, "function");
  const updater = new FakeUpdater();
  let prepared = 0;
  const controller = createUpdateController({
    updater,
    currentVersion: "0.2.0-codex.5",
    supported: true,
    canInstall: () => false,
    prepareInstall: async () => {
      prepared += 1;
    },
  });
  updater.emit("update-downloaded", { version: "0.2.0-codex.6" });

  await assert.rejects(controller.install(), /录音中不能安装更新/);
  assert.equal(prepared, 0);
  assert.equal(updater.installs, 0);
});

test("update installation only treats active capture as recording", () => {
  assert.equal(typeof canInstallWorkerUpdate, "function");
  assert.equal(canInstallWorkerUpdate({ recording: "recording" }), false);
  assert.equal(canInstallWorkerUpdate({ recording: "starting" }), false);
  assert.equal(
    canInstallWorkerUpdate({ recording: "error", health: "binding_required" }),
    true
  );
  assert.equal(
    canInstallWorkerUpdate({ recording: "microphone_unavailable" }),
    true
  );
});

test("ready update shuts down safely before restarting the installed app", async () => {
  assert.equal(typeof createUpdateController, "function");
  const updater = new FakeUpdater();
  const calls = [];
  const controller = createUpdateController({
    updater,
    currentVersion: "0.2.0-codex.5",
    supported: true,
    canInstall: () => true,
    prepareInstall: async () => calls.push("prepare"),
  });
  updater.emit("update-downloaded", { version: "0.2.0-codex.6" });

  await controller.install();
  assert.deepEqual(calls, ["prepare"]);
  assert.equal(updater.installs, 1);
});
