import assert from "node:assert/strict";
import test from "node:test";
import {
  SETTINGS_SAVE_UNCONFIRMED,
  buildWorkerSettingsPatch,
  saveSettings,
  setAutoLaunchAfterBootstrap,
} from "./settings-save.js";
import { PRODUCTION_API_ROUTES } from "./api-routes.js";

test("locked recording directory is omitted from ordinary settings updates", () => {
  assert.deepEqual(
    buildWorkerSettingsPatch(
      {
        autoLaunch: false,
        autoRecordEnabled: true,
        inputDevice: "default",
        dataRoot: "D:/RecorderData",
        apiRoutes: PRODUCTION_API_ROUTES,
      },
      { dataRootLocked: true }
    ),
    {
      autoRecordEnabled: true,
      inputDevice: "default",
      apiRoutes: PRODUCTION_API_ROUTES,
    }
  );
});

test("first deployment keeps the selected recording directory in settings update", () => {
  assert.equal(
    buildWorkerSettingsPatch(
      {
        autoLaunch: false,
        autoRecordEnabled: true,
        inputDevice: "default",
        dataRoot: "D:/RecorderData",
        apiRoutes: PRODUCTION_API_ROUTES,
      },
      { dataRootLocked: false }
    ).dataRoot,
    "D:/RecorderData"
  );
});

test("auto-launch before bootstrap fails without mutation or registration", () => {
  let applied = 0;
  const result = setAutoLaunchAfterBootstrap({
    workerLocation: null,
    desired: true,
    apply: () => {
      applied += 1;
    },
  });
  assert.equal(result.status, "failed");
  assert.match(result.error, /请先配置非系统盘数据目录/);
  assert.equal(applied, 0);
});

test("failed settings save keeps modal open and shows a concrete reason", async () => {
  let closed = 0;
  let warning = "";
  const saved = await saveSettings({
    updateSettings: async () => {
      throw new Error("录音服务未连接，请稍后重试");
    },
    setAutoLaunch: async () => {},
    workerSettings: {},
    autoLaunch: true,
    onClose: () => {
      closed += 1;
    },
    onUnconfirmed: (message) => {
      warning = message;
    },
  });
  assert.equal(saved, false);
  assert.equal(closed, 0);
  assert.equal(warning, "设置未保存：录音服务未连接，请稍后重试");
});

test("successful settings save closes modal", async () => {
  let closed = 0;
  const saved = await saveSettings({
    updateSettings: async () => {},
    setAutoLaunch: async () => ({
      status: "verified",
      desired: true,
      actual: true,
      error: null,
    }),
    workerSettings: {},
    autoLaunch: true,
    onClose: () => {
      closed += 1;
    },
    onUnconfirmed: () => {},
  });
  assert.equal(saved, true);
  assert.equal(closed, 1);
});

test("auto-launch IPC failure does not claim the already saved runtime settings were lost", async () => {
  let warning = "";
  const saved = await saveSettings({
    updateSettings: async () => {},
    setAutoLaunch: async () => {
      throw new Error("Windows 拒绝访问启动项");
    },
    workerSettings: {},
    autoLaunch: true,
    onClose: () => {},
    onUnconfirmed: (message) => {
      warning = message;
    },
  });
  assert.equal(saved, false);
  assert.equal(
    warning,
    "运行设置已保存，但开机自启设置失败：Windows 拒绝访问启动项"
  );
});

for (const result of [
  { status: "failed", error: "Windows 开机自启设置失败：注册表被拒绝" },
  { status: "unverified", error: "仅支持在 Windows 上验证开机自启状态" },
  { status: "unverified", error: null },
]) {
  test(`auto-launch ${result.status} keeps modal open and reports a concrete reason`, async () => {
    let closed = 0;
    let warning = "";
    const saved = await saveSettings({
      updateSettings: async () => {},
      setAutoLaunch: async () => result,
      workerSettings: {},
      autoLaunch: true,
      onClose: () => {
        closed += 1;
      },
      onUnconfirmed: (message) => {
        warning = message;
      },
    });
    assert.equal(saved, false);
    assert.equal(closed, 0);
    assert.equal(
      warning,
      `运行设置已保存，但${result.error || "开机自启状态未验证，请重试"}`
    );
  });
}
