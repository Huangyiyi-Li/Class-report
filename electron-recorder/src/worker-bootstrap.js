import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";

const CONFIG_DEFAULTS = {
  data_root: "", base_url: "https://rest.xxt.cn", device_no: "", school_id: null,
  location_id: "", location_name: "", segment_seconds: 300, checkpoint_seconds: 10,
  auto_record_enabled: false, input_device: "", username: "", password: "", mirror_server_url: "",
};

export function atomicWriteJson(target, payload) {
  fs.mkdirSync(path.dirname(target), { recursive: true });
  const temporary = `${target}.tmp-${crypto.randomUUID()}`;
  let descriptor;
  try {
    descriptor = fs.openSync(temporary, "wx", 0o600);
    fs.writeFileSync(descriptor, `${JSON.stringify(payload, null, 2)}\n`, "utf8");
    fs.fsyncSync(descriptor);
    fs.closeSync(descriptor);
    descriptor = undefined;
    fs.renameSync(temporary, target);
    if (process.platform !== "win32") {
      let directory;
      try {
        directory = fs.openSync(path.dirname(target), "r");
        fs.fsyncSync(directory);
      } catch {} finally {
        if (directory !== undefined) fs.closeSync(directory);
      }
    }
  } catch (error) {
    if (descriptor !== undefined) fs.closeSync(descriptor);
    try { fs.unlinkSync(temporary); } catch {}
    throw error;
  }
  try { fs.chmodSync(target, 0o600); } catch {}
}

export function validateBootstrapDataRoot(dataRoot, { platform = process.platform, systemDrive = process.env.SystemDrive || "C:" } = {}) {
  const absolute = platform === "win32" ? path.win32.isAbsolute(dataRoot || "") : path.isAbsolute(dataRoot || "");
  if (!absolute) throw new Error("录音数据目录必须是绝对路径");
  if (platform === "win32") {
    if (dataRoot.startsWith("\\\\")) throw new Error("录音数据目录不允许使用网络路径");
    const drive = path.win32.parse(dataRoot).root.slice(0, 2).toUpperCase();
    if (!drive || drive === systemDrive.slice(0, 2).toUpperCase()) throw new Error("录音数据必须保存到非系统盘");
  }
  return dataRoot;
}

export function bootstrapWorkerConfig({ userDataDir, patch }) {
  validateBootstrapDataRoot(patch?.dataRoot);
  const dataRoot = fs.realpathSync.native(patch.dataRoot);
  const located = loadWorkerLocator(userDataDir);
  if (located && located.dataRoot !== dataRoot) {
    throw new Error("录音数据目录首次部署后不可修改，需重新部署");
  }
  const configPath = path.join(dataRoot, ".classroom-recorder", "worker-config.json");
  let existing = {};
  try { existing = JSON.parse(fs.readFileSync(configPath, "utf8")); } catch {}
  const config = {
    ...CONFIG_DEFAULTS,
    ...existing,
    data_root: dataRoot,
    auto_record_enabled: Boolean(patch.autoRecordEnabled ?? existing.auto_record_enabled),
    input_device: patch.inputDevice === "default" ? "" : String(patch.inputDevice ?? existing.input_device ?? ""),
  };
  atomicWriteJson(configPath, config);
  atomicWriteJson(path.join(userDataDir, "worker-config-locator.json"), { configPath, dataRoot });
  return { configPath, runtimeDir: path.join(dataRoot, "runtime"), dataRoot };
}

export function loadWorkerLocator(userDataDir, validationOptions = {}) {
  try {
    const locator = JSON.parse(fs.readFileSync(path.join(userDataDir, "worker-config-locator.json"), "utf8"));
    if (typeof locator.dataRoot !== "string" || typeof locator.configPath !== "string") return null;
    validateBootstrapDataRoot(locator.dataRoot, validationOptions);
    if (!path.isAbsolute(locator.configPath)) return null;
    const root = fs.realpathSync.native(locator.dataRoot);
    const expected = path.join(root, ".classroom-recorder", "worker-config.json");
    if (path.resolve(locator.configPath) !== path.resolve(path.join(locator.dataRoot, ".classroom-recorder", "worker-config.json"))) return null;
    if (fs.realpathSync.native(locator.configPath) !== expected) return null;
    const config = JSON.parse(fs.readFileSync(locator.configPath, "utf8"));
    if (typeof config.data_root !== "string" || fs.realpathSync.native(config.data_root) !== root) return null;
    return { configPath: expected, runtimeDir: path.join(root, "runtime"), dataRoot: root };
  } catch {
    return null;
  }
}
