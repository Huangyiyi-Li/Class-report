export const PASSPORT_LOGIN_URL =
  "https://passport.xxt.cn/login?app=szjx&url=https%3A%2F%2Fszjx.xxt.cn%2F";
export const CURRENT_USER_URL =
  "https://szjx-console.xxt.cn/api/user-data-v2/user/get-user-info-by-login";

const PASSPORT_TARGET_WIDTH = 1440;
const PASSPORT_TARGET_HEIGHT = 900;
const PASSPORT_WINDOW_MARGIN = 48;
const PASSPORT_MIN_ZOOM = 0.67;

export function getPassportWindowLayout(workAreaSize = {}) {
  const workAreaWidth = positiveDimension(
    workAreaSize.width,
    PASSPORT_TARGET_WIDTH + PASSPORT_WINDOW_MARGIN
  );
  const workAreaHeight = positiveDimension(
    workAreaSize.height,
    PASSPORT_TARGET_HEIGHT + PASSPORT_WINDOW_MARGIN
  );
  const width = Math.min(
    PASSPORT_TARGET_WIDTH,
    Math.max(1, workAreaWidth - PASSPORT_WINDOW_MARGIN)
  );
  const height = Math.min(
    PASSPORT_TARGET_HEIGHT,
    Math.max(1, workAreaHeight - PASSPORT_WINDOW_MARGIN)
  );
  const zoomFactor = Number(
    Math.max(
      PASSPORT_MIN_ZOOM,
      Math.min(
        1,
        width / PASSPORT_TARGET_WIDTH,
        height / PASSPORT_TARGET_HEIGHT
      )
    ).toFixed(2)
  );
  return { width, height, zoomFactor };
}

export function isPassportConsoleUrl(value) {
  try {
    const url = new URL(value);
    return (
      url.protocol === "https:" &&
      (url.hostname === "szjx.xxt.cn" || url.hostname === "szjx-console.xxt.cn")
    );
  } catch {
    return false;
  }
}

export function createPassportAuthenticator({
  createWindow,
  browserSession,
  loginUrl = PASSPORT_LOGIN_URL,
  currentUserUrl = CURRENT_USER_URL,
} = {}) {
  if (
    typeof createWindow !== "function" ||
    typeof browserSession?.fetch !== "function"
  ) {
    throw passportError("PASSPORT_NOT_CONFIGURED", "Passport 登录窗口尚未配置");
  }

  const authenticate = () =>
    new Promise((resolve, reject) => {
      const window = createWindow();
      let completed = false;
      let resolving = false;

      const finish = (callback, value) => {
        if (completed) return;
        completed = true;
        callback(value);
        if (!window.isDestroyed?.()) window.close();
      };

      const handleNavigation = async (_event, url) => {
        if (!isPassportConsoleUrl(url) || resolving || completed) return;
        resolving = true;
        try {
          const user = await loadCurrentUser(browserSession, currentUserUrl);
          finish(resolve, {
            user,
            post: (requestUrl, payload) =>
              postJson(browserSession, requestUrl, payload),
          });
        } catch (error) {
          resolving = false;
          finish(reject, error);
        }
      };

      window.webContents.setWindowOpenHandler?.(() => ({ action: "deny" }));
      window.webContents.on("did-navigate", handleNavigation);
      window.webContents.on("did-redirect-navigation", handleNavigation);
      window.on("closed", () => {
        if (!completed) {
          completed = true;
          reject(passportError("PASSPORT_LOGIN_CANCELLED", "登录窗口已关闭"));
        }
      });
      window.loadURL(loginUrl);
    });
  authenticate.reset = () => resetPassportSession(browserSession);
  return authenticate;
}

export async function resetPassportSession(browserSession) {
  if (typeof browserSession?.clearStorageData === "function") {
    await browserSession.clearStorageData({
      storages: ["cookies", "localstorage", "sessionstorage"],
    });
  }
  if (typeof browserSession?.clearAuthCache === "function") {
    await browserSession.clearAuthCache();
  }
}

async function loadCurrentUser(browserSession, url) {
  const response = await browserSession.fetch(url, {
    method: "GET",
    credentials: "include",
    headers: { Accept: "application/json" },
  });
  const payload = await responseJson(response, "读取当前登录用户失败");
  const user =
    payload?.data && typeof payload.data === "object" ? payload.data : payload;
  return {
    schoolId: positiveInteger(user?.schoolId, "schoolId"),
    schoolName: nonEmptyString(user?.schoolName, "schoolName"),
    userName: nonEmptyString(user?.userName, "userName"),
    userType: nonNegativeInteger(user?.userType, "userType"),
  };
}

async function postJson(browserSession, url, payload) {
  const response = await browserSession.fetch(url, {
    method: "POST",
    credentials: "include",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload ?? {}),
  });
  return responseJson(response, "服务端请求失败");
}

async function responseJson(response, fallback) {
  if (!response?.ok) {
    throw passportError(
      "PASSPORT_REQUEST_FAILED",
      `${fallback}${response?.status ? `（HTTP ${response.status}）` : ""}`
    );
  }
  const payload = await response.json();
  const businessStatus = Number(payload?.status);
  if (Number.isFinite(businessStatus) && businessStatus >= 400) {
    const message =
      typeof payload?.message === "string" ? payload.message.trim() : "";
    throw passportError(
      "PASSPORT_REQUEST_FAILED",
      businessStatus === 401 || message.includes("未登录")
        ? "登录状态已失效，请重新登录 Passport"
        : message || `${fallback}（服务端状态 ${businessStatus}）`
    );
  }
  return payload;
}

function positiveInteger(value, field) {
  const normalized =
    typeof value === "string" && /^\d+$/.test(value.trim())
      ? Number(value)
      : value;
  if (!Number.isInteger(normalized) || normalized <= 0) {
    throw passportError("PASSPORT_IDENTITY_INVALID", `${field} is invalid`);
  }
  return normalized;
}

function nonNegativeInteger(value, field) {
  const normalized =
    typeof value === "string" && /^\d+$/.test(value.trim())
      ? Number(value)
      : value;
  if (!Number.isInteger(normalized) || normalized < 0) {
    throw passportError("PASSPORT_IDENTITY_INVALID", `${field} is invalid`);
  }
  return normalized;
}

function positiveDimension(value, fallback) {
  return Number.isFinite(value) && value > 0 ? Math.floor(value) : fallback;
}

function nonEmptyString(value, field) {
  const normalized = typeof value === "string" ? value.trim() : "";
  if (!normalized) {
    throw passportError("PASSPORT_IDENTITY_INVALID", `${field} is invalid`);
  }
  return normalized;
}

function passportError(code, message) {
  const error = new Error(message);
  error.code = code;
  return error;
}
