import assert from "node:assert/strict";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import {
  RecorderBackend,
  deriveDeviceNoFromNetworkInterfaces,
  formatLocalDateTime,
  resolveDeviceNo,
  selectPhysicalMacFromWindowsAdapters,
} from "./backend.js";

test("formatLocalDateTime emits Java Date-compatible local ISO time", () => {
  const value = formatLocalDateTime(new Date(2026, 5, 1, 11, 21, 8, 456));
  assert.match(value, /^2026-06-01T11:21:08\.000[+-]\d{2}:\d{2}$/);
  assert.equal(value.includes("Z"), false);
});

test("deriveDeviceNoFromNetworkInterfaces skips virtual adapters and returns uppercase physical MAC", () => {
  const value = deriveDeviceNoFromNetworkInterfaces({
    lo0: [{ internal: true, mac: "00:00:00:00:00:00" }],
    "vEthernet (Default Switch)": [{ internal: false, mac: "08:00:58:00:00:01" }],
    "VirtualBox Host-Only Network": [{ internal: false, mac: "0A:00:27:00:00:12" }],
    ethernet: [{ internal: false, mac: "8C:88:4B:07:68:9D" }],
  });

  assert.equal(value, "8C884B07689D");
});

test("resolveDeviceNo prefers a normalized physical MAC and falls back to interfaces", () => {
  assert.equal(resolveDeviceNo({
    physicalMacResolver: () => "8c-88-4b-07-68-9d",
    networkInterfaces: () => ({ ethernet: [{ internal: false, mac: "AA:BB:CC:DD:EE:FF" }] }),
  }), "8C884B07689D");

  assert.equal(resolveDeviceNo({
    physicalMacResolver: () => "",
    networkInterfaces: () => ({ ethernet: [{ internal: false, mac: "AA:BB:CC:DD:EE:FF" }] }),
  }), "AABBCCDDEEFF");
});

test("selectPhysicalMacFromWindowsAdapters prefers active PCI or USB hardware adapters", () => {
  const value = selectPhysicalMacFromWindowsAdapters([
    {
      Name: "Virtual Ethernet Adapter",
      MACAddress: "08:00:58:00:00:01",
      PhysicalAdapter: true,
      NetEnabled: true,
      PNPDeviceID: "ROOT\\VMS_MP\\0000",
      InterfaceIndex: 4,
    },
    {
      Name: "Realtek PCIe GbE Family Controller",
      MACAddress: "8C:88:4B:07:68:9D",
      PhysicalAdapter: true,
      NetEnabled: true,
      PNPDeviceID: "PCI\\VEN_10EC&DEV_8168",
      InterfaceIndex: 12,
    },
  ]);

  assert.equal(value, "8C884B07689D");
});

test("init prefers Windows physical adapter MAC over network interface enumeration", async () => {
  const backend = new RecorderBackend({
    userDataPath: path.join(os.tmpdir(), `classroom-recorder-test-${Date.now()}`),
    physicalMacResolver: () => "8C-88-4B-07-68-9D",
    networkInterfaces: () => ({
      "vEthernet (Default Switch)": [{ internal: false, mac: "08:00:58:00:00:01" }],
    }),
  });

  await backend.init();

  assert.equal(backend.config.deviceNo, "8C884B07689D");
  assert.equal(backend.config.code, "8C884B07689D");
  assert.equal(backend.config.deviceNoSource, "mac");
  assert.equal(backend.config.autoLaunchEnabled, false);
});

test("updateConfig keeps device numbers MAC-based and persists auto launch preference", async () => {
  const backend = new RecorderBackend({
    userDataPath: path.join(os.tmpdir(), `classroom-recorder-test-${Date.now()}`),
    physicalMacResolver: () => "",
    networkInterfaces: () => ({
      wifi: [{ internal: false, mac: "AA-BB-CC-DD-EE-FF" }],
    }),
  });
  await backend.init();

  await backend.updateConfig({
    deviceNo: "manual-device",
    code: "manual-code",
    autoLaunchEnabled: false,
  });

  assert.equal(backend.config.deviceNo, "AABBCCDDEEFF");
  assert.equal(backend.config.code, "AABBCCDDEEFF");
  assert.equal(backend.config.autoLaunchEnabled, false);
});

test("audio segment metadata stores timezone-qualified local time strings", async () => {
  const backend = new RecorderBackend({
    userDataPath: path.join(os.tmpdir(), `classroom-recorder-test-${Date.now()}`),
  });
  await backend.init();
  backend.flushQueue = async () => [];

  await backend.enqueueAudioSegment({
    bytes: Buffer.from("abc"),
    mimeType: "audio/ogg;codecs=opus",
    codec: "opus",
    rate: 16000,
    bits: 16,
    channel: 1,
    startTime: new Date(2026, 5, 1, 11, 21, 8).toISOString(),
    endTime: new Date(2026, 5, 1, 11, 26, 8).toISOString(),
  });

  assert.match(backend.queue[0].startTime, /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.000[+-]\d{2}:\d{2}$/);
  assert.equal(backend.queue[0].startTime.includes("Z"), false);
  assert.equal(backend.queue[0].format, "ogg");
  assert.equal(backend.queue[0].codec, "opus");
  assert.equal(backend.queue[0].rate, 16000);
  assert.equal(backend.queue[0].bits, 16);
  assert.equal(backend.queue[0].channel, 1);
});

test("audio file info payload normalizes old local queue timestamps", async () => {
  const backend = new RecorderBackend({
    userDataPath: path.join(os.tmpdir(), `classroom-recorder-test-${Date.now()}`),
  });
  await backend.init();

  const payload = await backend.buildAudioFileInfoPayload({
    code: "TEST-DEVICE-ALPHA",
    schoolId: 90001,
    unitId: 700002,
    segmentIndex: 1,
    localPath: new URL(import.meta.url),
    uploadedFilePath: "https://example.test/audio.ogg",
    format: "ogg",
    mimeType: "audio/ogg;codecs=opus",
    codec: "opus",
    startTime: "2026-06-02 10:57:06",
    endTime: "2026-06-02 11:02:06",
  });

  assert.match(payload.startTime, /^2026-06-02T10:57:06\.000[+-]\d{2}:\d{2}$/);
  assert.match(payload.endTime, /^2026-06-02T11:02:06\.000[+-]\d{2}:\d{2}$/);
  assert.equal(payload.format, "ogg");
  assert.equal(payload.codec, "opus");
  assert.equal(payload.rate, 16000);
  assert.equal(payload.bits, 16);
  assert.equal(payload.channel, 1);
});

test("flushQueue keeps paused status after uploading pre-pause audio", async () => {
  const backend = new RecorderBackend({
    userDataPath: path.join(os.tmpdir(), `classroom-recorder-test-${Date.now()}`),
  });
  await backend.init();
  backend.queue = [
    {
      segmentIndex: 1,
      status: "uploaded",
      format: "ogg",
      lastError: "",
      uploadedFilePath: "https://example.test/audio.ogg",
    },
  ];
  backend.saveAudioFileInfo = async () => {};
  backend.saveQueue = async () => {};
  backend.setStatus("paused");

  await backend.flushQueue();

  assert.equal(backend.getSnapshot().status, "paused");
  assert.equal(backend.queue[0].status, "metadata_saved");
});

test("flushQueue uploads and registers supported ogg opus queue items", async () => {
  const backend = new RecorderBackend({
    userDataPath: path.join(os.tmpdir(), `classroom-recorder-test-${Date.now()}`),
  });
  await backend.init();
  backend.queue = [
    {
      segmentIndex: 1,
      status: "pending_upload",
      format: "ogg",
      mimeType: "audio/ogg;codecs=opus",
      codec: "opus",
      lastError: "",
      uploadedFilePath: "",
    },
  ];
  let uploaded = false;
  let registered = false;
  backend.uploadToOss = async () => {
    uploaded = true;
    return "https://example.test/audio.ogg";
  };
  backend.saveAudioFileInfo = async () => {
    registered = true;
  };
  backend.saveQueue = async () => {};

  await backend.flushQueue();

  assert.equal(uploaded, true);
  assert.equal(registered, true);
  assert.equal(backend.queue[0].status, "metadata_saved");
});

test("flushQueue does not upload unsupported webm queue items", async () => {
  const backend = new RecorderBackend({
    userDataPath: path.join(os.tmpdir(), `classroom-recorder-test-${Date.now()}`),
  });
  await backend.init();
  backend.queue = [
    {
      segmentIndex: 1,
      status: "pending_upload",
      format: "webm",
      lastError: "",
      uploadedFilePath: "",
    },
  ];
  let uploaded = false;
  backend.uploadToOss = async () => {
    uploaded = true;
  };

  await backend.flushQueue();

  assert.equal(uploaded, false);
  assert.equal(backend.queue[0].status, "unsupported_format");
  assert.match(backend.queue[0].lastError, /不支持 webm/);
});
