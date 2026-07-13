import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const pkg = JSON.parse(readFileSync(path.join(root, "package.json"), "utf8"));

test("declares packaged worker and Windows FFmpeg resources", () => {
  assert.ok(pkg.build.extraResources.some((item) => item.from === "build/worker/ClassroomRecorderWorker.exe" && item.to === "worker/ClassroomRecorderWorker.exe"));
  assert.ok(pkg.build.extraResources.some((item) => item.from === "build/ffmpeg/ffmpeg.exe" && item.to === "ffmpeg/ffmpeg.exe"));
});

test("default test runs repository gate and declares supported Node versions", () => {
  assert.match(pkg.scripts.test, /test:repository/);
  assert.equal(pkg.scripts["test:repository"], "node scripts/test-clean-checkout.mjs");
  assert.match(pkg.engines.node, />=20/);
});

test("Windows release validates and builds worker before packaging", () => {
  const releaseScript = readFileSync(path.join(root, "scripts/build-windows-release.mjs"), "utf8");
  assert.match(releaseScript, /build-worker\.py/);
  assert.match(releaseScript, /FFMPEG_EXE/);
  assert.match(releaseScript, /process\.platform !== "win32"/);
});
