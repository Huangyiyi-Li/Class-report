import fs from "node:fs";
import path from "node:path";

const CONFIG_DEFAULTS = {
  data_root: "", base_url: "https://rest.xxt.cn", device_no: "", school_id: null,
  location_id: "", location_name: "", segment_seconds: 300, checkpoint_seconds: 10,
  auto_record_enabled: false, input_device: "", username: "", password: "", mirror_server_url: "",
};

function atomicWriteJson(target, payload) {
  fs.mkdirSync(path.dirname(target), { recursive: true });
  const temporary = `${target}.tmp-${process.pid}-${Date.now()}`;
  const descriptor = fs.openSync(temporary, "w", 0o600);
  try {
    fs.writeFileSync(descriptor, `${JSON.stringify(payload, null, 2)}\n`, "utf8");
    fs.fsyncSync(descriptor);
  } finally {
    fs.closeSync(descriptor);
  }
  fs.renameSync(temporary, target);
  try { fs.chmodSync(target, 0o600); } catch {}
}

export function validateBootstrapDataRoot(dataRoot, { platform = process.platform, systemDrive = process.env.SystemDrive || "C:" } = {}) {
  const absolute = platform === "win32" ? path.win32.isAbsolute(dataRoot || "") : path.isAbsolute(dataRoot || "");
  if (!absolute) throw new Error("录音数据目录必须是绝对路径");
  if (platform === "win32") {
    const drive = path.win32.parse(dataRoot).root.slice(0, 2).toUpperCase();
    if (!drive || drive === systemDrive.slice(0, 2).toUpperCase()) throw new Error("录音数据必须保存到非系统盘");
  }
  return dataRoot;
}

export function bootstrapWorkerConfig({ userDataDir, patch }) {
  const dataRoot = validateBootstrapDataRoot(patch?.dataRoot);
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
  atomicWriteJson(path.join(userDataDir, "worker-config-locator.json"), { configPath });
  return { configPath, runtimeDir: path.join(dataRoot, "runtime"), dataRoot };
}

export function loadWorkerLocator(userDataDir) {
  try {
    const locator = JSON.parse(fs.readFileSync(path.join(userDataDir, "worker-config-locator.json"), "utf8"));
    if (!locator.configPath || !path.isAbsolute(locator.configPath)) return null;
    const config = JSON.parse(fs.readFileSync(locator.configPath, "utf8"));
    if (!config.data_root) return null;
    return { configPath: locator.configPath, runtimeDir: path.join(config.data_root, "runtime"), dataRoot: config.data_root };
  } catch {
    return null;
  }
}
