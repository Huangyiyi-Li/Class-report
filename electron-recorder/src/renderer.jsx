import React, { useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  AlertTriangle,
  ChevronUp,
  Cloud,
  FolderOpen,
  HardDrive,
  Mic,
  Pause,
  Play,
  Power,
  RefreshCcw,
  Settings,
  UploadCloud,
  WifiOff,
  X,
} from "lucide-react";
import { createRuntimeState } from "./runtime-state.js";
import { getHealthMeta, getRecordingMeta, getUploadMeta } from "./state.js";
import { buildWorkerSettingsPatch, saveSettings } from "./settings-save.js";
import { beginFullRebinding, canRebind } from "./binding-flow.js";
import { BindingWizard } from "./binding-wizard.jsx";
import { createFloatingDragController } from "./floating-drag.js";
import {
  API_ROUTE_DEFINITIONS,
  PRODUCTION_API_ROUTES,
  TEST_API_ROUTES,
  detectApiEnvironment,
} from "./api-routes.js";
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
    return () => {
      offSnapshot?.();
      offSettings?.();
    };
  }, []);

  const runtime = snapshot.runtime || createRuntimeState(snapshot);
  if (isFloat) return <FloatingBall recording={runtime.recording} />;
  return (
    <MainWindow
      snapshot={snapshot}
      runtime={runtime}
      settingsOpen={settingsOpen}
      setSettingsOpen={setSettingsOpen}
    />
  );
}

function MainWindow({ snapshot, runtime, settingsOpen, setSettingsOpen }) {
  const [bindingOpen, setBindingOpen] = useState(false);
  const [rebindPending, setRebindPending] = useState(false);
  const home = getHomeState(snapshot, runtime);
  const binding = snapshot.binding || runtime.binding;
  const uploadAttention =
    runtime.pending > 0 ||
    ["failed", "metadata_failed", "network_error", "waiting_network"].includes(
      runtime.upload
    );
  const fullRebind = async () => {
    setRebindPending(true);
    try {
      await beginFullRebinding({
        confirm: () =>
          window.confirm(
            "重新绑定会先解除当前设备归属，并停止当前录音和上传处理。解除后需要重新登录并选择学校和教室。确认继续吗？"
          ),
        unbindDevice: () => shell.unbindDevice(),
        openBinding: () => {
          setSettingsOpen(false);
          setBindingOpen(true);
        },
      });
    } catch (error) {
      window.alert(error?.message || "解除绑定失败，请稍后重试");
    } finally {
      setRebindPending(false);
    }
  };

  return (
    <main className="app-shell">
      <header className="desktop-header">
        <div className="app-identity">
          <span className="app-mark">
            <Mic size={15} />
          </span>
          <strong>课堂录音采集助手</strong>
        </div>
        <div className="window-tools">
          <button
            className="header-action"
            onClick={() => shell?.minimizeToTray?.()}
          >
            <ChevronUp size={16} />
            最小化常驻
          </button>
          <button
            className="header-icon"
            aria-label="维护设置"
            onClick={() => setSettingsOpen(true)}
          >
            <Settings size={19} />
          </button>
        </div>
      </header>

      {binding ? (
        <section className="location-strip">
          <span>当前教室</span>
          <strong>
            {binding.schoolName || "学校未命名"} · {binding.classroom}
          </strong>
          <em>{binding.bindType === 2 ? "公共教室" : "班级教室"}</em>
        </section>
      ) : null}

      {!shell ? (
        <section className="inline-notice danger">
          <AlertTriangle size={18} />
          客户端控制通道未连接，请重新启动客户端。
        </section>
      ) : null}

      <section className={`home-state tone-${home.tone}`}>
        <div className="state-heading">
          <span className="state-symbol">{home.icon}</span>
          <div>
            <h1>{home.title}</h1>
            <p>{home.description}</p>
          </div>
        </div>

        {home.notice ? (
          <div className={`inline-notice ${home.noticeTone || ""}`}>
            <AlertTriangle size={18} />
            <span>{home.notice}</span>
          </div>
        ) : null}

        <div className="home-actions">
          {home.primary === "bind" ? (
            <button
              className="home-primary"
              onClick={() => setBindingOpen(true)}
              data-testid="open-binding"
            >
              登录并绑定设备
            </button>
          ) : null}
          {home.primary === "pause" ? (
            <button
              className="home-primary"
              onClick={() => shell?.pauseRecording?.()}
            >
              <Pause size={20} />
              暂停录音
            </button>
          ) : null}
          {home.primary === "start" ? (
            <button
              className="home-primary"
              onClick={() => shell?.startRecording?.()}
            >
              <Play size={20} />
              {runtime.recording === "paused" ? "继续录音" : "开始录音"}
            </button>
          ) : null}
          {home.primary === "settings" ? (
            <button
              className="home-primary"
              onClick={() => setSettingsOpen(true)}
            >
              <Settings size={19} />
              打开设置
            </button>
          ) : null}
          {home.primary === "clock" ? (
            <>
              <button
                className="home-primary"
                onClick={() => shell?.openSystemTimeSettings?.()}
              >
                打开系统时间设置
              </button>
              <button
                className="home-secondary"
                onClick={() => shell?.recheckRecording?.()}
              >
                <RefreshCcw size={18} />
                重新检测
              </button>
            </>
          ) : null}
          {home.showStop ? (
            <button
              className="home-secondary"
              onClick={() => shell?.stopRecording?.()}
            >
              <Power size={19} />
              停止录音
            </button>
          ) : null}
        </div>
      </section>

      <footer className={`upload-footer ${uploadAttention ? "attention" : ""}`}>
        <div>
          <UploadCloud size={17} />
          <span>
            {runtime.pending > 0
              ? `待上传 ${runtime.pending} 段`
              : "待上传 0 段 · 队列已清空"}
          </span>
          {snapshot.bindingServiceMode === "mock" ? <em>模拟数据</em> : null}
        </div>
        {uploadAttention ? (
          <button
            className="footer-retry"
            onClick={() => shell?.flushQueue?.()}
          >
            立即重试
          </button>
        ) : null}
      </footer>
      {settingsOpen ? (
        <SettingsModal
          snapshot={snapshot}
          runtime={runtime}
          onClose={() => setSettingsOpen(false)}
          onFullRebind={fullRebind}
          rebindPending={rebindPending}
        />
      ) : null}
      <BindingWizard
        open={bindingOpen}
        bindingServiceMode={snapshot.bindingServiceMode || "remote"}
        onClose={() => setBindingOpen(false)}
        onBound={() => {}}
      />
    </main>
  );
}

function getHomeState(snapshot, runtime) {
  const auth = snapshot.authIssue;
  if (auth?.reason === "clock_invalid") {
    return {
      tone: "danger",
      icon: <AlertTriangle size={29} />,
      title: "设备时间不正确",
      description: "当前设备时间与服务器时间不一致，暂时无法录音。",
      notice: "请将 Windows 时间调整为北京时间，返回客户端后重新检测。",
      noticeTone: "danger",
      primary: "clock",
    };
  }
  if (auth?.reason === "signature_invalid") {
    return {
      tone: "danger",
      icon: <AlertTriangle size={29} />,
      title: "暂时无法完成设备认证",
      description: "录音服务已停止。",
      notice: "请联系市场人员并提交维修工单。",
      noticeTone: "danger",
      primary: "settings",
    };
  }
  if (auth?.rebindRequired) {
    return {
      tone: "danger",
      icon: <AlertTriangle size={29} />,
      title: "设备需要重新绑定",
      description: "当前设备归属已失效，暂时无法录音。",
      notice: "请重新完成设备初始化绑定。",
      noticeTone: "danger",
      primary: "bind",
    };
  }
  if (!snapshot.binding && runtime.health === "binding_required") {
    return {
      tone: "idle",
      icon: <Mic size={29} />,
      title: "尚未绑定教室",
      description: "登录并选择教室后，录音服务会立即启用。",
      primary: "bind",
    };
  }
  if (
    ["microphone_unavailable", "mic_error"].includes(runtime.health) ||
    runtime.recording === "microphone_unavailable"
  ) {
    return {
      tone: "danger",
      icon: <Mic size={29} />,
      title: "暂不可录音",
      description: "保存的麦克风当前不可用。",
      notice: "录音已停止。请在设置中重新选择麦克风后再开始录音。",
      noticeTone: "danger",
      primary: "settings",
    };
  }
  if (runtime.recording === "recording") {
    return {
      tone: "recording",
      icon: <span className="live-dot" />,
      title: "录音中",
      description: "采集服务正在持续写入本地文件。",
      primary: "pause",
      showStop: true,
    };
  }
  if (runtime.recording === "paused") {
    return {
      tone: "paused",
      icon: <Pause size={29} />,
      title: "已暂停",
      description: "采集已暂停，已写入的文件仍会继续补传。",
      notice: "当前没有新的音频写入，请记得在下课前继续录音。",
      primary: "start",
      showStop: true,
    };
  }
  if (runtime.recording === "starting") {
    return {
      tone: "preparing",
      icon: <RefreshCcw size={29} />,
      title: "正在准备录音",
      description: "采集服务正在启动，请稍候，不要重复操作。",
    };
  }
  if (["blocked", "error"].includes(runtime.health)) {
    return {
      tone: "danger",
      icon: <AlertTriangle size={29} />,
      title: "暂时无法确认录音状态",
      description: "正在连接录音服务。",
      notice: "客户端正在尝试恢复连接，界面会在服务恢复后自动更新。",
      primary: "settings",
    };
  }
  return {
    tone: "idle",
    icon: <Mic size={29} />,
    title: "未开始录音",
    description: "录音由本机采集服务负责，音频会先安全写入本地。",
    primary: "start",
  };
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
    if (event.currentTarget.hasPointerCapture?.(event.pointerId))
      event.currentTarget.releasePointerCapture(event.pointerId);
  };
  return (
    <main
      className="floating-ball-stage"
      onContextMenu={(event) => {
        event.preventDefault();
        shell?.showFloatingMenu?.();
      }}
    >
      <div
        className={`floating-status-bubble tone-${meta.tone}`}
        onPointerDown={(event) => {
          if (event.button !== 0) return;
          event.currentTarget.setPointerCapture?.(event.pointerId);
          drag.current.start({ x: event.screenX, y: event.screenY });
        }}
        onPointerMove={(event) =>
          drag.current.move({ x: event.screenX, y: event.screenY })
        }
        onPointerUp={(event) => {
          drag.current.end();
          releasePointer(event);
        }}
        onPointerCancel={(event) => {
          drag.current.cancel();
          releasePointer(event);
        }}
        onLostPointerCapture={() => drag.current.cancel()}
      >
        <span className="bubble-ripple" />
        <span className="bubble-icon">
          {recording === "recording" ? (
            <Mic size={18} />
          ) : recording === "paused" ? (
            <Pause size={18} />
          ) : recording.includes("error") ? (
            <WifiOff size={18} />
          ) : (
            <Power size={18} />
          )}
        </span>
        <strong>{meta.bubbleText}</strong>
      </div>
    </main>
  );
}

function SettingsModal({
  snapshot,
  runtime,
  onClose,
  onFullRebind,
  rebindPending,
}) {
  const initial = snapshot.settings || {};
  const [form, setForm] = useState({
    autoLaunch: initial.autoLaunch === true,
    autoRecordEnabled: Boolean(initial.autoRecordEnabled),
    inputDevice: initial.inputDevice || "default",
    dataRoot: initial.dataRoot || snapshot.dataRoot || "",
    apiRoutes: initial.apiRoutes || PRODUCTION_API_ROUTES,
  });
  const [saveError, setSaveError] = useState("");
  const rebindAllowed = canRebind({ ...snapshot, runtime });
  const update = (key, value) =>
    setForm((current) => ({ ...current, [key]: value }));
  const updateRoute = (key, value) =>
    setForm((current) => ({
      ...current,
      apiRoutes: { ...current.apiRoutes, [key]: value },
    }));
  const save = async () => {
    setSaveError("");
    const workerSettings = buildWorkerSettingsPatch(form, {
      dataRootLocked: snapshot.dataRootLocked,
    });
    await saveSettings({
      updateSettings: (value) => shell.updateSettings(value),
      setAutoLaunch: (value) => shell.setAutoLaunch(value),
      workerSettings,
      autoLaunch: form.autoLaunch,
      onClose,
      onUnconfirmed: setSaveError,
    });
  };
  return (
    <div className="modal-backdrop" role="presentation">
      <section
        className="settings-modal"
        role="dialog"
        aria-modal="true"
        aria-label="维护设置"
      >
        <header className="modal-header">
          <div>
            <p className="eyebrow">维护设置</p>
            <h2>运行设置与诊断</h2>
          </div>
          <button
            className="icon-button"
            aria-label="关闭设置"
            onClick={onClose}
          >
            <X size={22} />
          </button>
        </header>
        <div className="settings-scroll">
          <div className="settings-grid">
            <section className="settings-section">
              <h3>
                <Settings size={21} />
                录音设置
              </h3>
              <Toggle
                title="开机自启动"
                description="电脑启动后自动运行客户端"
                checked={form.autoLaunch}
                onChange={(value) => update("autoLaunch", value)}
              />
              <Toggle
                title="自动录音"
                description="客户端启动并通过检查后自动开始录音"
                checked={form.autoRecordEnabled}
                onChange={(value) => update("autoRecordEnabled", value)}
              />
              <label>
                <span>麦克风设备</span>
                <input
                  value={form.inputDevice}
                  onChange={(event) =>
                    update("inputDevice", event.target.value)
                  }
                />
              </label>
              <label>
                <span>录音保存位置</span>
                <input
                  value={form.dataRoot}
                  readOnly={snapshot.dataRootLocked}
                  aria-readonly={snapshot.dataRootLocked}
                  onChange={(event) => update("dataRoot", event.target.value)}
                />
                {snapshot.dataRootLocked ? (
                  <small>
                    保存位置已固定，避免影响现有录音和待上传文件。切换接口环境不会修改此目录。
                  </small>
                ) : null}
              </label>
              <SettingRow
                title="开机自启状态"
                value={formatAutoLaunchStatus(snapshot.autoLaunchStatus)}
              />
              <SettingRow
                title="设备归属"
                value={formatBinding(snapshot.binding || runtime.binding)}
              />
              {snapshot.binding || runtime.binding ? (
                <div className="device-management">
                  <div>
                    <strong>设备管理</strong>
                    <p>更换学校、班级或教室时，需要解除当前绑定并重新登录。</p>
                  </div>
                  <button
                    className="danger-action compact"
                    onClick={onFullRebind}
                    disabled={!rebindAllowed || rebindPending}
                    title={rebindAllowed ? "" : "请先停止录音"}
                  >
                    {rebindPending ? "正在解除绑定…" : "解绑并重新绑定"}
                  </button>
                </div>
              ) : null}
              <SettingRow
                title="当前版本"
                value={`v${snapshot.appVersion || "--"}`}
              />
            </section>
            <section className="settings-section">
              <h3>
                <HardDrive size={21} />
                运行诊断
              </h3>
              <SettingRow title="待上传队列" value={`${runtime.pending} 段`} />
              <SettingRow
                title="已完成队列"
                value={`${snapshot.completed ?? "--"} 段`}
              />
              <SettingRow
                title="磁盘剩余"
                value={formatBytes(snapshot.freeDiskBytes)}
              />
              <SettingRow
                title="最近错误"
                value={snapshot.latestError || "无"}
              />
              <button
                className="secondary-action compact"
                onClick={() => shell?.openDataDir?.()}
              >
                <FolderOpen size={18} />
                打开本地文件夹
              </button>
              <button
                className="quiet-action compact"
                onClick={() => shell?.exportDiagnostics?.()}
              >
                导出诊断信息
              </button>
            </section>
          </div>
          <details className="diagnostics-panel">
            <summary>技术诊断日志</summary>
            <p>录音：{runtime.recording}</p>
            <p>上传：{runtime.upload}</p>
            <p>健康：{runtime.health}</p>
          </details>
          <section className="api-routes-section">
            <div className="api-routes-heading">
              <div>
                <h3>接口路由</h3>
                <p>
                  当前环境：
                  {safeApiEnvironment(form.apiRoutes) === "test"
                    ? "测试环境"
                    : safeApiEnvironment(form.apiRoutes) === "production"
                      ? "正式环境"
                      : "自定义"}
                </p>
              </div>
              <div className="route-presets">
                <button
                  className="home-secondary"
                  onClick={() => update("apiRoutes", TEST_API_ROUTES)}
                >
                  使用测试环境
                </button>
                <button
                  className="home-secondary"
                  onClick={() => update("apiRoutes", PRODUCTION_API_ROUTES)}
                >
                  使用正式环境
                </button>
              </div>
            </div>
            <div className="api-route-list">
              {API_ROUTE_DEFINITIONS.map((route) => (
                <label key={route.key}>
                  <span>{route.label}</span>
                  <input
                    value={form.apiRoutes[route.key] || ""}
                    onChange={(event) =>
                      updateRoute(route.key, event.target.value)
                    }
                  />
                </label>
              ))}
            </div>
          </section>
        </div>
        <footer className="modal-footer">
          {saveError && (
            <p role="alert" className="settings-save-error">
              {saveError}
            </p>
          )}
          <button className="quiet-action" onClick={() => shell?.showFloat?.()}>
            显示悬浮窗
          </button>
          <button className="secondary-action compact" onClick={save}>
            保存设置
          </button>
        </footer>
      </section>
    </div>
  );
}

function Toggle({ title, description, checked, onChange }) {
  return (
    <label className="toggle-row">
      <input
        type="checkbox"
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
      />
      <span className="toggle-track" aria-hidden="true" />
      <div>
        <strong>{title}</strong>
        {description ? <p>{description}</p> : null}
      </div>
    </label>
  );
}
function SettingRow({ title, value }) {
  return (
    <article className="setting-row">
      <div>
        <strong>{title}</strong>
      </div>
      <span>{value}</span>
    </article>
  );
}
function StatusPill({ icon, label, tone }) {
  return (
    <div className={`status-pill ${tone}`}>
      {icon}
      <span>{label}</span>
    </div>
  );
}
function InfoTile({ icon, title, value, tone }) {
  return (
    <div className={`info-tile ${tone}`}>
      {React.cloneElement(icon, { size: 25 })}
      <span>{title}</span>
      <strong>{value}</strong>
    </div>
  );
}
function formatBinding(binding) {
  if (!binding) return "设备未绑定";
  return (
    [binding.schoolName, binding.classroom].filter(Boolean).join(" · ") ||
    "设备未绑定"
  );
}
function formatBytes(bytes) {
  const value = Number(bytes);
  if (!Number.isFinite(value)) return "--";
  return `${(value / 1024 ** 3).toFixed(1)} GB`;
}
function formatAutoLaunchStatus(value) {
  if (!value) return "未验证";
  if (value.status === "verified") return "已验证";
  if (value.status === "failed") return `失败：${value.error || "未知错误"}`;
  return value.actual === null
    ? value.error || "未验证"
    : `未验证（实际${value.actual ? "已开启" : "未开启"}）`;
}

function safeApiEnvironment(routes) {
  try {
    return detectApiEnvironment(routes);
  } catch {
    return "custom";
  }
}

createRoot(document.getElementById("root")).render(<App />);
