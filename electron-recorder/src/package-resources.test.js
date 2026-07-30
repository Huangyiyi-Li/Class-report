import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const repositoryRoot = path.resolve(root, "..");
const pkg = JSON.parse(readFileSync(path.join(root, "package.json"), "utf8"));

test("packages every relative module imported by the Electron main process", () => {
  const packaged = new Set(pkg.build.files);
  const visited = new Set();

  function verifyModule(relativePath) {
    if (visited.has(relativePath)) return;
    visited.add(relativePath);
    assert.ok(
      packaged.has(relativePath),
      `${relativePath} is imported at runtime but excluded from build.files`
    );
    const source = readFileSync(path.join(root, relativePath), "utf8");
    for (const match of source.matchAll(/from\s+["'](\.\/.+?)["']/g)) {
      verifyModule(
        path.posix.normalize(
          path.posix.join(path.posix.dirname(relativePath), match[1])
        )
      );
    }
  }

  verifyModule(pkg.main);
});

test("declares packaged worker and Windows FFmpeg resources", () => {
  assert.ok(
    pkg.build.extraResources.some(
      (item) =>
        item.from === "build/worker/ClassroomRecorderWorker.exe" &&
        item.to === "worker/ClassroomRecorderWorker.exe"
    )
  );
  assert.ok(
    pkg.build.extraResources.some(
      (item) =>
        item.from === "build/ffmpeg/ffmpeg.exe" &&
        item.to === "ffmpeg/ffmpeg.exe"
    )
  );
});

test("default test runs repository gate and declares supported Node versions", () => {
  assert.match(pkg.scripts.test, /test:repository/);
  assert.equal(
    pkg.scripts["test:repository"],
    "node scripts/test-clean-checkout.mjs"
  );
  assert.equal(pkg.engines.node, ">=22.22.1");
});

test("Windows release validates and builds worker before packaging", () => {
  const releaseScript = readFileSync(
    path.join(root, "scripts/build-windows-release.mjs"),
    "utf8"
  );
  assert.match(releaseScript, /build-worker\.py/);
  assert.match(releaseScript, /FFMPEG_EXE/);
  assert.match(releaseScript, /process\.platform !== "win32"/);
  assert.match(releaseScript, /shell:\s*isWindows/);
  assert.match(
    releaseScript,
    /copyFileSync\(ffmpegSource, ffmpegDestination\)/
  );
  assert.match(releaseScript, /"nsis", "portable"/);
  assert.doesNotMatch(releaseScript, /"zip"/);
});

test("worker build includes runtime upload and audio dependencies", () => {
  const buildWorker = readFileSync(
    path.join(root, "scripts/build-worker.py"),
    "utf8"
  );
  assert.match(
    buildWorker,
    /["']--noconsole["']/,
    "packaged worker must not open a console window during normal startup"
  );
  assert.match(buildWorker, /"--paths",\s*str\(ROOT\.parent\)/);
  for (const dependency of [
    "sounddevice",
    "numpy",
    "windows_client.xxt_upload",
    "oss2",
  ]) {
    assert.match(
      buildWorker,
      new RegExp(`--hidden-import.*${dependency.replaceAll(".", "\\.")}`, "s")
    );
  }
  assert.match(buildWorker, /--collect-(all|submodules).*oss2/s);
  assert.match(buildWorker, /--copy-metadata.*oss2/s);

  const requirements = readFileSync(
    path.join(root, "worker/requirements-build.txt"),
    "utf8"
  );
  for (const dependency of [
    "pyinstaller",
    "sounddevice",
    "numpy",
    "oss2",
    "pytest",
  ]) {
    assert.match(
      requirements.toLowerCase(),
      new RegExp(`^${dependency}(?:[<=>~!]|$)`, "m")
    );
  }
});

test("generated worker and FFmpeg inputs are explicitly ignored", () => {
  const gitignore = readFileSync(
    path.join(repositoryRoot, ".gitignore"),
    "utf8"
  );
  assert.match(gitignore, /^electron-recorder\/build\/worker\/$/m);
  assert.match(gitignore, /^electron-recorder\/build\/ffmpeg\/$/m);
});

test("GitHub Windows workflow builds and validates installer artifacts", () => {
  const workflow = readFileSync(
    path.join(repositoryRoot, ".github/workflows/windows-recorder.yml"),
    "utf8"
  );
  assert.match(workflow, /runs-on:\s*windows-2022/);
  assert.match(workflow, /branches:\s*\n\s*- master/);
  assert.match(workflow, /tags:\s*\n\s*- ["']recorder-v\*/);
  assert.match(workflow, /["']v\*-codex\.\*["']/);
  assert.match(workflow, /Run Python checks/);
  assert.match(workflow, /Run Node\.js checks/);
  assert.match(workflow, /python scripts\/build-worker\.py/);
  assert.match(workflow, /npm run build/);
  assert.match(workflow, /electron-builder --win nsis portable --x64/);
  assert.match(workflow, /Run packaged application smoke test/);
  assert.match(workflow, /Run packaged normal-start test/);
  assert.match(workflow, /test-packaged-normal-start\.ps1/);
  assert.match(workflow, /ELECTRON_SMOKE_TEST/);
  assert.match(workflow, /BINDING_SERVICE_MODE\s*=\s*["']mock["']/);
  assert.match(workflow, /RedirectStandardOutput/);
  assert.match(workflow, /RedirectStandardError/);
  assert.match(workflow, /FFMPEG_EXE/);
});

test("packaged normal-start gate launches the real worker without smoke mode", () => {
  const script = readFileSync(
    path.join(root, "scripts/test-packaged-normal-start.ps1"),
    "utf8"
  );
  assert.match(script, /Remove-Item Env:ELECTRON_SMOKE_TEST/);
  assert.match(script, /worker-endpoint\.json/);
  assert.match(script, /worker-token/);
  assert.match(script, /TcpClient/);
  assert.match(script, /MainWindowHandle/);
  assert.match(script, /Sort-Object StartTime -Descending/);
  assert.match(
    script,
    /Start-Sleep -Seconds 1[\s\S]*Get-Process -Name ClassroomRecorderWorker/
  );
});

test("NSIS and portable installers use distinct artifact names", () => {
  assert.match(pkg.build.nsis.artifactName, /Setup/);
  assert.match(pkg.build.portable.artifactName, /Portable/);
  assert.notEqual(pkg.build.nsis.artifactName, pkg.build.portable.artifactName);
});

test("installed Windows builds declare GitHub differential update metadata", () => {
  assert.ok(pkg.dependencies["electron-updater"]);
  assert.deepEqual(pkg.build.publish, [
    {
      provider: "github",
      owner: "Huangyiyi-Li",
      repo: "Class-report",
      releaseType: "prerelease",
      channel: "codex",
    },
  ]);

  const workflow = readFileSync(
    path.join(repositoryRoot, ".github/workflows/windows-recorder.yml"),
    "utf8"
  );
  assert.match(workflow, /Upload updater metadata/);
  assert.match(workflow, /\*\.yml/);
  assert.match(workflow, /\*\.blockmap/);
  assert.match(workflow, /Download updater metadata/);
  assert.match(workflow, /Get-ChildItem release -File/);
  const metadataUpload = workflow.match(
    /- name: Upload updater metadata[\s\S]*?(?=\n\s{2}publish-github-prerelease:)/
  )?.[0];
  assert.ok(metadataUpload);
  assert.doesNotMatch(metadataUpload, /archive:\s*false/);
});

test("Passport BrowserWindow applies the display-aware layout and zoom factor", () => {
  const main = readFileSync(path.join(root, "src/main.js"), "utf8");
  assert.match(main, /getPassportWindowLayout/);
  assert.match(main, /workAreaSize/);
  assert.match(main, /zoomFactor:\s*passportLayout\.zoomFactor/);
});
