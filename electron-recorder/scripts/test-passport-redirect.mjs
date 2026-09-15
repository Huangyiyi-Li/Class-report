import assert from "node:assert/strict";
import { app, BrowserWindow, session } from "electron";
import { createPassportAuthenticator } from "../src/passport-login.js";

// A real Chromium 301 navigation, with synthetic identity and no account login.
const deadline = setTimeout(() => app.exit(1), 15000);
app.whenReady().then(async () => {
  try {
    const browserSession = session.fromPartition(
      "passport-redirect-regression"
    );
    await browserSession.protocol.handle("https", (request) => {
      if (new URL(request.url).hostname === "szjx.xxt.cn") {
        return Response.redirect("https://szjx.xinzx.cn/", 301);
      }
      return new Response("<title>Homepage fixture</title>", {
        headers: { "Content-Type": "text/html" },
      });
    });
    let window;
    let reads = 0;
    let closed;
    let loadError;
    const authenticate = createPassportAuthenticator({
      loginUrl: "https://szjx.xxt.cn/",
      createWindow: () => {
        window = new BrowserWindow({
          show: false,
          webPreferences: {
            session: browserSession,
            contextIsolation: true,
            nodeIntegration: false,
            sandbox: true,
          },
        });
        closed = new Promise((resolve) => window.once("closed", resolve));
        // Closing after authentication can abort loadURL; consume that expected result.
        const loadURL = window.loadURL.bind(window);
        window.loadURL = (...args) =>
          loadURL(...args).catch((error) => {
            loadError = error;
          });
        return window;
      },
      browserSession: {
        fetch: async () => {
          reads += 1;
          return Response.json({
            schoolId: 9001,
            schoolName: "Fixture school",
            userName: "Fixture teacher",
            userType: 0,
          });
        },
      },
    });
    const result = await authenticate();
    assert.equal(result.user.schoolId, 9001);
    assert.equal(reads, 1);
    await closed;
    assert.equal(window.isDestroyed(), true);
    if (loadError)
      assert.ok(["ERR_FAILED", "ERR_ABORTED"].includes(loadError.code));
    console.log(
      "PASS: real Electron 301 to xinzx triggers identity and closes Passport"
    );
    app.exit(0);
  } catch (error) {
    console.error(error);
    app.exit(1);
  } finally {
    clearTimeout(deadline);
  }
});
