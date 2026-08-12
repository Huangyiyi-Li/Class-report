import { execFile } from "node:child_process";
import path from "node:path";

const DATA_DIRECTORY_NAME = "ClassroomRecorderData";
const MINIMUM_FREE_BYTES = 5 * 1024 ** 3;
const FIXED_DRIVES_COMMAND = [
  "$ErrorActionPreference = 'Stop'; ",
  "Get-CimInstance Win32_LogicalDisk -Filter 'DriveType=3' | ",
  "Select-Object DeviceID, FreeSpace, Size | ",
  "ConvertTo-Json -Compress",
].join("");

export function parseFixedDriveOutput(output) {
  const text = String(output || "")
    .replace(/^\uFEFF/, "")
    .trim();
  if (!text) return [];
  const parsed = JSON.parse(text);
  const rows = Array.isArray(parsed) ? parsed : [parsed];
  return rows
    .map((row) => ({
      deviceId: normalizeDrive(row?.DeviceID),
      freeSpace: finiteNumber(row?.FreeSpace),
      size: finiteNumber(row?.Size),
    }))
    .filter((row) => row.deviceId && row.freeSpace >= 0 && row.size > 0);
}

export function recordingDataRootCandidates(
  drives,
  { systemDrive = process.env.SystemDrive || "C:" } = {}
) {
  const blockedDrive = normalizeDrive(systemDrive);
  return [...(Array.isArray(drives) ? drives : [])]
    .map((drive) => ({
      deviceId: normalizeDrive(drive?.deviceId),
      freeSpace: finiteNumber(drive?.freeSpace),
      size: finiteNumber(drive?.size),
    }))
    .filter(
      (drive) =>
        drive.deviceId &&
        drive.deviceId !== blockedDrive &&
        drive.freeSpace >= MINIMUM_FREE_BYTES &&
        drive.size > 0
    )
    .sort(
      (left, right) =>
        right.freeSpace - left.freeSpace ||
        left.deviceId.localeCompare(right.deviceId)
    )
    .map((drive) =>
      path.win32.join(`${drive.deviceId}\\`, DATA_DIRECTORY_NAME)
    );
}

export async function discoverRecordingDataRoots({
  platform = process.platform,
  systemDrive = process.env.SystemDrive || "C:",
  run = runPowerShell,
} = {}) {
  if (platform !== "win32") return [];
  const output = await run(FIXED_DRIVES_COMMAND);
  return recordingDataRootCandidates(parseFixedDriveOutput(output), {
    systemDrive,
  });
}

export async function bootstrapFirstAvailableRecordingRoot({
  userDataDir,
  roots,
  bootstrap,
} = {}) {
  if (typeof bootstrap !== "function") {
    throw new TypeError("bootstrap must be a function");
  }
  for (const dataRoot of Array.isArray(roots) ? roots : []) {
    try {
      return await bootstrap({
        userDataDir,
        patch: { dataRoot },
      });
    } catch {}
  }
  return null;
}

function runPowerShell(command) {
  return new Promise((resolve, reject) => {
    execFile(
      "powershell.exe",
      ["-NoProfile", "-NonInteractive", "-Command", command],
      { encoding: "utf8", windowsHide: true, timeout: 10_000 },
      (error, stdout) => {
        if (error) reject(error);
        else resolve(stdout);
      }
    );
  });
}

function normalizeDrive(value) {
  const match = /^([A-Za-z]):/.exec(String(value || "").trim());
  return match ? `${match[1].toUpperCase()}:` : "";
}

function finiteNumber(value) {
  const number = Number(value);
  return Number.isFinite(number) ? number : -1;
}
