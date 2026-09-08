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
      ? "未形成可确认的录音文件"
      : "尚未形成可确认的录音片段";
  if (total && run.saved < total)
    local =
      completed === total
        ? "云端已接收，本地部分文件已清理或缺失"
        : "部分本地文件缺失，请检查录音保存位置";
  if (incomplete) local += "；部分片段尚未完成保存";
  let upload = total
    ? `已上传并登记 ${completed}/${total} 段`
    : "暂无可上传片段";
  if (complete) upload = "本次录音已上传并登记完成";
  else if (run.counts?.local_missing) upload += "；存在缺失文件，无法完成补传";
  else if (run.counts?.failed || run.counts?.metadata_failed)
    upload += "；部分失败，等待重试";
  else if (total > completed) upload += "；其余等待上传或登记";
  return {
    complete,
    local,
    upload,
    warning: interrupted
      ? "本次录音发生中断或保存不完整，请核对有效时段。"
      : "",
  };
}
