import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

const recorderDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const repositoryDir = path.resolve(recorderDir, "..");

const trackedFiles = new Set(
  execFileSync("git", ["ls-files"], {
    cwd: repositoryDir,
    encoding: "utf8",
  })
    .trim()
    .split("\n")
    .filter(Boolean),
);

const requiredFiles = [
  "electron-recorder/package.json",
  "electron-recorder/package-lock.json",
  "electron-recorder/vite.config.js",
  "electron-recorder/index.html",
  "electron-recorder/build/icon.ico",
  "electron-recorder/build/icon.png",
  "electron-recorder/scripts/build-windows-release.mjs",
  "electron-recorder/scripts/build-worker.py",
  "electron-recorder/scripts/install-electron.mjs",
  "electron-recorder/scripts/start-dev.mjs",
  "electron-recorder/scripts/test-clean-checkout.mjs",
  "electron-recorder/docs/TESTING.md",
  "electron-recorder/WINDOWS_TEST_README.md",
];

const missingFiles = requiredFiles.filter((file) => !trackedFiles.has(file));
assert.deepEqual(missingFiles, [], `required build inputs are not tracked: ${missingFiles.join(", ")}`);

const generatedDirectory =
  /(^|\/)(node_modules|dist|release)(\/|$)|^electron-recorder\/(worker\/build|build\/(worker|ffmpeg))\//;
const trackedGeneratedFiles = [...trackedFiles].filter((file) => generatedDirectory.test(file));
assert.deepEqual(
  trackedGeneratedFiles,
  [],
  `generated directories contain tracked files: ${trackedGeneratedFiles.join(", ")}`,
);

console.log("clean-checkout repository inputs are tracked and generated directories are clean");
