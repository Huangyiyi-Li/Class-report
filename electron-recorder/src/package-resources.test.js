import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const repositoryRoot = path.resolve(root, "..");
const pkg = JSON.parse(readFileSync(path.join(root, "package.json"), "utf8"));

test("declares packaged worker and Windows FFmpeg resources", () => {
  assert.ok(pkg.build.extraResources.some((item) => item.from === "build/worker/ClassroomRecorderWorker.exe" && item.to === "worker/ClassroomRecorderWorker.exe"));
  assert.ok(pkg.build.extraResources.some((item) => item.from === "build/ffmpeg/ffmpeg.exe" && item.to === "ffmpeg/ffmpeg.exe"));
});

test("default test runs repository gate and declares supported Node versions", () => {
  assert.match(pkg.scripts.test, /test:repository/);
  assert.equal(pkg.scripts["test:repository"], "node scripts/test-clean-checkout.mjs");
  assert.equal(pkg.engines.node, "^20.19.0 || >=22.12.0");
});

test("Windows release validates and builds worker before packaging", () => {
  const releaseScript = readFileSync(path.join(root, "scripts/build-windows-release.mjs"), "utf8");
  assert.match(releaseScript, /build-worker\.py/);
  assert.match(releaseScript, /FFMPEG_EXE/);
  assert.match(releaseScript, /process\.platform !== "win32"/);
  assert.match(releaseScript, /"nsis", "portable"/);
  assert.doesNotMatch(releaseScript, /"zip"/);
});

test("worker build includes runtime upload and audio dependencies", () => {
  const buildWorker = readFileSync(path.join(root, "scripts/build-worker.py"), "utf8");
  assert.match(buildWorker, /"--paths",\s*str\(ROOT\.parent\)/);
  for (const dependency of ["sounddevice", "numpy", "windows_client.xxt_upload", "oss2"]) {
    assert.match(buildWorker, new RegExp(`--hidden-import.*${dependency.replaceAll(".", "\\.")}`, "s"));
  }
  assert.match(buildWorker, /--collect-(all|submodules).*oss2/s);
  assert.match(buildWorker, /--copy-metadata.*oss2/s);

  const requirements = readFileSync(path.join(root, "worker/requirements-build.txt"), "utf8");
  for (const dependency of ["pyinstaller", "sounddevice", "numpy", "oss2", "pytest"]) {
    assert.match(requirements.toLowerCase(), new RegExp(`^${dependency}(?:[<=>~!]|$)`, "m"));
  }
});

test("generated worker and FFmpeg inputs are explicitly ignored", () => {
  const gitignore = readFileSync(path.join(repositoryRoot, ".gitignore"), "utf8");
  assert.match(gitignore, /^electron-recorder\/build\/worker\/$/m);
  assert.match(gitignore, /^electron-recorder\/build\/ffmpeg\/$/m);
});

test("GitHub Windows workflow builds and uploads installer artifacts", () => {
  const workflow = readFileSync(path.join(repositoryRoot, ".github/workflows/windows-recorder.yml"), "utf8");
  assert.match(workflow, /runs-on:\s*windows-2022/);
  assert.match(workflow, /branches:\s*\n\s*- master/);
  assert.match(workflow, /tags:\s*\n\s*- ["']recorder-v\*/);
  assert.match(workflow, /Run Python checks/);
  assert.match(workflow, /Run Node\.js checks/);
  assert.match(workflow, /python scripts\/build-worker\.py/);
  assert.match(workflow, /npm run build/);
  assert.match(workflow, /electron-builder --win nsis portable --x64/);
  assert.match(workflow, /FFMPEG_EXE/);
  assert.match(workflow, /actions\/upload-artifact@v4/);
  assert.match(workflow, /gh release create/);
  assert.match(workflow, /--prerelease/);
  assert.match(workflow, /release\/\*\.exe/);
});

test("NSIS and portable installers use distinct artifact names", () => {
  assert.match(pkg.build.nsis.artifactName, /Setup/);
  assert.match(pkg.build.portable.artifactName, /Portable/);
  assert.notEqual(pkg.build.nsis.artifactName, pkg.build.portable.artifactName);
});
