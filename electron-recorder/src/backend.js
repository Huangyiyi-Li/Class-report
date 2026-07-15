import crypto from "node:crypto";
import { execFileSync } from "node:child_process";
import { EventEmitter } from "node:events";
import fs from "node:fs/promises";
import https from "node:https";
import { createRequire } from "node:module";
import os from "node:os";
import path from "node:path";

const require = createRequire(import.meta.url);
const { version: APP_VERSION } = require("../package.json");

const DEFAULT_CONFIG = {
  baseUrl: "https://rest.xxt.cn",
  environmentName: "生产环境",
  deviceNo: "",
  schoolId: null,
  locationId: "",
  locationName: "",
  segmentSeconds: 300,
  checkpointSeconds: 10,
  autoLaunchEnabled: false,
  autoRecordEnabled: false,
  inputDevice: "",
};

const STATUS = {
  IDLE: "idle",
  RECORDING: "recording",
  PAUSED: "paused",
  UPLOADING: "uploading",
  NETWORK_ERROR: "network_error",
  MIC_ERROR: "mic_error",
};

export class RecorderBackend extends EventEmitter {
  constructor({
    userDataPath,
    networkInterfaces = os.networkInterfaces,
    physicalMacResolver = resolveWindowsPhysicalMac,
  }) {
    super();
    this.networkInterfaces = networkInterfaces;
    this.physicalMacResolver = physicalMacResolver;
    this.dataDir = path.join(userDataPath, "client-data");
    this.configPath = path.join(this.dataDir, "client.json");
    this.queuePath = path.join(this.dataDir, "queue.json");
    this.indexPath = path.join(this.dataDir, "segment-index.json");
    this.recordingsDir = path.join(this.dataDir, "recordings");
    this.logLines = [];
    this.diagnosticLines = [];
    this.status = STATUS.IDLE;
    this.level = 0;
    this.countdownSeconds = 0;
    this.lastSyncTime = "";
    this.deviceAuth = null;
    this.ossConfig = null;
    this.mirrorToken = "";
    this.config = { ...DEFAULT_CONFIG };
    this.retryTimer = null;
  }

  async init() {
    await fs.mkdir(this.dataDir, { recursive: true });
    await fs.mkdir(this.recordingsDir, { recursive: true });
    this.config = await this.loadJson(this.configPath, DEFAULT_CONFIG);
    this.config = { ...DEFAULT_CONFIG, ...this.config };
    this.applyMacDeviceNo();
    await this.writeJson(this.configPath, this.config);
    this.queue = await this.loadJson(this.queuePath, []);
    this.log("客户端后台已启动");
    this.startAutoRetry();
    this.broadcast();
  }

  getSnapshot() {
    const pending = this.queue?.filter((item) => !["metadata_saved", "unsupported_format"].includes(item.status)).length ?? 0;
    const completed = this.queue?.filter((item) => item.status === "metadata_saved").length ?? 0;
    return {
      status: this.status,
      level: this.level,
      countdownSeconds: this.countdownSeconds,
      pending,
      completed,
      lastSyncTime: this.lastSyncTime,
      appVersion: APP_VERSION,
      config: this.config,
      dataDir: this.dataDir,
      logs: this.logLines.slice(-80),
      diagnostics: this.diagnosticLines.slice(-120),
    };
  }

  setStatus(status) {
    this.status = status;
    this.broadcast();
  }

  setLevel(level) {
    this.level = Math.max(0, Math.min(1, Number(level) || 0));
    this.broadcast();
  }

  setCountdown(seconds) {
    this.countdownSeconds = Math.max(0, Math.round(Number(seconds) || 0));
    this.broadcast();
  }

  log(message, options = {}) {
    const line = `[${new Date().toLocaleTimeString("zh-CN", { hour12: false })}] ${message}`;
    if (options.diagnostic) {
      this.diagnosticLines.push(line);
      if (this.diagnosticLines.length > 240) this.diagnosticLines = this.diagnosticLines.slice(-240);
    } else {
      this.logLines.push(line);
      if (this.logLines.length > 200) this.logLines = this.logLines.slice(-200);
    }
    this.emit("log", line);
    this.broadcast();
  }

  async updateConfig(patch = {}) {
    const next = { ...this.config };
    for (const key of ["schoolId", "unitId", "segmentSeconds"]) {
      if (patch[key] !== undefined && patch[key] !== "") next[key] = Number(patch[key]);
    }
    if (patch.mirrorEnabled !== undefined) next.mirrorEnabled = Boolean(patch.mirrorEnabled);
    if (patch.autoLaunchEnabled !== undefined) next.autoLaunchEnabled = Boolean(patch.autoLaunchEnabled);
    this.config = next;
    this.applyMacDeviceNo();
    const normalized = { ...this.config };
    if (!Number.isFinite(next.schoolId)) next.schoolId = DEFAULT_CONFIG.schoolId;
    if (!Number.isFinite(next.unitId)) next.unitId = DEFAULT_CONFIG.unitId;
    if (!Number.isFinite(next.segmentSeconds) || next.segmentSeconds < 30) next.segmentSeconds = DEFAULT_CONFIG.segmentSeconds;
    normalized.schoolId = next.schoolId;
    normalized.unitId = next.unitId;
    normalized.segmentSeconds = next.segmentSeconds;
    this.config = normalized;
    this.deviceAuth = null;
    this.ossConfig = null;
    await this.writeJson(this.configPath, this.config);
    this.log("班级绑定配置已保存");
    this.broadcast();
    return this.getSnapshot();
  }

  applyMacDeviceNo() {
    const macDeviceNo =
      normalizeMacAddress(this.physicalMacResolver()) ||
      deriveDeviceNoFromNetworkInterfaces(this.networkInterfaces());
    if (!macDeviceNo) {
      this.config.deviceNoSource = "unavailable";
      if (!this.config.code) this.config.code = this.config.deviceNo;
      if (!this.config.deviceNo) this.config.deviceNo = this.config.code;
      return;
    }
    this.config.deviceNo = macDeviceNo;
    this.config.code = macDeviceNo;
    this.config.deviceNoSource = "mac";
  }

  async verifyBinding() {
    this.log("正在校验设备与班级绑定");
    const result = await this.ensureDeviceAuth(true);
    this.log(`绑定校验成功：${this.config.schoolName} · ${this.config.className}`);
    return result;
  }

  async enqueueAudioSegment({ bytes, mimeType, codec, rate, bits, channel, startTime, endTime }) {
    const started = parseInputDate(startTime);
    const ended = parseInputDate(endTime);
    const segmentIndex = await this.nextSegmentIndex(started);
    const ext = this.extensionForMimeType(mimeType);
    const day = this.formatDay(started);
    const fileName = `${this.config.code}_${day}_${String(segmentIndex).padStart(3, "0")}.${ext}`;
    const localDir = path.join(this.recordingsDir, day);
    const localPath = path.join(localDir, fileName);
    await fs.mkdir(localDir, { recursive: true });
    await fs.writeFile(localPath, Buffer.from(bytes));

    const item = {
      code: this.config.code,
      schoolId: this.config.schoolId,
      unitId: this.config.unitId,
      segmentIndex,
      localPath,
      startTime: formatLocalDateTime(started),
      endTime: formatLocalDateTime(ended),
      format: ext,
      mimeType,
      codec: codec || this.codecForMimeType(mimeType),
      rate: Number(rate || 16000),
      bits: Number(bits || 16),
      channel: Number(channel || 1),
      status: "pending_upload",
      uploadedFilePath: "",
      lastError: "",
    };
    this.queue.push(item);
    await this.saveQueue();
    this.log(`分段 ${segmentIndex} 已本地保存：${fileName}`);
    this.flushQueue().catch((error) => {
      this.log(`自动上传失败：${error.message}`);
      this.setStatus(STATUS.NETWORK_ERROR);
    });
    return item;
  }

  async flushQueue() {
    if (!this.queue?.length) return [];
    const touched = [];
    const previousStatus = this.status;
    this.setStatus(STATUS.UPLOADING);
    for (const item of this.queue) {
      if (["metadata_saved", "unsupported_format"].includes(item.status)) continue;
      try {
        if (!this.isSupportedAudioFormat(item.format)) {
          item.status = "unsupported_format";
          item.lastError = `转录接口不支持 ${item.format} 格式，请用新版客户端重新录制`;
          await this.saveQueue();
          this.log(`分段 ${item.segmentIndex} 未上传：${item.lastError}`);
          touched.push(item);
          continue;
        }
        if (item.status === "pending_upload" || item.status === "failed") {
          this.log(`开始上传分段 ${item.segmentIndex}`);
          item.uploadedFilePath = await this.uploadToOss(item);
          item.status = "uploaded";
          item.lastError = "";
          await this.saveQueue();
        }
        if (item.status === "uploaded") {
          this.log(`正在登记分段 ${item.segmentIndex} 音频信息`);
          await this.saveAudioFileInfo(item);
          item.status = "metadata_saved";
          item.lastError = "";
          this.lastSyncTime = new Date().toLocaleTimeString("zh-CN", { hour12: false });
          await this.saveQueue();
          this.log(`分段 ${item.segmentIndex} 上传并登记成功`);
        }
      } catch (error) {
        item.status = "failed";
        item.lastError = error.message;
        await this.saveQueue();
        this.log(`分段 ${item.segmentIndex} 上传失败，将自动重试：${error.message}`);
        touched.push(item);
        this.setStatus(STATUS.NETWORK_ERROR);
        throw error;
      }
      touched.push(item);
    }
    this.setStatus([STATUS.RECORDING, STATUS.PAUSED, STATUS.NETWORK_ERROR].includes(previousStatus) ? previousStatus : STATUS.IDLE);
    return touched;
  }

  async uploadToOss(item) {
    const deviceAuth = await this.ensureDeviceAuth();
    const ossConfig = await this.ensureOssConfig(deviceAuth.accessToken);
    const objectKey = `test/${this.formatDay(parseInputDate(item.startTime))}/${path.basename(item.localPath)}`;
    const body = await fs.readFile(item.localPath);
    this.log(`正在上传分段 ${item.segmentIndex} 音频文件`);
    await putObjectToOss({ ossConfig, objectKey, body, contentType: item.mimeType || "application/octet-stream" });
    this.log(`分段 ${item.segmentIndex} 音频文件上传完成`);
    return `https://${ossConfig.bucket}.${ossConfig.endPoint}/${objectKey}`;
  }

  async saveAudioFileInfo(item) {
    const token = (await this.ensureDeviceAuth()).accessToken;
    const payload = await this.buildAudioFileInfoPayload(item);
    try {
      await postJson(`${this.config.baseUrl}/book-reading/audio/save-audio-file-info`, payload, {
        "Device-Access-Token": token,
      });
    } catch (error) {
      const legacyPayload = {
        code: payload.code,
        segmentIndex: payload.segmentIndex,
        filePath: payload.filePath,
        fileSize: payload.fileSize,
        format: payload.format.toUpperCase(),
        startTime: new Date(payload.startTime).getTime(),
        endTime: new Date(payload.endTime).getTime(),
      };
      await postJson(`${this.config.baseUrl}/book-reading/audio/save-audio-file-info`, legacyPayload, {
        "Device-Access-Token": token,
      });
    }
    await this.tryMirrorMetadata(payload);
  }

  async buildAudioFileInfoPayload(item) {
    const stat = await fs.stat(item.localPath);
    return {
      code: item.code,
      schoolId: item.schoolId,
      unitId: item.unitId,
      segmentIndex: item.segmentIndex,
      filePath: item.uploadedFilePath,
      fileSize: Math.max(1, Math.round(stat.size / 1024)),
      format: item.format,
      codec: item.codec || this.codecForMimeType(item.mimeType),
      rate: Number(item.rate || 16000),
      bits: Number(item.bits || 16),
      channel: Number(item.channel || 1),
      startTime: formatLocalDateTime(parseInputDate(item.startTime)),
      endTime: formatLocalDateTime(parseInputDate(item.endTime)),
      uploadStatus: 1,
      failReason: "",
      audioType: this.config.audioType,
    };
  }

  async tryMirrorMetadata(payload) {
    if (!this.config.mirrorServerUrl || this.config.mirrorEnabled === false) return;
    try {
      if (!this.mirrorToken) {
        const login = await postJson(`${this.config.mirrorServerUrl}/api/login`, {
          username: this.config.mirrorUsername,
          password: this.config.mirrorPassword,
        });
        this.mirrorToken = login.token || "";
      }
      await postJson(`${this.config.mirrorServerUrl}/book-reading/audio/save-audio-file-info`, payload, {
        Authorization: `Bearer ${this.mirrorToken}`,
      });
      this.log("本地报告服务镜像完成", { diagnostic: true });
    } catch (error) {
      this.log(`本地报告服务镜像失败：${error.message}`, { diagnostic: true });
    }
  }

  async ensureDeviceAuth(force = false) {
    if (!force && this.deviceAuth && new Date(this.deviceAuth.expireDate).getTime() - Date.now() > 30 * 60 * 1000) {
      return this.deviceAuth;
    }
    const timestamp = Date.now();
    const sign = crypto.createHash("sha1").update(`${this.config.deviceNo}${this.config.deviceNo}`).digest("hex");
    const result = await postJson(`${this.config.baseUrl}/wisdom/book-reading/device-auth`, {
      deviceNo: this.config.deviceNo,
      sign,
      timestamp,
    });
    if (!result.accessToken) throw new Error(result.message || "设备认证失败");
    this.deviceAuth = result;
    this.config.schoolId = Number(result.schoolId || this.config.schoolId);
    this.config.unitId = Number(result.groupId || this.config.unitId);
    this.config.schoolName = result.schoolName || this.config.schoolName;
    this.config.className = result.groupName || this.config.className;
    await this.writeJson(this.configPath, this.config);
    return this.deviceAuth;
  }

  async ensureOssConfig(accessToken) {
    if (this.ossConfig && Number(this.ossConfig.expiration) - Date.now() > 30 * 60 * 1000) return this.ossConfig;
    this.log("正在获取上传凭证");
    const result = await postJson(
      `${this.config.baseUrl}/book-reading/ali-oss/get-ali-oss-upload-token`,
      {},
      { "Device-Access-Token": accessToken },
    );
    if (!result.accessKeyId) throw new Error(result.message || "获取 OSS 上传凭证失败");
    this.ossConfig = result;
    return this.ossConfig;
  }

  startAutoRetry() {
    if (this.retryTimer) clearInterval(this.retryTimer);
    this.retryTimer = setInterval(() => {
      const hasPending = this.queue?.some((item) => item.status !== "metadata_saved");
      if (!hasPending || this.status === STATUS.RECORDING || this.status === STATUS.UPLOADING) return;
      this.flushQueue().catch((error) => {
        this.log(`后台补传暂未成功：${error.message}`, { diagnostic: true });
      });
    }, 30 * 1000);
    this.retryTimer.unref?.();
  }

  async nextSegmentIndex(when) {
    const day = this.formatDay(when);
    const data = await this.loadJson(this.indexPath, {});
    if (data.date !== day) {
      data.date = day;
      data.lastIndex = 0;
    }
    data.lastIndex = Number(data.lastIndex || 0) + 1;
    await this.writeJson(this.indexPath, data);
    return data.lastIndex;
  }

  async saveQueue() {
    await this.writeJson(this.queuePath, this.queue);
    this.broadcast();
  }

  async loadJson(filePath, fallback) {
    try {
      return JSON.parse(await fs.readFile(filePath, "utf8"));
    } catch {
      return structuredClone(fallback);
    }
  }

  async writeJson(filePath, data) {
    await fs.mkdir(path.dirname(filePath), { recursive: true });
    await fs.writeFile(filePath, JSON.stringify(data, null, 2), "utf8");
  }

  formatDay(date) {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, "0");
    const day = String(date.getDate()).padStart(2, "0");
    return `${year}${month}${day}`;
  }

  extensionForMimeType(mimeType = "") {
    if (mimeType.includes("webm")) return "webm";
    if (mimeType.includes("mp4")) return "m4a";
    if (mimeType.includes("mpeg")) return "mp3";
    if (mimeType.includes("wav")) return "wav";
    if (mimeType.includes("ogg")) return "ogg";
    return "wav";
  }

  codecForMimeType(mimeType = "") {
    if (mimeType.includes("opus")) return "opus";
    return "raw";
  }

  isSupportedAudioFormat(format = "") {
    return ["raw", "wav", "mp3", "ogg"].includes(String(format).toLowerCase());
  }

  broadcast() {
    this.emit("snapshot", this.getSnapshot());
  }
}

export function formatLocalDateTime(date) {
  const normalized = new Date(date.getTime() - date.getMilliseconds());
  const year = normalized.getFullYear();
  const month = String(normalized.getMonth() + 1).padStart(2, "0");
  const day = String(normalized.getDate()).padStart(2, "0");
  const hours = String(normalized.getHours()).padStart(2, "0");
  const minutes = String(normalized.getMinutes()).padStart(2, "0");
  const seconds = String(normalized.getSeconds()).padStart(2, "0");
  const offsetMinutes = -normalized.getTimezoneOffset();
  const sign = offsetMinutes >= 0 ? "+" : "-";
  const absoluteOffset = Math.abs(offsetMinutes);
  const offsetHours = String(Math.floor(absoluteOffset / 60)).padStart(2, "0");
  const offsetRemainderMinutes = String(absoluteOffset % 60).padStart(2, "0");
  return `${year}-${month}-${day}T${hours}:${minutes}:${seconds}.000${sign}${offsetHours}:${offsetRemainderMinutes}`;
}

export function deriveDeviceNoFromNetworkInterfaces(networkInterfaces = {}) {
  const physicalCandidates = Object.entries(networkInterfaces)
    .filter(([name]) => !isVirtualInterfaceName(name))
    .sort(([leftName], [rightName]) => interfacePriority(leftName) - interfacePriority(rightName));

  for (const [, entries] of physicalCandidates) {
    for (const entry of entries || []) {
      if (entry?.internal) continue;
      const normalized = normalizeMacAddress(entry?.mac);
      if (normalized) return normalized;
    }
  }
  return "";
}

export function resolveDeviceNo({
  physicalMacResolver = resolveWindowsPhysicalMac,
  networkInterfaces = os.networkInterfaces,
} = {}) {
  return normalizeMacAddress(physicalMacResolver()) ||
    deriveDeviceNoFromNetworkInterfaces(networkInterfaces());
}

function normalizeMacAddress(mac) {
  const normalized = String(mac || "").replace(/[^0-9a-f]/gi, "").toUpperCase();
  if (!normalized || /^0+$/.test(normalized)) return "";
  return normalized;
}

function resolveWindowsPhysicalMac() {
  if (process.platform !== "win32") return "";
  const script =
    "Get-CimInstance Win32_NetworkAdapter -ErrorAction SilentlyContinue | " +
    "Select-Object Name,MACAddress,PhysicalAdapter,NetEnabled,NetConnectionStatus,PNPDeviceID,InterfaceIndex | " +
    "ConvertTo-Json -Compress";
  try {
    const output = execFileSync(
      "powershell.exe",
      ["-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", script],
      { encoding: "utf8", timeout: 5000, windowsHide: true },
    ).trim();
    const parsed = JSON.parse(output || "[]");
    return selectPhysicalMacFromWindowsAdapters(Array.isArray(parsed) ? parsed : [parsed]);
  } catch {
    return "";
  }
}

export function selectPhysicalMacFromWindowsAdapters(adapters = []) {
  const physical = adapters
    .filter((adapter) => adapter?.PhysicalAdapter === true)
    .filter((adapter) => normalizeMacAddress(adapter?.MACAddress))
    .filter((adapter) => !isVirtualWindowsAdapter(adapter));
  const hardwareBus = physical.filter((adapter) => /^(PCI|USB)\\/i.test(String(adapter?.PNPDeviceID || "")));
  const candidates = hardwareBus.length ? hardwareBus : physical;
  candidates.sort((left, right) => {
    const activeDifference = adapterActivePriority(left) - adapterActivePriority(right);
    if (activeDifference) return activeDifference;
    const busDifference = adapterBusPriority(left) - adapterBusPriority(right);
    if (busDifference) return busDifference;
    return Number(left?.InterfaceIndex || Number.MAX_SAFE_INTEGER) - Number(right?.InterfaceIndex || Number.MAX_SAFE_INTEGER);
  });
  return normalizeMacAddress(candidates[0]?.MACAddress);
}

function adapterActivePriority(adapter) {
  return adapter?.NetEnabled === true || Number(adapter?.NetConnectionStatus) === 2 ? 0 : 1;
}

function adapterBusPriority(adapter) {
  const pnpDeviceId = String(adapter?.PNPDeviceID || "");
  if (/^PCI\\/i.test(pnpDeviceId)) return 0;
  if (/^USB\\/i.test(pnpDeviceId)) return 1;
  return 2;
}

function isVirtualWindowsAdapter(adapter) {
  const name = String(adapter?.Name || "");
  const pnpDeviceId = String(adapter?.PNPDeviceID || "");
  return isVirtualInterfaceName(name) || /^(ROOT|SWD|HTREE)\\/i.test(pnpDeviceId);
}

function isVirtualInterfaceName(name) {
  return /virtual|vethernet|hyper-v|vmware|virtualbox|loopback|tunnel|tap|tun|vpn|docker|wsl|npcap|teredo|isatap|bluetooth|本地连接\*|虚拟|蓝牙|桥接/i.test(
    String(name || ""),
  );
}

function interfacePriority(name) {
  return /^(ethernet|以太网|wi-?fi|wlan|无线)/i.test(String(name || "")) ? 0 : 1;
}

function parseInputDate(value) {
  if (value instanceof Date) return value;
  const text = String(value || "");
  if (/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$/.test(text)) {
    const [datePart, timePart] = text.split(" ");
    const [year, month, day] = datePart.split("-").map(Number);
    const [hours, minutes, seconds] = timePart.split(":").map(Number);
    return new Date(year, month - 1, day, hours, minutes, seconds);
  }
  return new Date(text);
}

async function postJson(url, payload, headers = {}) {
  const response = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
      ...headers,
    },
    body: JSON.stringify(payload),
  });
  const text = await response.text();
  let data = {};
  try {
    data = text ? JSON.parse(text) : {};
  } catch {
    data = { content: text };
  }
  if (!response.ok) throw new Error(`HTTP ${response.status}: ${text}`);
  return data;
}

function putObjectToOss({ ossConfig, objectKey, body, contentType }) {
  return new Promise((resolve, reject) => {
    const date = new Date().toUTCString();
    const resource = `/${ossConfig.bucket}/${objectKey}`;
    const canonicalizedOssHeaders = `x-oss-security-token:${ossConfig.securityToken}\n`;
    const stringToSign = `PUT\n\n${contentType}\n${date}\n${canonicalizedOssHeaders}${resource}`;
    const signature = crypto
      .createHmac("sha1", ossConfig.accessKeySecret)
      .update(stringToSign)
      .digest("base64");
    const request = https.request(
      {
        method: "PUT",
        hostname: `${ossConfig.bucket}.${ossConfig.endPoint}`,
        path: `/${objectKey}`,
        headers: {
          Authorization: `OSS ${ossConfig.accessKeyId}:${signature}`,
          Date: date,
          "Content-Type": contentType,
          "Content-Length": body.length,
          "x-oss-security-token": ossConfig.securityToken,
        },
      },
      (response) => {
        response.resume();
        response.on("end", () => {
          if (response.statusCode >= 200 && response.statusCode < 300) resolve();
          else reject(new Error(`OSS 上传失败: HTTP ${response.statusCode}`));
        });
      },
    );
    request.on("error", reject);
    request.end(body);
  });
}
