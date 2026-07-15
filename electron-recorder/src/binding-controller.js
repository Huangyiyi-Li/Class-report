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

  async createSession() {
    const deviceNo = this.resolveDeviceNo();
    if (!deviceNo) {
      throw controllerError("DEVICE_IDENTITY_UNAVAILABLE", "未找到可用的物理网卡设备标识");
    }
    return this.service.createSession({ deviceNo });
  }

  getSession(sessionId) {
    return this.service.getSession(sessionId);
  }

  simulateScan(sessionId) {
    return this.service.simulateScan(sessionId);
  }

  listSchools(sessionId) {
    return this.service.listSchools(sessionId);
  }

  listLocations(sessionId, query) {
    return this.service.listLocations(sessionId, query);
  }

  async confirmBinding(sessionId, selection) {
    const snapshot = this.getSnapshot() || {};
    const recording = snapshot.recordingState || snapshot.recording || snapshot.runtime?.recording || "idle";
    const isRebinding = Boolean(snapshot.binding);
    if (["starting", "recording"].includes(recording) || (isRebinding && recording !== "idle")) {
      throw controllerError("BINDING_REQUIRES_IDLE", "请先停止录音，再重新绑定位置");
    }

    const binding = await this.service.confirmBinding(sessionId, selection);
    await this.sendWorkerCommand("apply_binding", binding);
    return binding;
  }
}
