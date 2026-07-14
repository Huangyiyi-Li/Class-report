import { copyFileSync, existsSync, mkdirSync } from "node:fs";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const isWindows = process.platform === "win32";
const npmCommand = isWindows ? "npm.cmd" : "npm";
const npxCommand = isWindows ? "npx.cmd" : "npx";
const pythonCommand = process.env.PYTHON || "python";
const recorderDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

const env = {
  ...process.env,
  ELECTRON_MIRROR: process.env.ELECTRON_MIRROR || "https://npmmirror.com/mirrors/electron/",
  ELECTRON_BUILDER_BINARIES_MIRROR:
    process.env.ELECTRON_BUILDER_BINARIES_MIRROR ||
    "https://npmmirror.com/mirrors/electron-builder-binaries/",
};

function run(command, args, options = {}) {
  console.log(`Running ${command} ${args.join(" ")}`);
  const result = spawnSync(command, args, {
    env,
    stdio: "inherit",
    shell: isWindows,
    ...options,
  });
  if (result.error) console.error(result.error);
  if (result.status !== 0) {
    console.error(`${command} exited with status ${result.status} and signal ${result.signal || "none"}`);
    process.exit(result.status ?? 1);
  }
}

if (process.platform !== "win32") {
  console.error("Windows release inputs must be built and packaged on Windows.");
  process.exit(1);
}

const ffmpegSource = process.env.FFMPEG_EXE;
if (!ffmpegSource || !existsSync(ffmpegSource)) {
  console.error("Set FFMPEG_EXE to a trusted Windows ffmpeg.exe before packaging.");
  process.exit(1);
}
const ffmpegDestination = path.join(recorderDir, "build", "ffmpeg", "ffmpeg.exe");
mkdirSync(path.dirname(ffmpegDestination), { recursive: true });
copyFileSync(ffmpegSource, ffmpegDestination);

run(pythonCommand, ["scripts/build-worker.py"], { cwd: recorderDir });
run(npmCommand, ["run", "build"]);
const builderArgs = ["electron-builder", "--win", "nsis", "portable", "--x64", "--publish", "never"];
run(npxCommand, builderArgs);
