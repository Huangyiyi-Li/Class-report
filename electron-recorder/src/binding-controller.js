function controllerError(code, message) {
  const error = new Error(message);
  error.code = code;
  return error;
}

export class BindingController {
  constructor({ service, resolveDeviceNo, getSnapshot, sendWorkerCommand }) {
    this.service = service;
    this.resolveDeviceNo = resolveDeviceNo;
    this.getSnapshot = getSnapshot;
    this.sendWorkerCommand = sendWorkerCommand;
  }

  async createSession({ replaceDevice = false } = {}) {
    const snapshot = this.getSnapshot() || {};
    const persistedDeviceNo =
      [snapshot.binding?.deviceNo, snapshot.deviceNo]
        .map(normalizeMacDeviceNo)
        .find(Boolean) || "";
    const resolvedDeviceNo = normalizeMacDeviceNo(this.resolveDeviceNo());
    const deviceNo = replaceDevice
      ? resolvedDeviceNo
      : persistedDeviceNo || resolvedDeviceNo;
    if (!deviceNo) {
      throw controllerError(
        "DEVICE_IDENTITY_UNAVAILABLE",
        "未找到可用的物理网卡设备标识"
      );
    }
    return this.service.createSession({ deviceNo, scopeDeviceNo: true });
  }

  createReplacementSession() {
    return this.createSession({ replaceDevice: true });
  }

  getSession(sessionId) {
    return this.service.getSession(sessionId);
  }

  resetAuthentication() {
    return this.service.resetAuthentication();
  }

  listGrades(sessionId) {
    return this.service.listGrades(sessionId);
  }

  listClasses(sessionId, query) {
    return this.service.listClasses(sessionId, query);
  }

  async confirmBinding(sessionId, selection) {
    const snapshot = this.getSnapshot() || {};
    const recording =
      snapshot.recordingState ||
      snapshot.recording ||
      snapshot.runtime?.recording ||
      "idle";
    const isRebinding = Boolean(snapshot.binding);
    if (
      ["starting", "recording"].includes(recording) ||
      (isRebinding && recording !== "idle")
    ) {
      throw controllerError(
        "BINDING_REQUIRES_IDLE",
        "请先停止录音，再重新绑定位置"
      );
    }

    const binding = await this.service.confirmBinding(sessionId, selection);
    await this.sendWorkerCommand("apply_binding", binding);
    return binding;
  }

  async replaceBinding(sessionId, selection) {
    this.#requireBindingChangeAllowed();
    try {
      const binding = await this.service.replaceBinding(sessionId, selection);
      await this.sendWorkerCommand("apply_binding", binding);
      return binding;
    } catch (error) {
      if (error?.unbound) {
        await this.sendWorkerCommand("clear_binding", {});
      }
      throw error;
    }
  }

  async unbindDevice() {
    const snapshot = this.getSnapshot() || {};
    if (!snapshot.binding) {
      throw controllerError("BINDING_NOT_FOUND", "设备当前未绑定");
    }
    const recording =
      snapshot.recordingState ||
      snapshot.recording ||
      snapshot.runtime?.recording ||
      "idle";
    if (recording === "starting") {
      throw controllerError(
        "BINDING_REQUIRES_IDLE",
        "录音正在启动，请稍后再变更设备绑定"
      );
    }
    const session = await this.service.createSession({
      deviceNo: snapshot.binding.deviceNo,
      scopeDeviceNo: false,
    });
    if (recording !== "idle") {
      await this.sendWorkerCommand("stop", {});
    }
    await this.sendWorkerCommand("prepare_unbind", {});
    await this.service.unbindDevice(session.id);
    await this.sendWorkerCommand("clear_binding", {});
    return { success: true };
  }

  #requireBindingChangeAllowed() {
    const snapshot = this.getSnapshot() || {};
    const recording =
      snapshot.recordingState ||
      snapshot.recording ||
      snapshot.runtime?.recording ||
      "idle";
    if (["starting", "recording"].includes(recording)) {
      throw controllerError(
        "BINDING_REQUIRES_IDLE",
        "请先停止录音，再更换设备绑定"
      );
    }
  }
}

function normalizeMacDeviceNo(value) {
  const text = typeof value === "string" ? value.trim().toUpperCase() : "";
  const scoped = text.match(/^([0-9A-F]{12})-\d+$/);
  if (scoped) return /^0{12}$/.test(scoped[1]) ? "" : scoped[1];
  if (!/^[0-9A-F]{2}(?:[:-]?[0-9A-F]{2}){5}$/.test(text)) return "";
  const normalized = text.replace(/[:-]/g, "");
  return /^0{12}$/.test(normalized) ? "" : normalized;
}
