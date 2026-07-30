export const SETTINGS_SAVE_UNCONFIRMED = "设置保存失败，请稍后重试";
export const AUTO_LAUNCH_UNVERIFIED = "开机自启状态未验证，请重试";

export function setAutoLaunchAfterBootstrap({
  workerLocation,
  desired,
  apply,
}) {
  if (!workerLocation?.configPath) {
    return {
      desired,
      actual: null,
      status: "failed",
      error: "请先配置非系统盘数据目录",
    };
  }
  return apply(desired);
}

export async function saveSettings({
  updateSettings,
  setAutoLaunch,
  workerSettings,
  autoLaunch,
  onClose,
  onUnconfirmed,
}) {
  try {
    await updateSettings(workerSettings);
  } catch (error) {
    const detail =
      typeof error?.message === "string" ? error.message.trim() : "";
    onUnconfirmed(detail ? `设置未保存：${detail}` : SETTINGS_SAVE_UNCONFIRMED);
    return false;
  }

  try {
    const result = await setAutoLaunch(autoLaunch);
    if (result?.status !== "verified") {
      onUnconfirmed(
        `运行设置已保存，但${result?.error || AUTO_LAUNCH_UNVERIFIED}`
      );
      return false;
    }
    onClose();
    return true;
  } catch (error) {
    const detail =
      typeof error?.message === "string" ? error.message.trim() : "";
    onUnconfirmed(
      `运行设置已保存，但开机自启设置失败：${detail || "请稍后重试"}`
    );
    return false;
  }
}
