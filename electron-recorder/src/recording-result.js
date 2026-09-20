export function recordingResult(run) {
  const total = Number(run.segments || 0);
  const completed = Number(run.completed || 0);
  const stopped = run.endedAt !== null && run.endedAt !== undefined;
  const incomplete = stopped && Number(run.expected || 0) > total;
  const interrupted = Boolean(run.interrupted || incomplete);
  const complete = stopped && total > 0 && completed === total && !interrupted;
  let local = total
    ? `已保存 ${total} 段`
    : stopped
      ? "本次没有已保存的录音"
      : "正在录制，首段录音尚未保存完成";
  if (total && run.saved < total)
    local =
      completed === total
        ? "云端已接收，本地部分文件已清理或缺失"
        : "部分本地录音文件缺失";
  if (incomplete) local += "；有片段未完成保存";
  let upload = total
    ? `平台已接收 ${completed}/${total} 段`
    : "暂无待上传录音";
  if (total > 0 && completed === total) upload = "已保存的录音已上传";
  else if (run.counts?.local_missing) upload += "；缺失文件无法上传";
  else if (run.counts?.failed || run.counts?.metadata_failed)
    upload += "；未完成的录音会自动重试上传";
  else if (total > completed) upload += "；其余等待上传完成";
  return {
    complete,
    local,
    upload,
    warning: interrupted
      ? incomplete ? "本次有录音未完成保存。" : "本次录音的完整性未确认。"
      : "",
  };
}
