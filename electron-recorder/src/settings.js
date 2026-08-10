import fs from "node:fs";
import path from "node:path";
import {
  atomicWriteJson,
  validateBootstrapDataRoot,
} from "./worker-bootstrap.js";
import {
  PRODUCTION_API_ROUTES,
  migrateOfficialApiRoutes,
} from "./api-routes.js";

export const DEFAULT_SETTINGS = Object.freeze({
  autoLaunch: false,
  autoRecordEnabled: true,
  inputDevice: "default",
  apiRoutes: PRODUCTION_API_ROUTES,
});

const PERSISTED_KEYS = new Set(Object.keys(DEFAULT_SETTINGS));
const RUNTIME_KEYS = new Set([
  "autoRecordEnabled",
  "inputDevice",
  "dataRoot",
  "apiRoutes",
]);

function requirePlainObject(value, label) {
  if (
    !value ||
    typeof value !== "object" ||
    Array.isArray(value) ||
    Object.getPrototypeOf(value) !== Object.prototype
  ) {
    throw new TypeError(`${label} must be a plain object`);
  }
}

function validateText(value, name, maxLength, { allowEmpty = false } = {}) {
  if (typeof value !== "string")
    throw new TypeError(`${name} must be a string`);
  const normalized = value.trim();
  if (!allowEmpty && !normalized)
    throw new TypeError(`${name} must not be empty`);
  if (normalized.length > maxLength)
    throw new TypeError(`${name} exceeds ${maxLength} characters`);
  if (/\0|[\r\n]/u.test(normalized))
    throw new TypeError(`${name} contains invalid characters`);
  return normalized;
}

export function validateAutoLaunchValue(value) {
  if (typeof value !== "boolean")
    throw new TypeError("autoLaunch must be boolean");
  return value;
}

export function validateSettingsPatch(patch, options = {}) {
  requirePlainObject(patch, "settings patch");
  const unknown = Object.keys(patch).filter((key) => !RUNTIME_KEYS.has(key));
  if (unknown.length)
    throw new TypeError(
      `settings patch contains forbidden field: ${unknown[0]}`
    );
  const validated = {};
  if (Object.hasOwn(patch, "autoRecordEnabled")) {
    if (typeof patch.autoRecordEnabled !== "boolean")
      throw new TypeError("autoRecordEnabled must be boolean");
    validated.autoRecordEnabled = patch.autoRecordEnabled;
  }
  if (Object.hasOwn(patch, "inputDevice"))
    validated.inputDevice = validateText(patch.inputDevice, "inputDevice", 256);
  if (Object.hasOwn(patch, "dataRoot")) {
    const root = validateText(patch.dataRoot, "dataRoot", 1024);
    validateBootstrapDataRoot(root, options);
    validated.dataRoot = root;
  }
  if (Object.hasOwn(patch, "apiRoutes")) {
    validated.apiRoutes = migrateOfficialApiRoutes(patch.apiRoutes);
  }
  return validated;
}

function validatePersisted(payload) {
  requirePlainObject(payload, "persisted settings");
  if (Object.keys(payload).some((key) => !PERSISTED_KEYS.has(key)))
    throw new TypeError("persisted settings contain unknown fields");
  return {
    autoLaunch: validateAutoLaunchValue(payload.autoLaunch),
    autoRecordEnabled: validateSettingsPatch({
      autoRecordEnabled: payload.autoRecordEnabled,
    }).autoRecordEnabled,
    inputDevice: validateSettingsPatch({ inputDevice: payload.inputDevice })
      .inputDevice,
    apiRoutes: Object.hasOwn(payload, "apiRoutes")
      ? migrateOfficialApiRoutes(payload.apiRoutes)
      : { ...PRODUCTION_API_ROUTES },
  };
}

function settingsPath(configPath) {
  return configPath
    ? path.join(path.dirname(configPath), "settings.json")
    : null;
}

export function loadSettings(configPath) {
  if (!configPath)
    return {
      ...DEFAULT_SETTINGS,
      apiRoutes: { ...DEFAULT_SETTINGS.apiRoutes },
    };
  try {
    return validatePersisted(
      JSON.parse(fs.readFileSync(settingsPath(configPath), "utf8"))
    );
  } catch {
    return {
      ...DEFAULT_SETTINGS,
      apiRoutes: { ...DEFAULT_SETTINGS.apiRoutes },
    };
  }
}

export function loadWorkerCoreSettings(configPath) {
  try {
    const payload = JSON.parse(fs.readFileSync(configPath, "utf8"));
    requirePlainObject(payload, "worker config");
    if (
      typeof payload.auto_record_enabled !== "boolean" ||
      typeof payload.input_device !== "string"
    )
      return {};
    const inputDevice = payload.input_device.trim();
    if (inputDevice.length > 256 || /\0|[\r\n]/u.test(inputDevice)) return {};
    const apiRoutes = payload.api_routes
      ? migrateOfficialApiRoutes(payload.api_routes)
      : { ...PRODUCTION_API_ROUTES };
    return {
      autoRecordEnabled: payload.auto_record_enabled,
      inputDevice: inputDevice || "default",
      apiRoutes,
    };
  } catch {
    return {};
  }
}

export function saveSettings(configPath, settings) {
  if (!configPath) throw new Error("worker configuration is not bootstrapped");
  const persisted = validatePersisted(settings);
  atomicWriteJson(settingsPath(configPath), persisted);
  return persisted;
}

export function applyAutoLaunch({ desired, app, platform = process.platform }) {
  validateAutoLaunchValue(desired);
  if (platform !== "win32") {
    return {
      desired,
      actual: null,
      status: "unverified",
      error: "仅支持在 Windows 上验证开机自启状态",
    };
  }
  try {
    app.setLoginItemSettings({
      openAtLogin: desired,
      openAsHidden: true,
      path: process.execPath,
    });
  } catch (error) {
    return {
      desired,
      actual: null,
      status: "failed",
      error: `Windows 开机自启设置失败: ${error.message}`,
    };
  }
  try {
    const actual = app.getLoginItemSettings().openAtLogin === true;
    return {
      desired,
      actual,
      status: actual === desired ? "verified" : "unverified",
      error: null,
    };
  } catch (error) {
    return {
      desired,
      actual: null,
      status: "failed",
      error: `Windows 开机自启状态读取失败: ${error.message}`,
    };
  }
}
