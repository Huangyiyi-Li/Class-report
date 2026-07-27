function controllerError(code, message) {
  const error = new Error(message);
  error.code = code;
  return error;
}

export class BindingController {
  constructor({
    service,
    resolveDeviceNo,
    getSnapshot,
    sendWorkerCommand,
    resetAuthentication = async () => {},
  }) {
    this.service = service;
    this.resolveDeviceNo = resolveDeviceNo;
    this.getSnapshot = getSnapshot;
    this.sendWorkerCommand = sendWorkerCommand;
    this.resetAuthentication = resetAuthentication;
  }

  async createSession({ replaceDevice = false } = {}) {
    const snapshot = this.getSnapshot() || {};
    const persistedDeviceNo =
      typeof snapshot.binding?.deviceNo === "string"
        ? snapshot.binding.deviceNo.trim()
        : "";
    const resolvedDeviceNo = this.resolveDeviceNo();
    const deviceNo = replaceDevice
      ? resolvedDeviceNo
      : persistedDeviceNo || resolvedDeviceNo;
    if (!deviceNo) {
      throw controllerError(
        "DEVICE_IDENTITY_UNAVAILABLE",
        "未找到可用的物理网卡设备标识"
      );
    }
    return this.service.createSession({ deviceNo });
  }

  createReplacementSession() {
    return this.createSession({ replaceDevice: true });
  }

  async restartSession(sessionId, { replaceDevice = false } = {}) {
    await this.service.cancelSession(sessionId);
    await this.resetAuthentication();
    return this.createSession({ replaceDevice });
  }

  getSession(sessionId) {
    return this.service.getSession(sessionId);
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

  async unbindDevice() {
    const snapshot = this.getSnapshot() || {};
    if (!snapshot.binding) {
      throw controllerError("BINDING_NOT_FOUND", "设备当前未绑定");
    }
    this.#requireIdle(snapshot);
    await this.sendWorkerCommand("prepare_unbind", {});
    const session = await this.service.createSession({
      deviceNo: snapshot.binding.deviceNo,
    });
    await this.service.unbindDevice(session.id);
    await this.sendWorkerCommand("clear_binding", {});
    return { success: true };
  }

  #requireIdle(snapshot) {
    const recording =
      snapshot.recordingState ||
      snapshot.recording ||
      snapshot.runtime?.recording ||
      "idle";
    if (recording !== "idle") {
      throw controllerError(
        "BINDING_REQUIRES_IDLE",
        "请先停止录音，再变更设备绑定"
      );
    }
  }
}
