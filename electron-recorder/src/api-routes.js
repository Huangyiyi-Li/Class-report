const ROUTE_PATHS = Object.freeze({
  deviceAuth: "/wisdom/book-reading/device-auth",
  gradeClassList: "/wisdom/group/grade-class-list",
  bindDevice: "/ai-lesson-eval/recording-device/bind-device",
  unbindDevice: "/ai-lesson-eval/recording-device/unbind-device",
  ossToken: "/wisdom/ali-oss/get-ali-oss-token",
  saveAudioFileInfo: "/ai-lesson-eval/audio/save-audio-file-info",
});

export const API_ROUTE_DEFINITIONS = Object.freeze([
  { key: "deviceAuth", label: "设备认证" },
  { key: "gradeClassList", label: "学校、年级和班级目录" },
  { key: "bindDevice", label: "绑定设备" },
  { key: "unbindDevice", label: "解除绑定" },
  { key: "ossToken", label: "获取上传凭证" },
  { key: "saveAudioFileInfo", label: "登记录音文件" },
]);

function createPreset(origin) {
  return Object.freeze(
    Object.fromEntries(
      Object.entries(ROUTE_PATHS).map(([key, route]) => [
        key,
        `${origin}${route}`,
      ])
    )
  );
}

export const TEST_API_ROUTES = createPreset("https://rest-test.xxt.cn");
export const PRODUCTION_API_ROUTES = createPreset("https://rest.xxt.cn");

const LEGACY_OFFICIAL_OSS_ROUTES = new Map([
  [
    "http://rest-test.xxt.cn/wisdom/ali-oss/get-ali-oss-upload-token",
    "http://rest-test.xxt.cn/wisdom/ali-oss/get-ali-oss-token",
  ],
  [
    "https://rest-test.xxt.cn/wisdom/ali-oss/get-ali-oss-upload-token",
    "https://rest-test.xxt.cn/wisdom/ali-oss/get-ali-oss-token",
  ],
  [
    "http://rest.xxt.cn/wisdom/ali-oss/get-ali-oss-upload-token",
    "http://rest.xxt.cn/wisdom/ali-oss/get-ali-oss-token",
  ],
  [
    "https://rest.xxt.cn/wisdom/ali-oss/get-ali-oss-upload-token",
    "https://rest.xxt.cn/wisdom/ali-oss/get-ali-oss-token",
  ],
]);

export function migrateOfficialApiRoutes(value) {
  const routes = validateApiRoutes(value);
  const migratedOssRoute = LEGACY_OFFICIAL_OSS_ROUTES.get(routes.ossToken);
  return migratedOssRoute ? { ...routes, ossToken: migratedOssRoute } : routes;
}

export function validateApiRoutes(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new TypeError("apiRoutes must be an object");
  }
  const allowed = new Set(Object.keys(ROUTE_PATHS));
  const unknown = Object.keys(value).find((key) => !allowed.has(key));
  if (unknown)
    throw new TypeError(`apiRoutes contains forbidden field: ${unknown}`);

  const routes = {};
  for (const key of allowed) {
    const raw = value[key];
    if (typeof raw !== "string" || !raw.trim()) {
      throw new TypeError(`apiRoutes.${key} must not be empty`);
    }
    if (raw.length > 2048 || /[\0\r\n]/u.test(raw)) {
      throw new TypeError(`apiRoutes.${key} is invalid`);
    }
    let url;
    try {
      url = new URL(raw.trim());
    } catch {
      throw new TypeError(`apiRoutes.${key} must be an http/https URL`);
    }
    if (!["http:", "https:"].includes(url.protocol) || !url.hostname) {
      throw new TypeError(`apiRoutes.${key} must be an http/https URL`);
    }
    if (url.username || url.password || url.hash) {
      throw new TypeError(`apiRoutes.${key} contains unsupported URL parts`);
    }
    routes[key] = url.toString().replace(/\/$/, "");
  }
  return routes;
}

export function detectApiEnvironment(routes) {
  const normalized = validateApiRoutes(routes);
  if (sameRoutes(normalized, TEST_API_ROUTES)) return "test";
  if (sameRoutes(normalized, PRODUCTION_API_ROUTES)) return "production";
  return "custom";
}

function sameRoutes(left, right) {
  return Object.keys(ROUTE_PATHS).every((key) => left[key] === right[key]);
}
