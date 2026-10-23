import { createRuntimeState } from "./runtime-state.js";

// Feedback follows capture transitions, never upload progress or queue counts.
export function createRecordingFeedback() {
  let previous = "idle";
  let failure = null;
  return (snapshot) => {
    if (
      snapshot.health === "blocked" &&
      snapshot.latestError === "正在启动录音服务"
    )
      return null;
    const runtime = createRuntimeState(snapshot);
    if (!runtime.safe || runtime.recording === "error") {
      const key = runtime.safe ? "capture_error" : runtime.health;
      if (failure === key) return null;
      failure = key;
      const interrupted =
        previous === "recording" || previous === "interrupted";
      previous = interrupted ? "interrupted" : "error";
      return {
        title: interrupted ? "录音已中断" : "尚未开始录音",
        body:
          {
            microphone_unavailable:
              "麦克风不可用，请检查连接并重新选择麦克风。",
            storage_unavailable: "录音保存位置不可用，请检查数据盘。",
            disk_low: "录音保存空间不足，请检查数据盘。",
            binding_required: "请打开客户端，完成教室绑定。",
          }[key] || "采集服务不可用，请打开客户端查看并处理。",
        urgent: true,
      };
    }
    const recovering = previous === "interrupted";
    failure = null;
    if (runtime.recording === previous) return null;
    previous = runtime.recording;
    if (runtime.recording === "recording")
      return {
        title: recovering ? "录音已恢复" : "已开始录音",
        body: "可从系统托盘查看状态、暂停或停止录音。",
      };
    if (runtime.recording === "paused")
      return {
        title: "录音已暂停",
        body: "当前不采集声音，可从系统托盘继续录音。",
      };
    return null;
  };
}
