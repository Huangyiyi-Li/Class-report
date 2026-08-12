import assert from "node:assert/strict";
import test from "node:test";

import {
  bootstrapFirstAvailableRecordingRoot,
  discoverRecordingDataRoots,
  parseFixedDriveOutput,
  recordingDataRootCandidates,
} from "./windows-storage.js";

test("new installations prefer the fixed non-system drive with most free space", () => {
  const gib = 1024 ** 3;
  const roots = recordingDataRootCandidates(
    [
      { deviceId: "C:", freeSpace: 90 * gib, size: 100 * gib },
      { deviceId: "D:", freeSpace: 20 * gib, size: 50 * gib },
      { deviceId: "E:", freeSpace: 70 * gib, size: 80 * gib },
    ],
    { systemDrive: "C:" }
  );

  assert.deepEqual(roots, [
    "E:\\ClassroomRecorderData",
    "D:\\ClassroomRecorderData",
  ]);
});

test("drive selection never falls back to the Windows system drive", () => {
  assert.deepEqual(
    recordingDataRootCandidates(
      [{ deviceId: "C:", freeSpace: 900_000, size: 1_000_000 }],
      { systemDrive: "C:" }
    ),
    []
  );
});

test("drive selection excludes non-system disks below the recording safety threshold", () => {
  const gib = 1024 ** 3;
  assert.deepEqual(
    recordingDataRootCandidates(
      [
        { deviceId: "D:", freeSpace: 4 * gib, size: 100 * gib },
        { deviceId: "E:", freeSpace: 6 * gib, size: 100 * gib },
      ],
      { systemDrive: "C:" }
    ),
    ["E:\\ClassroomRecorderData"]
  );
});

test("PowerShell fixed-drive output accepts one drive or a drive list", () => {
  assert.deepEqual(
    parseFixedDriveOutput(
      '\ufeff{"DeviceID":"D:","FreeSpace":200000,"Size":500000}'
    ),
    [{ deviceId: "D:", freeSpace: 200000, size: 500000 }]
  );
  assert.equal(
    parseFixedDriveOutput(
      '[{"DeviceID":"D:","FreeSpace":"200000","Size":"500000"}]'
    )[0].freeSpace,
    200000
  );
});

test("Windows drive discovery separates setup from the PowerShell pipeline", async () => {
  let command = "";
  await discoverRecordingDataRoots({
    platform: "win32",
    systemDrive: "C:",
    run: async (value) => {
      command = value;
      return '[{"DeviceID":"D:","FreeSpace":10737418240,"Size":21474836480}]';
    },
  });

  assert.match(
    command,
    /^\$ErrorActionPreference = 'Stop'; Get-CimInstance/,
    "the preference assignment must not consume the disk query pipeline"
  );
});

test("first launch initializes the first usable non-system recording root", async () => {
  const attempts = [];
  const result = await bootstrapFirstAvailableRecordingRoot({
    userDataDir: "C:\\Users\\teacher\\AppData\\Local\\Recorder",
    roots: ["E:\\ClassroomRecorderData", "D:\\ClassroomRecorderData"],
    bootstrap: (options) => {
      attempts.push(options);
      if (options.patch.dataRoot.startsWith("E:")) {
        throw new Error("E drive is read-only");
      }
      return { dataRoot: options.patch.dataRoot, runtimeDir: "runtime" };
    },
  });

  assert.equal(result.dataRoot, "D:\\ClassroomRecorderData");
  assert.deepEqual(
    attempts.map((attempt) => attempt.patch),
    [
      { dataRoot: "E:\\ClassroomRecorderData" },
      { dataRoot: "D:\\ClassroomRecorderData" },
    ]
  );
});

test("first launch stays unconfigured when no non-system root is usable", async () => {
  assert.equal(
    await bootstrapFirstAvailableRecordingRoot({
      userDataDir: "C:\\Users\\teacher\\AppData\\Local\\Recorder",
      roots: ["D:\\ClassroomRecorderData"],
      bootstrap: () => {
        throw new Error("not writable");
      },
    }),
    null
  );
});
