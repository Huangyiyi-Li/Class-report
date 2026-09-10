import React, { useEffect, useRef, useState } from "react";
import { recordingResult } from "./recording-result.js";

export function RecordingNotice({ snapshot, open, onClose, onSettings }) {
  const [error, setError] = useState("");
  if (!open) return null;
  const acknowledge = async () => {
    try {
      if (snapshot.recordingNoticeVersion !== undefined)
        await window.recorderShell.acknowledgeRecordingNotice();
      onClose();
    } catch {
      setError("说明阅读状态未保存，可稍后重试。");
    }
  };
  return (
    <section className="recording-notice" aria-label="录音说明">
      <h2>第一次使用？先看这三步</h2>
      <p className="notice-purpose">录下课堂声音，用于生成教学诊断报告。</p>
      <ol className="notice-steps">
        <li>
          <strong>确认教室</strong>
          <span>登录后，选择这台电脑所在的教室。</span>
        </li>
        <li>
          <strong>试试麦克风</strong>
          <span>试录 8 秒，听听声音是否清楚。</span>
        </li>
        <li>
          <strong>结束后看结果</strong>
          <span>点击“停止录音”，再看下方“最近录音”。</span>
        </li>
      </ol>
      <div className="notice-stop">
        <strong>关窗口，不会停止录音</strong>
        <p>
          结束采集请点“停止录音”。开启自动录音后，软件启动并检查通过就会开始录音。
        </p>
      </div>
      {["recording", "starting"].includes(snapshot.recording) && (
        <p className="notice-live">当前正在录音或准备录音。</p>
      )}
      <details className="notice-more">
        <summary>录音存在哪里？谁能查看？</summary>
        <p>
          录音先保存在这台电脑上，联网后自动上传到课堂评价平台。断网也能录音，恢复网络后继续上传。
        </p>
        <p>查看范围由学校和平台设置决定。如有疑问，请联系学校管理员。</p>
      </details>
      {error && <p role="alert">{error}</p>}
      <div className="first-use-actions">
        <button className="notice-primary" onClick={onSettings}>
          去设置
        </button>
        <button className="quiet-action" onClick={acknowledge}>
          知道了
        </button>
      </div>
    </section>
  );
}

export function RecentRecordings({ runs = [], recording }) {
  const time = (value) =>
    value && Number.isFinite(Date.parse(value))
      ? new Date(value).toLocaleString("zh-CN", {
          month: "2-digit",
          day: "2-digit",
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit",
          hour12: false,
        })
      : "结束时间未确认";
  return (
    <section className="recent-recordings" aria-label="最近录音">
      <h2>最近录音</h2>
      {!runs.length ? (
        <p>暂无可核对的记录。此处展示启用本功能后的录音。</p>
      ) : (
        runs.map((run) => {
          const result = recordingResult(run);
          return (
            <article
              key={run.id}
              className={result.complete ? "result-complete" : ""}
            >
              <strong>
                {time(run.startedAt)} —{" "}
                {run.endedAt === null
                  ? recording === "paused"
                    ? "已暂停，尚未结束"
                    : "尚未结束"
                  : time(run.endedAt)}
              </strong>
              <p>{result.local}</p>
              <p>{result.upload}</p>
              {result.warning && (
                <p className="result-warning">{result.warning}</p>
              )}
            </article>
          );
        })
      )}
      <small>
        按一次开始至停止汇总，暂停后继续仍属同一次录音。上传完成不代表报告已生成。
      </small>
    </section>
  );
}

export function MicrophoneTest({ device, recording, configured }) {
  const [probe, setProbe] = useState({ status: "idle" });
  const [audioUrl, setAudioUrl] = useState("");
  const [error, setError] = useState("");
  const generation = useRef(0);
  const timer = useRef(null);
  const url = useRef("");
  const api = window.recorderShell;
  const clearAudio = () => {
    if (url.current) URL.revokeObjectURL(url.current);
    url.current = "";
    setAudioUrl("");
  };
  const cancel = async () => {
    generation.current++;
    clearTimeout(timer.current);
    clearAudio();
    setProbe({ status: "idle" });
    try {
      await api?.cancelMicrophoneTest();
    } catch {
      setError("清除请求未确认，试录会在 8 秒内自动停止。");
    }
  };
  useEffect(() => {
    return () => {
      generation.current++;
      clearTimeout(timer.current);
      if (url.current) URL.revokeObjectURL(url.current);
      url.current = "";
      api?.cancelMicrophoneTest?.().catch(() => {});
    };
  }, [device]);
  useEffect(() => {
    setProbe({ status: "idle" });
    setAudioUrl("");
    setError("");
  }, [device]);
  const start = async () => {
    const current = ++generation.current;
    clearAudio();
    setError("");
    setProbe({ status: "starting" });
    try {
      const started = await api.startMicrophoneTest(device);
      if (current !== generation.current) return;
      setProbe(started);
      const poll = async () => {
        try {
          const result = await api.getMicrophoneTest();
          if (current !== generation.current) return;
          setProbe(result);
          if (result.status === "ready" && result.audio) {
            const bytes = Uint8Array.from(atob(result.audio), (c) =>
              c.charCodeAt(0)
            );
            url.current = URL.createObjectURL(
              new Blob([bytes], { type: "audio/wav" })
            );
            setAudioUrl(url.current);
            // The renderer owns the temporary playback now; erase the worker copy.
            await api.cancelMicrophoneTest();
          } else if (result.status === "recording")
            timer.current = setTimeout(poll, 150);
          else if (result.error) setError(result.error);
        } catch (e) {
          if (current === generation.current) {
            setError(e.message || "试录连接中断，请重试");
            setProbe({ status: "error" });
          }
        }
      };
      timer.current = setTimeout(poll, 150);
    } catch (e) {
      if (current === generation.current) {
        setError(e.message || "无法开始试录");
        setProbe({ status: "error" });
      }
    }
  };
  const busy = ["starting", "recording"].includes(probe.status);
  const available = configured && ["idle", "error"].includes(recording);
  return (
    <div className="microphone-test" aria-label="麦克风测试">
      <strong>麦克风测试</strong>
      <p>
        使用上方所选麦克风试录 8
        秒，再回放确认声音。仅临时保存在内存，不上传；切换设备或关闭设置会清除。
      </p>
      {!available && (
        <p>
          {configured
            ? "请先停止正式录音，再进行测试。"
            : "请先保存录音目录，等待录音服务连接。"}
        </p>
      )}
      <div className="first-use-actions">
        {configured && recording !== "idle" && (
          <button
            type="button"
            className="quiet-action"
            onClick={async () => {
              try {
                await api.stopRecording();
              } catch (e) {
                setError(e.message || "停止录音未确认，请重试");
              }
            }}
          >
            停止正式录音
          </button>
        )}
        <button
          type="button"
          className="quiet-action"
          disabled={!available || busy}
          onClick={start}
        >
          {busy ? `试录中 ${probe.seconds || 0}/8 秒` : "试录 8 秒"}
        </button>
        <button
          type="button"
          className="quiet-action"
          onClick={cancel}
          disabled={probe.status === "idle"}
        >
          结束并清除
        </button>
      </div>
      {busy && (
        <>
          <meter
            min="0"
            max="100"
            value={probe.level || 0}
            aria-label="麦克风输入音量"
          />
          <p>请在平时讲课的位置说一句话，观察音量变化。</p>
        </>
      )}
      {audioUrl && (
        <>
          <audio controls src={audioUrl} aria-label="试录回放" />
          <p>
            {probe.peak > 0
              ? "请点击播放，亲耳确认声音清楚且来自正确的麦克风。"
              : "未检测到明显音量，请回放确认，并检查静音、输入设备和麦克风距离。"}
          </p>
        </>
      )}
      {(error || probe.error) && (
        <p role="alert" className="result-warning">
          {error || probe.error}
        </p>
      )}
    </div>
  );
}
