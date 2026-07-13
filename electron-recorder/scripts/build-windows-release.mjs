import { cpSync, existsSync, rmSync, symlinkSync } from "node:fs";
import { homedir } from "node:os";
import path from "node:path";
import { spawnSync } from "node:child_process";

const isWindows = process.platform === "win32";
const npmCommand = isWindows ? "npm.cmd" : "npm";
const npxCommand = isWindows ? "npx.cmd" : "npx";

const env = {
  ...process.env,
  ELECTRON_MIRROR: process.env.ELECTRON_MIRROR || "https://npmmirror.com/mirrors/electron/",
  ELECTRON_BUILDER_BINARIES_MIRROR:
    process.env.ELECTRON_BUILDER_BINARIES_MIRROR ||
    "https://npmmirror.com/mirrors/electron-builder-binaries/",
};

function run(command, args, options = {}) {
  const result = spawnSync(command, args, {
    env,
    stdio: "inherit",
    shell: false,
    ...options,
  });
  if (result.status !== 0) process.exit(result.status ?? 1);
}

function tryRun(command, args) {
  return spawnSync(command, args, {
    env,
    stdio: "inherit",
    shell: false,
  }).status ?? 1;
}

function output(command, args) {
  const result = spawnSync(command, args, {
    env,
    encoding: "utf8",
    shell: false,
  });
  return result.status === 0 ? result.stdout.trim() : "";
}

function prepareAppleSiliconNsis() {
  if (process.platform !== "darwin" || process.arch !== "arm64") return;

  const cacheNsisDir = path.join(
    homedir(),
    "Library/Caches/electron-builder/nsis/nsis-3.0.4.1-nsis-3.0.4.1",
  );

  if (!existsSync(cacheNsisDir)) {
    tryRun(npxCommand, ["electron-builder", "--win", "nsis", "--x64", "--publish", "never"]);
  }

  if (!existsSync(cacheNsisDir)) {
    console.error("未找到 electron-builder 的 NSIS 缓存，请重新运行本命令。");
    process.exit(1);
  }

  const makensis = output("which", ["makensis"]);
  if (!makensis) {
    console.error("Apple Silicon Mac 需要先安装 makensis：brew install makensis");
    process.exit(1);
  }

  const nsisShareDir = output("brew", ["--prefix", "makensis"]);
  const homebrewNsisDir = nsisShareDir ? path.join(nsisShareDir, "share", "nsis") : "";
  if (!homebrewNsisDir || !existsSync(homebrewNsisDir)) {
    console.error("未找到 Homebrew NSIS 目录，请先运行：brew install makensis");
    process.exit(1);
  }

  const bridgeDir = "/tmp/electron-builder-nsis-arm64";
  rmSync(bridgeDir, { recursive: true, force: true });
  cpSync(homebrewNsisDir, bridgeDir, { recursive: true });
  cpSync(path.join(cacheNsisDir, "elevate.exe"), path.join(bridgeDir, "elevate.exe"));
  rmSync(path.join(bridgeDir, "mac"), { recursive: true, force: true });
  cpSync(path.join(cacheNsisDir, "mac"), path.join(bridgeDir, "mac"), { recursive: true });
  rmSync(path.join(bridgeDir, "mac", "makensis"), { force: true });
  symlinkSync(makensis, path.join(bridgeDir, "mac", "makensis"));
  env.ELECTRON_BUILDER_NSIS_DIR = bridgeDir;
}

run(npmCommand, ["run", "build"]);
prepareAppleSiliconNsis();
const builderArgs = ["electron-builder", "--win", "nsis", "zip", "--x64", "--publish", "never"];
if (process.platform === "darwin" && process.arch === "arm64") {
  builderArgs.push("--config.win.signAndEditExecutable=false");
}
run(npxCommand, builderArgs);
