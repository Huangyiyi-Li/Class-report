export const RECORDING_META = {
  idle: { label: "未开始录音", tone: "idle", helper: "录音由本机采集服务负责，音频会先安全写入本地。", bubbleText: "待机", bubbleIcon: "standby" },
  recording: { label: "录音中", tone: "recording", helper: "采集服务正在持续写入本地文件。", bubbleText: "录音中", bubbleIcon: "recording" },
  paused: { label: "已暂停", tone: "paused", helper: "采集已暂停，已写入的文件仍会继续补传。", bubbleText: "暂停", bubbleIcon: "paused" },
  error: { label: "录音异常", tone: "danger", helper: "采集服务发生异常，请查看设备健康状态。", bubbleText: "异常", bubbleIcon: "offline" },
  recording_error: { label: "暂不可录音", tone: "danger", helper: "当前设备状态不满足安全录音条件。", bubbleText: "不可用", bubbleIcon: "offline" },
};

export const UPLOAD_META = {
  clear: { label: "队列已清空", tone: "ok" },
  mock_blocked: { label: "模拟模式，仅保存本地", tone: "mock" },
  uploading: { label: "上传中", tone: "sync" },
  waiting_network: { label: "等待网络", tone: "danger" },
  failed: { label: "上传失败", tone: "danger" },
};

export const HEALTH_META = {
  healthy: { label: "设备正常", tone: "ok" },
  storage_unavailable: { label: "存储不可用", tone: "danger" },
  disk_low: { label: "磁盘空间不足", tone: "danger" },
  microphone_unavailable: { label: "麦克风不可用", tone: "danger" },
  binding_required: { label: "设备尚未绑定", tone: "danger" },
  error: { label: "服务异常", tone: "danger" },
};

export const getRecordingMeta = (state) => RECORDING_META[state] || RECORDING_META.error;
export const getUploadMeta = (state) => UPLOAD_META[state] || { label: state || "未知", tone: "danger" };
export const getHealthMeta = (state) => HEALTH_META[state] || { label: state || "未知", tone: "danger" };
