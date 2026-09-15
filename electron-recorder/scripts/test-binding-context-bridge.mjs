import assert from "node:assert/strict";
import { app, BrowserWindow, ipcMain } from "electron";
import { fileURLToPath } from "node:url";
import { createRequire } from "node:module";
import { bindingErrorView } from "../src/binding-error-view.js";
import { createBindingFailureTracker } from "../src/diagnostics.js";

const require = createRequire(import.meta.url);
const { captureResult } = require("../src/ipc-result.cjs");
const tracker = createBindingFailureTracker();
let source;
ipcMain.handle("binding:create-session", () =>
  captureResult(() => {
    tracker.capture("create_session", source);
    throw source;
  })
);

const deadline = setTimeout(() => app.exit(1), 20000);
app.whenReady().then(async () => {
  try {
    const window = new BrowserWindow({
      show: false,
      webPreferences: {
        preload: fileURLToPath(new URL("../src/preload.cjs", import.meta.url)),
        contextIsolation: true,
        nodeIntegration: false,
        sandbox: true,
      },
    });
    await window.loadURL(
      "data:text/html,<title>Binding bridge regression</title>"
    );
    for (const fields of [
      { code: "PASSPORT_LOGIN_CANCELLED", message: "登录窗口已关闭" },
      {
        code: "BINDING_REJECTED",
        message: "设备已绑定",
        businessCode: 7,
        operation: "bind",
        unbound: true,
      },
      {
        code: "BINDING_REJECTED",
        message: "无权解绑",
        businessCode: 3,
        operation: "unbind",
      },
    ]) {
      source = Object.assign(new Error(fields.message), fields);
      const received = await window.webContents.executeJavaScript(`
      window.recorderShell.createBindingSession().then(
        () => ({ unexpectedSuccess: true }),
        error => ({ code: error.code, message: error.message,
          businessCode: error.businessCode, operation: error.operation, unbound: error.unbound })
      )
    `);
      assert.equal(
        bindingErrorView(received).problemCode,
        tracker.latest().problemCode
      );
      for (const [key, value] of Object.entries(fields))
        assert.equal(received[key], value);
    }
    console.log(
      "PASS: real sandboxed contextBridge preserves binding errors and diagnostic codes"
    );
    app.exit(0);
  } catch (error) {
    console.error(error);
    app.exit(1);
  } finally {
    clearTimeout(deadline);
  }
});
