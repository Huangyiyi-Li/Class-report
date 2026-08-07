function errorMessage(error, fallback) {
  const message =
    typeof error?.message === "string" ? error.message.trim() : "";
  return message || fallback;
}

export function canInstallWorkerUpdate(snapshot = {}) {
  return !["starting", "recording"].includes(snapshot.recording);
}

export function createUpdateController({
  updater,
  currentVersion,
  supported,
  publish = () => {},
  canInstall = () => true,
  prepareInstall = async () => {},
} = {}) {
  let state = {
    status: supported ? "idle" : "unsupported",
    currentVersion,
    availableVersion: "",
    percent: 0,
    error: "",
  };

  const updateState = (patch) => {
    state = { ...state, ...patch };
    publish({ ...state });
    return { ...state };
  };

  if (supported && updater) {
    updater.autoDownload = false;
    updater.autoInstallOnAppQuit = false;
    updater.allowPrerelease = true;
    updater.channel = "codex";

    updater.on("checking-for-update", () =>
      updateState({ status: "checking", error: "" })
    );
    updater.on("update-not-available", () =>
      updateState({
        status: "current",
        availableVersion: "",
        percent: 0,
        error: "",
      })
    );
    updater.on("update-available", (info) => {
      updateState({
        status: "downloading",
        availableVersion: info?.version || "",
        percent: 0,
        error: "",
      });
      Promise.resolve(updater.downloadUpdate()).catch((error) =>
        updateState({
          status: "error",
          error: errorMessage(error, "更新下载失败，请稍后重试"),
        })
      );
    });
    updater.on("download-progress", (progress) =>
      updateState({
        status: "downloading",
        percent: Math.max(
          0,
          Math.min(100, Math.round(Number(progress?.percent) || 0))
        ),
      })
    );
    updater.on("update-downloaded", (info) =>
      updateState({
        status: "ready",
        availableVersion: info?.version || state.availableVersion,
        percent: 100,
        error: "",
      })
    );
    updater.on("error", (error) =>
      updateState({
        status: "error",
        error: errorMessage(error, "检查更新失败，请稍后重试"),
      })
    );
  }

  return {
    getState() {
      return { ...state };
    },

    async check() {
      if (!supported || !updater) {
        return updateState({
          status: "unsupported",
          error: "便携版或开发版本不支持应用内更新",
        });
      }
      updateState({ status: "checking", error: "" });
      try {
        await updater.checkForUpdates();
      } catch (error) {
        updateState({
          status: "error",
          error: errorMessage(error, "检查更新失败，请稍后重试"),
        });
        throw error;
      }
      return { ...state };
    },

    async install() {
      if (state.status !== "ready") {
        throw new Error("更新尚未下载完成");
      }
      if (!canInstall()) {
        throw new Error("录音中不能安装更新，请先暂停录音");
      }
      updateState({ status: "installing", error: "" });
      try {
        await prepareInstall();
        updater.quitAndInstall(false, true);
      } catch (error) {
        updateState({
          status: "ready",
          error: errorMessage(error, "录音服务未能安全退出，请稍后重试"),
        });
        throw error;
      }
      return { ...state };
    },
  };
}
