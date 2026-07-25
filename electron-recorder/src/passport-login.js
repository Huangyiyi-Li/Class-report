export const PASSPORT_LOGIN_URL =
  "https://passport.xxt.cn/login?app=szjx&url=https%3A%2F%2Fszjx.xxt.cn%2F";
export const CURRENT_USER_URL =
  "https://szjx-console.xxt.cn/api/user-data-v2/user/get-user-info-by-login";

export function isPassportConsoleUrl(value) {
  try {
    const url = new URL(value);
    return url.protocol === "https:" && url.hostname === "szjx-console.xxt.cn";
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
  if (typeof createWindow !== "function" || typeof browserSession?.fetch !== "function") {
    throw passportError("PASSPORT_NOT_CONFIGURED", "Passport 登录窗口尚未配置");
  }

  return () => new Promise((resolve, reject) => {
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
          post: (requestUrl, payload) => postJson(browserSession, requestUrl, payload),
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
}

async function loadCurrentUser(browserSession, url) {
  const response = await browserSession.fetch(url, {
    method: "GET",
    credentials: "include",
    headers: { Accept: "application/json" },
  });
  const payload = await responseJson(response, "读取当前登录用户失败");
  const user = payload?.data && typeof payload.data === "object" ? payload.data : payload;
  return {
    schoolId: positiveInteger(user?.schoolId, "schoolId"),
    schoolName: nonEmptyString(user?.schoolName, "schoolName"),
    userName: nonEmptyString(user?.userName, "userName"),
    userType: positiveInteger(user?.userType, "userType"),
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
      `${fallback}${response?.status ? `（HTTP ${response.status}）` : ""}`,
    );
  }
  return response.json();
}

function positiveInteger(value, field) {
  const normalized = typeof value === "string" && /^\d+$/.test(value.trim())
    ? Number(value)
    : value;
  if (!Number.isInteger(normalized) || normalized <= 0) {
    throw passportError("PASSPORT_IDENTITY_INVALID", `${field} is invalid`);
  }
  return normalized;
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
