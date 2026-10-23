import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import vm from "node:vm";

const main = readFileSync(new URL("./main.js", import.meta.url), "utf8");
const preload = readFileSync(new URL("./preload.cjs", import.meta.url), "utf8");
const renderer = readFileSync(
  new URL("./renderer.jsx", import.meta.url),
  "utf8"
);

function bodyBetween(start, end) {
  return main.slice(
    main.indexOf(start),
    main.indexOf(end, main.indexOf(start))
  );
}

test("hide cancels a pending first show without sending recording commands", () => {
  const calls = [];
  const context = {
    pendingFloatingShow: true,
    floatingDragOffset: { x: 1, y: 2 },
    settings: { floatingHideNoticeSeen: true },
    setFloatingVisibility: (visible) => calls.push(visible),
    floatingBallWindow: { hide: () => calls.push("hide") },
    updateTray: () => calls.push("tray"),
  };
  vm.createContext(context);
  vm.runInContext(
    bodyBetween(
      "function hideFloatingBallWindow()",
      "function persistDesktopSettings()"
    ) + "hideFloatingBallWindow();",
    context
  );
  assert.equal(context.pendingFloatingShow, false);
  assert.deepEqual(calls, [false, "hide", "tray"]);
  assert.equal(context.floatingDragOffset, null);
});

test("closing the main window leaves a hidden float hidden", () => {
  const closeHandler = bodyBetween(
    'mainWindow.on("close",',
    "function createFloatingBallWindow()"
  );
  assert.doesNotMatch(closeHandler, /showFloatingBallWindow\(/);
  const minimizeHandler = bodyBetween(
    'ipcMain.handle("window:minimize-to-tray",',
    'ipcMain.handle("window:show-main",'
  );
  assert.doesNotMatch(minimizeHandler, /showFloatingBallWindow\(/);
});

test("floating UI exposes a close action through the isolated bridge and menu", () => {
  assert.match(renderer, /aria-label="隐藏录音悬浮窗"/);
  assert.match(renderer, /onClick=\{\(\) => shell\?\.hideFloat\?\.\(\)\}/);
  assert.match(preload, /hideFloat:.*window:hide-float/);
  assert.match(main, /ipcMain.handle\("window:hide-float",/);
  assert.match(
    bodyBetween("function showFloatingBallMenu()", "function broadcast("),
    /隐藏悬浮窗/
  );
});

test("thin capsule uses an opaque clipped window on Windows", () => {
  assert.match(main, /const FLOATING_BALL_WIDTH = 88;/);
  assert.match(main, /const FLOATING_BALL_HEIGHT = 24;/);
  assert.match(main, /width: FLOATING_BALL_WIDTH/);
  assert.match(main, /height: FLOATING_BALL_HEIGHT/);
  const options = bodyBetween(
    "function createFloatingBallWindow()",
    "function showFloatingBallWindow("
  );
  assert.match(options, /transparent: process.platform !== "win32"/);
  assert.match(options, /roundedCorners: false/);
  assert.match(options, /thickFrame: false/);
  assert.match(options, /backgroundColor: process.platform === "win32"/);
  assert.match(options, /once\("ready-to-show"/);
  assert.match(
    main,
    /setShape\(createFloatingCapsuleShape|setShape\(\s*createFloatingCapsuleShape/
  );
});

test("startup respects visibility preference and puts configured clients in the tray", () => {
  assert.match(
    main,
    /if \(settings\.floatingWindowVisible\)\s+showFloatingBallWindow\(\{ remember: false \}\)/
  );
  assert.match(
    main,
    /show: !workerLocation \|\| Boolean\(process\.env\.ELECTRON_SMOKE_TEST\)/
  );
});
