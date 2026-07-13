export const SETTINGS_SAVE_UNCONFIRMED = "保存结果未确认，请重新打开设置核对";

export async function saveSettings({ updateSettings, setAutoLaunch, workerSettings, autoLaunch, onClose, onUnconfirmed }) {
  try {
    await updateSettings(workerSettings);
    await setAutoLaunch(autoLaunch);
    onClose();
    return true;
  } catch {
    onUnconfirmed(SETTINGS_SAVE_UNCONFIRMED);
    return false;
  }
}
