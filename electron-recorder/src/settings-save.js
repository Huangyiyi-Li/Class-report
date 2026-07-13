export const SETTINGS_SAVE_UNCONFIRMED = "保存结果未确认，请重新打开设置核对";
export const AUTO_LAUNCH_UNVERIFIED = "开机自启状态未验证，请重试";

export async function saveSettings({ updateSettings, setAutoLaunch, workerSettings, autoLaunch, onClose, onUnconfirmed }) {
  try {
    await updateSettings(workerSettings);
    const result = await setAutoLaunch(autoLaunch);
    if (result?.status !== "verified") {
      onUnconfirmed(result?.error || AUTO_LAUNCH_UNVERIFIED);
      return false;
    }
    onClose();
    return true;
  } catch {
    onUnconfirmed(SETTINGS_SAVE_UNCONFIRMED);
    return false;
  }
}
