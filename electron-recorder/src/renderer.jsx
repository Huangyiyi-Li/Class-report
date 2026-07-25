import React, { useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import { AlertTriangle, Check, ChevronUp, Cloud, FolderOpen, HardDrive, Mic, Pause, Play, Power, RefreshCcw, Settings, UploadCloud, WifiOff, X } from "lucide-react";
import { createRuntimeState } from "./runtime-state.js";
import { getHealthMeta, getRecordingMeta, getUploadMeta } from "./state.js";
import { saveSettings } from "./settings-save.js";
import { canRebind } from "./binding-flow.js";
import { BindingWizard } from "./binding-wizard.jsx";
import { createFloatingDragController } from "./floating-drag.js";
import "./styles.css";

const shell = window.recorderShell;
const FLOATING_HASHES = new Set(["#floating-ball", "#/floating-ball"]);

function App() {
  const isFloat = FLOATING_HASHES.has(window.location.hash);
  const [snapshot, setSnapshot] = useState({});
  const [settingsOpen, setSettingsOpen] = useState(false);

  useEffect(() => {
    document.documentElement.dataset.view = isFloat ? "float" : "main";
    document.body.classList.toggle("float-mode", isFloat);
    return () => document.body.classList.remove("float-mode");
  }, [isFloat]);

  useEffect(() => {
    shell?.getSnapshot?.().then((value) => value && setSnapshot(value));
    const offSnapshot = shell?.onSnapshot?.(setSnapshot);
    const offSettings = shell?.onOpenSettings?.(() => setSettingsOpen(true));
    return () => { offSnapshot?.(); offSettings?.(); };
  }, []);

  const runtime = snapshot.runtime || createRuntimeState(snapshot);
  if (isFloat) return <FloatingBall recording={runtime.recording} />;
  return <MainWindow snapshot={snapshot} runtime={runtime} settingsOpen={settingsOpen} setSettingsOpen={setSettingsOpen} />;
}

function MainWindow({ snapshot, runtime, settingsOpen, setSettingsOpen }) {
  const [bindingOpen, setBindingOpen] = useState(false);
  const recording = getRecordingMeta(runtime.recording);
  const upload = getUploadMeta(runtime.upload);
  const health = getHealthMeta(runtime.health);
  const location = formatBinding(snapshot.binding || runtime.binding);
  const canStart = runtime.safe && runtime.recording !== "recording";

  return (
    <main className="app-shell">
      <header className="topbar">
        <div><p className="eyebrow">{location}</p><div className="title-row"><h1>课堂录音采集助手</h1><span className="version-badge">v{snapshot.appVersion || "--"}</span></div></div>
        <div className="top-actions">
          <StatusPill icon={<UploadCloud />} label={`${upload.label} · ${runtime.pending} 段`} tone={upload.tone} />
          <StatusPill icon={<HardDrive />} label={health.label} tone={health.tone} />
          <button className="ghost-button" onClick={() => shell?.minimizeToTray?.()}><ChevronUp size={18} />最小化常驻</button>
          <button className="icon-button" aria-label="维护设置" onClick={() => setSettingsOpen(true)}><Settings size={21} /></button>
        </div>
      </header>
      {!shell ? <section className="bridge-warning"><AlertTriangle size={20} />客户端控制通道未连接，请重新安装最新版安装包。</section> : null}
      {snapshot.binding || runtime.health === "binding_required" ? <BindingBanner snapshot={snapshot} runtime={runtime} onOpen={() => setBindingOpen(true)} /> : null}
      <section className="layout">
        <section className={`record-card tone-${recording.tone}`}>
          <div className="card-label">当前课堂录音</div>
          <div className="hero-row"><span className={`record-dot ${runtime.recording === "recording" ? "live" : ""}`} /><div><h2>{recording.label}</h2><p>{recording.helper}</p></div></div>
          <div className="state-grid">
            <InfoTile icon={<Mic />} title="录音状态" value={recording.label} tone={runtime.safe ? "green" : "orange"} />
            <InfoTile icon={<UploadCloud />} title="上传状态" value={`${upload.label} · ${runtime.pending} 段`} tone={runtime.pending ? "orange" : "green"} />
            <InfoTile icon={<Check />} title="设备健康" value={health.label} tone={runtime.safe ? "green" : "orange"} />
          </div>
          <div className="primary-actions">
            {runtime.recording === "recording" ? <button className="danger-action" onClick={() => shell?.pauseRecording?.()}><Pause size={24} />暂停录音</button> : <button className="primary-action" disabled={!canStart} onClick={() => shell?.startRecording?.()}><Play size={25} />开始录音</button>}
            <button className="secondary-action" onClick={() => shell?.stopRecording?.()}><Power size={22} />停止录音</button>
            <button className="quiet-action" onClick={() => shell?.flushQueue?.()}><RefreshCcw size={20} />重新上传待传文件</button>
          </div>
        </section>
        <aside className="side-panel">
          <section className="soft-card"><div className="section-title"><Cloud size={22} />上传队列</div><p>{upload.label}</p><strong>{runtime.pending} 段待处理</strong></section>
          <section className="soft-card alert-card"><div className="section-title"><AlertTriangle size={22} />设备健康</div><p>{health.label}</p></section>
          <section className="soft-card history-card"><div className="section-title">最近错误</div><p>{snapshot.latestError || "暂无错误"}</p></section>
        </aside>
      </section>
      {settingsOpen ? <SettingsModal snapshot={snapshot} runtime={runtime} onClose={() => setSettingsOpen(false)} /> : null}
      <BindingWizard
        open={bindingOpen}
        isRebinding={Boolean(snapshot.binding)}
        bindingServiceMode={snapshot.bindingServiceMode || "remote"}
        onClose={() => setBindingOpen(false)}
        onBound={() => {}}
      />
    </main>
  );
}

function BindingBanner({ snapshot, runtime, onOpen }) {
  const [unbinding, setUnbinding] = useState(false);
  const binding = snapshot.binding;
  const rebindAllowed = canRebind({ ...snapshot, runtime });
  if (!binding) return <section className="binding-gate unbound"><div className="binding-gate-icon"><AlertTriangle size={22} /></div><div><span className="binding-gate-label">需要完成设备配置</span><strong>设备尚未绑定班级或公共教室</strong><p>使用 Passport 登录并选择教室后，录音服务会立即启用。</p></div><button className="binding-action" onClick={onOpen} data-testid="open-binding">登录并绑定设备</button></section>;
  const type = binding.bindType === 2 ? "公共教室" : "班级教室";
  const unbind = async () => {
    if (!window.confirm("解除绑定后将立即停止生产上传，并要求重新绑定才能录音。确认继续吗？")) return;
    setUnbinding(true);
    try {
      await shell.unbindDevice();
    } catch (error) {
      window.alert(error?.message || "解绑失败，请稍后重试");
    } finally {
      setUnbinding(false);
    }
  };
  return <section className="binding-gate bound"><div className="binding-gate-icon"><Check size={22} /></div><div><span className="binding-gate-label">当前设备归属 {binding.bindingSource === "mock" ? <em>模拟数据</em> : null}</span><strong>{binding.schoolName || "学校未命名"} · {binding.classroom}</strong><p>{type}{binding.className ? ` · ${binding.className}` : ""}</p></div><button className="binding-action danger" onClick={unbind} disabled={!rebindAllowed || unbinding} title={rebindAllowed ? "" : "请先停止录音"}>{unbinding ? "正在解绑…" : "解除绑定"}</button><button className="binding-action subtle" onClick={onOpen} disabled={!rebindAllowed || unbinding} title={rebindAllowed ? "" : "请先停止录音"} data-testid="open-binding">重新绑定</button></section>;
}

function FloatingBall({ recording }) {
  const meta = getRecordingMeta(recording);
  const drag = useRef(null);
  if (!drag.current) {
    drag.current = createFloatingDragController({
      onStart: (point) => shell?.startFloatingDrag?.(point),
      onMove: (point) => shell?.moveFloatingDrag?.(point),
      onEnd: () => shell?.endFloatingDrag?.(),
      onClick: () => shell?.showMain?.(),
    });
  }
  const releasePointer = (event) => {
    if (event.currentTarget.hasPointerCapture?.(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId);
  };
  return <main className="floating-ball-stage" onContextMenu={(event) => { event.preventDefault(); shell?.showFloatingMenu?.(); }}><div className={`floating-status-bubble tone-${meta.tone}`}
    onPointerDown={(event) => { if (event.button !== 0) return; event.currentTarget.setPointerCapture?.(event.pointerId); drag.current.start({ x: event.screenX, y: event.screenY }); }}
    onPointerMove={(event) => drag.current.move({ x: event.screenX, y: event.screenY })}
    onPointerUp={(event) => { drag.current.end(); releasePointer(event); }}
    onPointerCancel={(event) => { drag.current.cancel(); releasePointer(event); }}
    onLostPointerCapture={() => drag.current.cancel()}>
    <span className="bubble-ripple" /><span className="bubble-icon">{recording === "recording" ? <Mic size={18} /> : recording === "paused" ? <Pause size={18} /> : recording.includes("error") ? <WifiOff size={18} /> : <Power size={18} />}</span><strong>{meta.bubbleText}</strong>
  </div></main>;
}

function SettingsModal({ snapshot, runtime, onClose }) {
  const initial = snapshot.settings || {};
  const [form, setForm] = useState({ autoLaunch: initial.autoLaunch === true, autoRecordEnabled: Boolean(initial.autoRecordEnabled), inputDevice: initial.inputDevice || "default", dataRoot: initial.dataRoot || snapshot.dataRoot || "" });
  const [saveError, setSaveError] = useState("");
  const update = (key, value) => setForm((current) => ({ ...current, [key]: value }));
  const save = async () => {
    setSaveError("");
    const { autoLaunch, ...workerSettings } = form;
    await saveSettings({
      updateSettings: (value) => shell.updateSettings(value),
      setAutoLaunch: (value) => shell.setAutoLaunch(value),
      workerSettings, autoLaunch, onClose, onUnconfirmed: setSaveError,
    });
  };
  return <div className="modal-backdrop" role="presentation"><section className="settings-modal" role="dialog" aria-modal="true" aria-label="维护设置">
    <header className="modal-header"><div><p className="eyebrow">维护设置</p><h2>运行设置与诊断</h2></div><button className="icon-button" aria-label="关闭设置" onClick={onClose}><X size={22} /></button></header>
    <div className="settings-scroll"><div className="settings-grid">
      <section className="settings-section"><h3><Settings size={21} />录音设置</h3>
        <Toggle title="开机自启动" checked={form.autoLaunch} onChange={(value) => update("autoLaunch", value)} />
        <Toggle title="自动录音" checked={form.autoRecordEnabled} onChange={(value) => update("autoRecordEnabled", value)} />
        <label><span>麦克风设备 ID</span><input value={form.inputDevice} onChange={(event) => update("inputDevice", event.target.value)} /></label>
        <label><span>录音数据目录</span><input value={form.dataRoot} disabled={snapshot.dataRootLocked} onChange={(event) => update("dataRoot", event.target.value)} />{snapshot.dataRootLocked ? <small>如需修改请重新部署</small> : null}</label>
        <SettingRow title="开机自启状态" value={formatAutoLaunchStatus(snapshot.autoLaunchStatus)} />
        <SettingRow title="设备归属" value={formatBinding(snapshot.binding || runtime.binding)} /><SettingRow title="当前版本" value={`v${snapshot.appVersion || "--"}`} />
      </section>
      <section className="settings-section"><h3><HardDrive size={21} />运行诊断</h3>
        <SettingRow title="待上传队列" value={`${runtime.pending} 段`} /><SettingRow title="已完成队列" value={`${snapshot.completed ?? "--"} 段`} />
        <SettingRow title="磁盘剩余" value={formatBytes(snapshot.freeDiskBytes)} /><SettingRow title="最近错误" value={snapshot.latestError || "无"} />
        <button className="secondary-action compact" onClick={() => shell?.openDataDir?.()}><FolderOpen size={18} />打开本地文件夹</button>
        <button className="quiet-action compact" onClick={() => shell?.exportDiagnostics?.()}>导出诊断信息</button>
      </section>
    </div><details className="diagnostics-panel"><summary>技术诊断日志</summary><p>录音：{runtime.recording}</p><p>上传：{runtime.upload}</p><p>健康：{runtime.health}</p></details></div>
    <footer className="modal-footer">{saveError && <p role="alert" className="settings-save-error">{saveError}</p>}<button className="quiet-action" onClick={() => shell?.showFloat?.()}>显示悬浮窗</button><button className="secondary-action compact" onClick={save}>保存设置</button></footer>
  </section></div>;
}

function Toggle({ title, checked, onChange }) { return <label className="toggle-row"><input type="checkbox" checked={checked} onChange={(event) => onChange(event.target.checked)} /><span className="toggle-track" aria-hidden="true" /><div><strong>{title}</strong></div></label>; }
function SettingRow({ title, value }) { return <article className="setting-row"><div><strong>{title}</strong></div><span>{value}</span></article>; }
function StatusPill({ icon, label, tone }) { return <div className={`status-pill ${tone}`}>{icon}<span>{label}</span></div>; }
function InfoTile({ icon, title, value, tone }) { return <div className={`info-tile ${tone}`}>{React.cloneElement(icon, { size: 25 })}<span>{title}</span><strong>{value}</strong></div>; }
function formatBinding(binding) { if (!binding) return "设备未绑定"; return [binding.schoolName, binding.classroom].filter(Boolean).join(" · ") || "设备未绑定"; }
function formatBytes(bytes) { const value = Number(bytes); if (!Number.isFinite(value)) return "--"; return `${(value / 1024 ** 3).toFixed(1)} GB`; }
function formatAutoLaunchStatus(value) { if (!value) return "未验证"; if (value.status === "verified") return "已验证"; if (value.status === "failed") return `失败：${value.error || "未知错误"}`; return value.actual === null ? (value.error || "未验证") : `未验证（实际${value.actual ? "已开启" : "未开启"}）`; }

createRoot(document.getElementById("root")).render(<App />);
