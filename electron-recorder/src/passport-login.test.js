import assert from "node:assert/strict";
import { EventEmitter } from "node:events";
import test from "node:test";

import {
  CURRENT_USER_URL,
  PASSPORT_LOGIN_URL,
  createPassportAuthenticator,
  getPassportWindowLayout,
  isPassportConsoleUrl,
} from "./passport-login.js";

class FakeWebContents extends EventEmitter {
  constructor() {
    super();
    this.openHandler = null;
  }

  setWindowOpenHandler(handler) {
    this.openHandler = handler;
  }
}

class FakeWindow extends EventEmitter {
  constructor() {
    super();
    this.webContents = new FakeWebContents();
    this.loadedUrl = "";
    this.destroyed = false;
  }

  loadURL(url) {
    this.loadedUrl = url;
  }

  close() {
    this.destroyed = true;
    this.emit("closed");
  }

  isDestroyed() {
    return this.destroyed;
  }
}

function response(body, { status = 200 } = {}) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  };
}

test("only the authenticated szjx console is a login completion URL", () => {
  assert.equal(
    isPassportConsoleUrl("https://szjx-console.xxt.cn/user-data/home"),
    true
  );
  assert.equal(isPassportConsoleUrl("https://szjx.xxt.cn/"), false);
  assert.equal(
    isPassportConsoleUrl("https://passport.xxt.cn/user-select-pre"),
    false
  );
  assert.equal(
    isPassportConsoleUrl(
      "https://szjx-console.xxt.cn.evil.test/user-data/home"
    ),
    false
  );
});

test("Passport authenticator accepts the live teacher userType and reuses its session", async () => {
  const window = new FakeWindow();
  const requests = [];
  const browserSession = {
    fetch: async (url, options) => {
      requests.push([url, options]);
      if (url === CURRENT_USER_URL) {
        return response({
          schoolId: 9001,
          schoolName: "众享中学",
          userName: "测试教师",
          userType: 0,
          webId: 778899,
        });
      }
      return response({ success: true });
    },
  };
  const authenticate = createPassportAuthenticator({
    createWindow: () => window,
    browserSession,
  });

  const login = authenticate();
  assert.equal(window.loadedUrl, PASSPORT_LOGIN_URL);
  window.webContents.emit("did-navigate", {}, "https://szjx.xxt.cn/");
  assert.equal(requests.length, 0);
  window.webContents.emit(
    "did-redirect-navigation",
    {},
    "https://szjx-console.xxt.cn/user-data/home"
  );
  const authenticated = await login;

  assert.deepEqual(authenticated.user, {
    schoolId: 9001,
    schoolName: "众享中学",
    userName: "测试教师",
    userType: 0,
  });
  assert.equal(window.destroyed, true);
  await authenticated.post(
    "https://rest.xxt.cn/ai-lesson-eval/basic-data/get-grade-list",
    {}
  );
  assert.deepEqual(
    requests.map(([url]) => url),
    [
      CURRENT_USER_URL,
      "https://rest.xxt.cn/ai-lesson-eval/basic-data/get-grade-list",
    ]
  );
  assert.equal(requests[0][1].credentials, "include");
  assert.equal(requests[1][1].credentials, "include");
  assert.equal(requests[1][1].method, "POST");
  assert.equal(requests[1][1].body, "{}");
  assert.equal(requests[1][1].headers.Authorization, "778899");
});

test("Passport API business errors are reported instead of being parsed as an invalid catalog", async () => {
  const window = new FakeWindow();
  const browserSession = {
    fetch: async (url) =>
      url === CURRENT_USER_URL
        ? response({
            schoolId: 9001,
            schoolName: "众享中学",
            userName: "测试教师",
            userType: 0,
            webId: 778899,
          })
        : response({ code: 2, message: "未登录", status: 401 }),
  };
  const authenticate = createPassportAuthenticator({
    createWindow: () => window,
    browserSession,
  });

  const login = authenticate();
  window.webContents.emit(
    "did-navigate",
    {},
    "https://szjx-console.xxt.cn/user-data/home"
  );
  const authenticated = await login;

  await assert.rejects(
    authenticated.post("https://rest.xxt.cn/wisdom/group/grade-class-list", {
      schoolId: 9001,
    }),
    {
      code: "PASSPORT_REQUEST_FAILED",
      message: "登录状态已失效，请重新登录 Passport",
    }
  );
});

test("Passport identity without webId is rejected before protected API calls", async () => {
  const window = new FakeWindow();
  const authenticate = createPassportAuthenticator({
    createWindow: () => window,
    browserSession: {
      fetch: async () =>
        response({
          schoolId: 9001,
          schoolName: "众享中学",
          userName: "测试教师",
          userType: 0,
        }),
    },
  });

  const login = authenticate();
  window.webContents.emit(
    "did-navigate",
    {},
    "https://szjx-console.xxt.cn/user-data/home"
  );

  await assert.rejects(login, {
    code: "PASSPORT_IDENTITY_INVALID",
    message: "webId is invalid",
  });
});

test("Passport window fits a desktop page into the available display area", () => {
  assert.deepEqual(getPassportWindowLayout({ width: 1920, height: 1040 }), {
    width: 1440,
    height: 900,
    zoomFactor: 1,
  });

  const compact = getPassportWindowLayout({ width: 1366, height: 728 });
  assert.deepEqual(
    { width: compact.width, height: compact.height },
    { width: 1318, height: 680 }
  );
  assert.ok(compact.zoomFactor >= 0.75 && compact.zoomFactor <= 0.76);
});

test("closing the Passport window before console login rejects the session", async () => {
  const window = new FakeWindow();
  const authenticate = createPassportAuthenticator({
    createWindow: () => window,
    browserSession: { fetch: async () => response({}) },
  });

  const login = authenticate();
  window.close();

  await assert.rejects(login, { code: "PASSPORT_LOGIN_CANCELLED" });
});
