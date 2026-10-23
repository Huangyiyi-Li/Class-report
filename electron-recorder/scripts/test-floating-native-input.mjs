import { app, BrowserWindow, screen } from "electron";
import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { mkdtempSync, rmSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

if (
  process.platform !== "win32" &&
  process.env.RECORDER_FLOATING_NATIVE_READY_ONLY !== "1"
) {
  console.log("Windows native pointer regression requires Windows.");
  app.exit(0);
} else {
  if (process.env.RECORDER_NATIVE_SCALE_FACTOR)
    app.commandLine.appendSwitch(
      "force-device-scale-factor",
      process.env.RECORDER_NATIVE_SCALE_FACTOR
    );
  const scriptDir = path.dirname(fileURLToPath(import.meta.url));
  const fixture = mkdtempSync(
    path.join(app.getPath("temp"), "recorder-native-input-")
  );
  app.setPath("userData", fixture);
  process.env.ELECTRON_SMOKE_TEST = "1";
  process.env.BINDING_SERVICE_MODE = "mock";
  process.env.RECORDER_FLOATING_NATIVE_TEST = "1";
  const execute = promisify(execFile);
  const waitFor = async (check, timeout = 5000) => {
    const deadline = Date.now() + timeout;
    while (Date.now() < deadline) {
      const result = await check();
      if (result) return result;
      await new Promise((resolve) => setTimeout(resolve, 50));
    }
    return null;
  };
  const inject = async (points) => {
    const physical = points.map(({ x, y, button }) => ({
      ...screen.dipToScreenPoint({ x, y }),
      button,
    }));
    const { stdout } = await execute(
      "pwsh",
      [
        "-NoProfile",
        "-NonInteractive",
        "-File",
        path.join(scriptDir, "test-floating-native-input.ps1"),
        "-PointsJson",
        JSON.stringify(physical),
      ],
      { windowsHide: true, timeout: 15000 }
    );
    return JSON.parse(stdout);
  };
  const deadline = setTimeout(() => app.exit(1), 45000);
  const run = async () => {
    try {
      console.log("[floating-native-stage] importing application");
      await import("../src/main.js");
      await app.whenReady();
      console.log("[floating-native-stage] application ready");
      const floating = await waitFor(() =>
        BrowserWindow.getAllWindows().find(
          (win) =>
            win.webContents.getURL().includes("floating-ball") &&
            !win.webContents.isLoading()
        )
      );
      if (!floating) throw new Error("floating window did not load");
      console.log("[floating-native-stage] floating renderer ready");
      if (process.env.RECORDER_FLOATING_NATIVE_READY_ONLY === "1") {
        clearTimeout(deadline);
        console.log("[floating-native-ready] passed");
        app.exit(0);
        return;
      }
      await waitFor(() =>
        floating.webContents.executeJavaScript(
          "Boolean(document.querySelector('.floating-close') && window.recorderShell)"
        )
      );
      await floating.webContents.executeJavaScript(
        `window.__pointerEvents=[]; for(const kind of ['pointerdown','pointerup','click','pointercancel']) document.addEventListener(kind,event=>window.__pointerEvents.push({kind,target:event.target.closest('button, .floating-status-bubble')?.className,x:event.screenX,y:event.screenY}),true); window.recorderShell.showFloat();`
      );
      await waitFor(() => floating.isVisible());
      floating.setPosition(220, 220);
      const beforeClose = floating.getBounds();
      const clickPoint = { x: beforeClose.x + 74, y: beforeClose.y + 12 };
      const nativeClose = await inject([
        { ...clickPoint, button: "down" },
        { ...clickPoint, button: "up" },
      ]);
      const closeHidden = Boolean(
        await waitFor(() => !floating.isVisible(), 1500)
      );
      const closeEvents = await floating.webContents.executeJavaScript(
        "window.__pointerEvents"
      );
      await floating.webContents.executeJavaScript(
        "window.__pointerEvents=[]; window.recorderShell.showFloat()"
      );
      await waitFor(() => floating.isVisible());
      floating.setPosition(220, 220);
      const beforeDrag = floating.getBounds();
      const start = { x: beforeDrag.x + 24, y: beforeDrag.y + 12 };
      const pathPoints = [{ ...start, button: "down" }];
      for (let step = 1; step <= 6; step++)
        pathPoints.push({ x: start.x + step * 15, y: start.y + step * 10 });
      pathPoints.push({ x: start.x + 90, y: start.y + 60, button: "up" });
      const nativeDrag = await inject(pathPoints);
      await waitFor(() => {
        const bounds = floating.getBounds();
        return bounds.x !== beforeDrag.x || bounds.y !== beforeDrag.y;
      }, 1500);
      const afterDrag = floating.getBounds();
      const dragEvents = await floating.webContents.executeJavaScript(
        "window.__pointerEvents"
      );
      const finalClosePoint = { x: afterDrag.x + 74, y: afterDrag.y + 12 };
      const nativeCloseAfterDrag = await inject([
        { ...finalClosePoint, button: "down" },
        { ...finalClosePoint, button: "up" },
      ]);
      const closeAfterDragHidden = Boolean(
        await waitFor(() => !floating.isVisible(), 1500)
      );
      if (!closeAfterDragHidden)
        await floating.webContents.executeJavaScript(
          "window.recorderShell.hideFloat()"
        );
      await floating.webContents.executeJavaScript(
        "window.recorderShell.showFloat()"
      );
      await waitFor(() => floating.isVisible());
      const afterReopen = floating.getBounds();
      const reopenCycles = [];
      for (let cycle = 0; cycle < 3; cycle++) {
        await inject([
          { x: afterDrag.x + 74, y: afterDrag.y + 12, button: "down" },
          { x: afterDrag.x + 74, y: afterDrag.y + 12, button: "up" },
        ]);
        const hidden = Boolean(
          await waitFor(() => !floating.isVisible(), 1500)
        );
        await floating.webContents.executeJavaScript(
          "window.recorderShell.showFloat()"
        );
        await waitFor(() => floating.isVisible());
        reopenCycles.push({ hidden, bounds: floating.getBounds() });
      }
      const result = {
        closeHidden,
        closeAfterDragHidden,
        dragged: afterDrag.x !== beforeDrag.x || afterDrag.y !== beforeDrag.y,
        positionRestored:
          afterReopen.x === afterDrag.x &&
          afterReopen.y === afterDrag.y &&
          reopenCycles.every(
            ({ hidden, bounds }) =>
              hidden && bounds.x === afterDrag.x && bounds.y === afterDrag.y
          ),
        sizeStable:
          afterDrag.width <= 89 &&
          reopenCycles.every(({ bounds }) => bounds.width <= 89),
        reopenCycles,
        windowHandle: floating
          .getNativeWindowHandle()
          .readBigUInt64LE()
          .toString(),
        focusable: floating.isFocusable(),
        scaleFactor: screen.getDisplayMatching(beforeClose).scaleFactor,
        beforeClose,
        beforeDrag,
        afterDrag,
        afterReopen,
        closeEvents,
        dragEvents,
        nativeClose,
        nativeDrag,
        nativeCloseAfterDrag,
      };
      console.log("[floating-native-input]", JSON.stringify(result));
      clearTimeout(deadline);
      app.isQuitting = true;
      app.exit(
        result.closeHidden &&
          result.closeAfterDragHidden &&
          result.dragged &&
          result.sizeStable &&
          result.positionRestored
          ? 0
          : 1
      );
    } catch (error) {
      console.error(error);
      clearTimeout(deadline);
      app.exit(1);
    } finally {
      try {
        rmSync(fixture, { recursive: true, force: true });
      } catch {}
    }
  };
  void run();
}
