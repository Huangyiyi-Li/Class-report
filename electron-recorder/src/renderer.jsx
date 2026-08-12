import React, { useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  AlertTriangle,
  ChevronUp,
  FolderOpen,
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
import { getRecordingMeta } from "./state.js";
import { buildWorkerSettingsPatch, saveSettings } from "./settings-save.js";
import { beginFullRebinding, canRebind } from "./binding-flow.js";
import { BindingWizard } from "./binding-wizard.jsx";
import { authIssueView } from "./auth-issue-view.js";
import { bindingErrorView } from "./binding-error-view.js";
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
  const [actionPending, setActionPending] = useState("");
  const [actionError, setActionError] = useState("");
  const [clockNow, setClockNow] = useState(Date.now());
  const home = getHomeState(snapshot, runtime);
  const binding = snapshot.binding || runtime.binding;
  const uploadAttention =
    runtime.pending > 0 ||
    ["failed", "metadata_failed", "network_error", "waiting_network"].includes(
      runtime.upload
    );
  const uploadSummary = formatUploadSummary(snapshot, runtime);
  useEffect(() => {
    if (runtime.recording !== "recording") return undefined;
    setClockNow(Date.now());
    const timer = window.setInterval(() => setClockNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [runtime.recording, snapshot.recordingStartedAt]);
  const runRecorderAction = async (name, action) => {
    if (!action || actionPending) return;
    setActionPending(name);
    setActionError("");
    try {
      await action();
    } catch (error) {
      setActionError(error?.message || "操作未完成，请根据当前状态检查后重试");
    } finally {
      setActionPending("");
    }
  };
  const fullRebind = async (skipConfirmation = false) => {
    const shouldSkipConfirmation = skipConfirmation === true;
    setRebindPending(true);
    try {
      await beginFullRebinding({
        confirm: () =>
          shouldSkipConfirmation ||
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
      const view = bindingErrorView(error, {
        deviceNo: binding?.deviceNo || snapshot.deviceNo,
        boundSchoolName: binding?.schoolName,
      });
      const message = [
        view.title,
        view.detail,
        view.guidance,
        view.deviceNo ? `设备编号：${view.deviceNo}` : "",
        view.problemCode ? `问题代码：${view.problemCode}` : "",
      ]
        .filter(Boolean)
        .join("\n\n");
      if (
        view.primary === "switch_identity" &&
        window.confirm(`${message}\n\n是否切换账号或学校后重试？`)
      ) {
        await shell.resetBindingAuthentication();
        return fullRebind(true);
      }
      window.alert(message);
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
        <div
          className="desktop-location"
          title={binding ? formatBinding(binding) : "尚未绑定教室"}
        >
          {binding ? (
            <>
              <span>{binding.schoolName || "学校未命名"}</span>
              <i>·</i>
              <strong>{binding.classroom}</strong>
            </>
          ) : (
            <strong>尚未绑定教室</strong>
          )}
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

      {!shell ? (
        <section className="inline-notice danger">
          <AlertTriangle size={18} />
          客户端控制通道未连接，请重新启动客户端。
        </section>
      ) : null}

      <section className={`home-state tone-${home.tone}`}>
        <div className="state-heading">
          <span className="state-symbol">{home.icon}</span>
          <div className="state-copy">
            <h1>{home.title}</h1>
            {runtime.recording === "recording" ? (
              <strong className="recording-elapsed">
                {formatElapsed(snapshot.recordingStartedAt, clockNow)}
              </strong>
            ) : null}
            {home.description ? <p>{home.description}</p> : null}
          </div>
        </div>

        {home.notice ? (
          <div className={`inline-notice ${home.noticeTone || ""}`}>
            <AlertTriangle size={18} />
            <span>{home.notice}</span>
          </div>
        ) : null}

        {home.deviceNo ? (
          <dl className="home-support-reference">
            <div>
              <dt>设备编号</dt>
              <dd>{home.deviceNo}</dd>
            </div>
            <div>
              <dt>问题代码</dt>
              <dd>{home.problemCode}</dd>
            </div>
          </dl>
        ) : null}

        <div className="home-actions">
          {home.primary === "bind" ? (
            <button
              className="home-primary"
              onClick={() => setBindingOpen(true)}
              data-testid="open-binding"
            >
              {home.primaryLabel || "登录并绑定设备"}
            </button>
          ) : null}
          {home.primary === "pause" ? (
            <button
              className="home-primary"
              disabled={Boolean(actionPending)}
              onClick={() =>
                runRecorderAction("pause", () => shell?.pauseRecording?.())
              }
            >
              <Pause size={20} />
              {actionPending === "pause" ? "正在暂停…" : "暂停录音"}
            </button>
          ) : null}
          {home.primary === "start" ? (
            <button
              className="home-primary"
              disabled={Boolean(actionPending)}
              onClick={() =>
                runRecorderAction("start", () => shell?.startRecording?.())
              }
            >
              <Play size={20} />
              {actionPending === "start"
                ? "正在启动…"
                : runtime.recording === "paused"
                  ? "继续录音"
                  : "开始录音"}
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
          {home.primary === "calibrate_clock" ? (
            <>
              <button
                className="home-primary"
                disabled={Boolean(actionPending)}
                onClick={() =>
                  runRecorderAction("calibrate-clock", async () => {
                    await shell?.calibrateSystemTime?.();
                    await shell?.recheckRecording?.();
                  })
                }
              >
                {actionPending === "calibrate-clock"
                  ? "正在校准…"
                  : "自动校准时间"}
              </button>
              <button
                className="home-secondary"
                disabled={Boolean(actionPending)}
                onClick={() => shell?.openSystemTimeSettings?.()}
              >
                打开时间设置
              </button>
            </>
          ) : null}
          {home.primary === "recheck_auth" ? (
            <button
              className="home-primary"
              disabled={Boolean(actionPending)}
              onClick={() =>
                runRecorderAction("recheck-auth", () =>
                  shell?.recheckRecording?.()
                )
              }
            >
              <RefreshCcw size={18} />
              {actionPending === "recheck-auth" ? "正在检测…" : "重新检测"}
            </button>
          ) : null}
          {home.showStop ? (
            <button
              className="home-secondary"
              disabled={Boolean(actionPending)}
              onClick={() =>
                runRecorderAction("stop", () => shell?.stopRecording?.())
              }
            >
              <Power size={19} />
              停止录音
            </button>
          ) : null}
        </div>
        {actionError ? (
          <div className="inline-notice danger" role="alert">
            <AlertTriangle size={18} />
            <span>{actionError}</span>
          </div>
        ) : null}
      </section>

      {uploadAttention ? (
        <footer className="upload-footer attention">
          <div>
            <UploadCloud size={18} />
            <span>{uploadSummary}</span>
            {snapshot.bindingServiceMode === "mock" ? <em>模拟数据</em> : null}
          </div>
          <button
            className="footer-retry"
            disabled={Boolean(actionPending || snapshot.manualFlushActive)}
            onClick={() =>
              runRecorderAction("flush", () => shell?.flushQueue?.())
            }
          >
            {actionPending === "flush" || snapshot.manualFlushActive
              ? "正在重试…"
              : "立即重试"}
          </button>
        </footer>
      ) : null}
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
        replacementRequired={snapshot.authIssue?.reason === "class_not_found"}
        onClose={() => setBindingOpen(false)}
        onBound={() => {}}
      />
    </main>
  );
}

function getHomeState(snapshot, runtime) {
  const auth = snapshot.authIssue;
  const authView = authIssueView(auth, { deviceNo: snapshot.deviceNo });
  if (authView)
    return {
      ...authView,
      icon: <AlertTriangle size={29} />,
      noticeTone: "danger",
    };
  if (!snapshot.binding && runtime.health === "binding_required") {
    return {
      tone: "idle",
      icon: <Mic size={29} />,
      title: "尚未绑定教室",
      description: "登录并选择学校和教室后，才能开始录音。",
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
      title: "无法录音",
      description: "当前选择的麦克风不可用。",
      notice: "请打开设置，选择其他麦克风后重新检测。",
      noticeTone: "danger",
      primary: "settings",
    };
  }
  if (runtime.recording === "recording") {
    return {
      tone: "recording",
      icon: <span className="live-dot" />,
      title: "正在录音",
      primary: "pause",
      showStop: true,
    };
  }
  if (runtime.recording === "paused") {
    return {
      tone: "paused",
      icon: <Pause size={29} />,
      title: "录音已暂停",
      description: "暂停期间不会录制声音。",
      primary: "start",
      showStop: true,
    };
  }
  if (runtime.recording === "starting") {
    return {
      tone: "preparing",
      icon: <RefreshCcw size={29} />,
      title: "正在准备录音",
      description: "正在检查麦克风和录音保存位置，请稍候。",
    };
  }
  if (
    runtime.health === "blocked" &&
    snapshot.latestError === "正在启动录音服务"
  ) {
    return {
      tone: "preparing",
      icon: <RefreshCcw size={29} />,
      title: "正在准备录音",
      description: "正在检查录音条件，请稍候。",
    };
  }
  if (["blocked", "error"].includes(runtime.health)) {
    return {
      tone: "danger",
      icon: <AlertTriangle size={29} />,
      title: "当前无法录音",
      description: snapshot.latestError || "录音服务暂时不可用。",
      notice: "客户端正在尝试恢复连接，界面会在服务恢复后自动更新。",
      primary: "settings",
    };
  }
  return {
    tone: "idle",
    icon: <Mic size={29} />,
    title: "录音尚未开始",
    description: "需要录制时，请点击“开始录音”。",
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
  const [inputDevices, setInputDevices] = useState([
    { value: "default", label: "系统默认麦克风" },
  ]);
  const [deviceLoadError, setDeviceLoadError] = useState("");
  const rebindAllowed = canRebind({ ...snapshot, runtime });
  const update = (key, value) =>
    setForm((current) => ({ ...current, [key]: value }));
  const updateRoute = (key, value) =>
    setForm((current) => ({
      ...current,
      apiRoutes: { ...current.apiRoutes, [key]: value },
    }));
  useEffect(() => {
    let active = true;
    shell
      ?.listInputDevices?.()
      .then((devices) => {
        if (!active || !Array.isArray(devices)) return;
        setInputDevices(devices);
        setDeviceLoadError("");
      })
      .catch(() => {
        if (active)
          setDeviceLoadError("暂时无法读取麦克风列表，请稍后重新打开设置");
      });
    return () => {
      active = false;
    };
  }, []);
  const chooseDataRoot = async () => {
    if (snapshot.dataRootLocked) {
      await shell?.openDataDir?.();
      return;
    }
    const selected = await shell?.chooseDataRoot?.();
    if (selected) update("dataRoot", selected);
  };
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
        aria-label="设置"
      >
        <header className="modal-header">
          <div>
            <h2>设置</h2>
            <p>调整这台电脑的录音和运行方式</p>
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
          <section className="settings-section current-device-section">
            <h3>当前设备</h3>
            <div className="device-identity-summary">
              <span className="device-identity-icon">
                <Mic size={21} />
              </span>
              <div>
                <strong>
                  {(snapshot.binding || runtime.binding)?.schoolName ||
                    "尚未绑定学校"}
                </strong>
                <p>
                  {(snapshot.binding || runtime.binding)?.classroom ||
                    "完成绑定后才能开始录音"}
                </p>
              </div>
              <span
                className={`device-state tone-${getRecordingMeta(runtime.recording).tone}`}
              >
                {formatRecordingStatus(runtime.recording)}
              </span>
            </div>
          </section>
          <div className="settings-flow">
            <section className="settings-section recording-settings-section">
              <div className="settings-section-heading">
                <h3>录音</h3>
                <p>影响日常录音的设置</p>
              </div>
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
                <select
                  value={form.inputDevice}
                  onChange={(event) =>
                    update("inputDevice", event.target.value)
                  }
                >
                  {!inputDevices.some(
                    (device) => device.value === form.inputDevice
                  ) && form.inputDevice !== "default" ? (
                    <option value={form.inputDevice} disabled>
                      {form.inputDevice}（当前不可用）
                    </option>
                  ) : null}
                  {inputDevices.map((device) => (
                    <option key={device.value} value={device.value}>
                      {device.label}
                    </option>
                  ))}
                </select>
                {deviceLoadError ? <small>{deviceLoadError}</small> : null}
              </label>
              <label>
                <span>录音保存位置</span>
                <div className="setting-field-action">
                  <input
                    value={form.dataRoot}
                    readOnly
                    aria-readonly="true"
                    placeholder="请选择非系统盘文件夹"
                  />
                  <button
                    type="button"
                    className="quiet-action compact"
                    onClick={chooseDataRoot}
                  >
                    <FolderOpen size={17} />
                    {snapshot.dataRootLocked ? "打开文件夹" : "选择文件夹"}
                  </button>
                </div>
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
              <div className="settings-control-row">
                <div>
                  <strong>录音悬浮窗</strong>
                  <p>显示当前录音状态，点击可打开主窗口</p>
                </div>
                <button
                  className="quiet-action compact"
                  onClick={() => shell?.showFloat?.()}
                >
                  显示录音悬浮窗
                </button>
              </div>
            </section>
            <section className="settings-section software-settings-section">
              <div className="settings-section-heading">
                <h3>软件</h3>
              </div>
              <SettingRow
                title="当前版本"
                value={`v${snapshot.appVersion || "--"}`}
              />
              <UpdateSetting
                update={snapshot.update}
                recording={runtime.recording}
                onError={setSaveError}
              />
            </section>
            <details className="advanced-settings-section">
              <summary>
                <span>
                  <strong>高级设置</strong>
                  <small>供部署和技术排查使用</small>
                </span>
              </summary>
              <section className="advanced-diagnostics">
                <div className="settings-section-heading">
                  <h3>诊断信息</h3>
                  <p>仅在排查异常时查看</p>
                </div>
                <SettingRow
                  title="设备认证"
                  value={formatDiagnosticStatus(
                    snapshot.uploadDiagnostics?.deviceAuth
                  )}
                />
                <SettingRow
                  title="上传凭证"
                  value={formatDiagnosticStatus(
                    snapshot.uploadDiagnostics?.ossCredentials
                  )}
                />
                <SettingRow
                  title="OSS 目标"
                  value={formatOssTarget(snapshot.uploadDiagnostics)}
                />
                <SettingRow
                  title="等待上传"
                  value={`${countQueueStatuses(snapshot.queueDiagnostics, [
                    "pending",
                    "uploading",
                    "failed",
                  ])} 段`}
                />
                <SettingRow
                  title="已上传，等待登记"
                  value={`${countQueueStatuses(snapshot.queueDiagnostics, [
                    "uploaded",
                    "registering",
                    "metadata_failed",
                  ])} 段`}
                />
                {Number(snapshot.localMissing || 0) > 0 ? (
                  <SettingRow
                    title="本地文件已缺失"
                    value={`${snapshot.localMissing} 段（不再重试）`}
                  />
                ) : null}
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
                  value={
                    snapshot.latestUploadError ||
                    snapshot.uploadDetail?.error ||
                    snapshot.uploadDiagnostics?.lastError ||
                    snapshot.latestError ||
                    "无"
                  }
                />
                <SettingRow
                  title="下次自动重试"
                  value={formatRetryAt(snapshot.uploadDetail?.retryAt)}
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
            </details>
          </div>
          {snapshot.binding || runtime.binding ? (
            <section className="settings-section device-management-section">
              <div className="settings-section-heading">
                <h3>设备管理</h3>
                <p>更换学校、班级或教室</p>
              </div>
              <div className="device-management">
                <div>
                  <strong>解除当前设备绑定</strong>
                  <p>
                    {rebindAllowed
                      ? "解除后，需要重新登录并选择学校和教室。"
                      : "当前录音尚未结束。请先停止录音，再解除设备绑定。"}
                  </p>
                </div>
                <button
                  className="danger-action compact"
                  onClick={onFullRebind}
                  disabled={!rebindAllowed || rebindPending}
                  title={rebindAllowed ? "" : "请先停止录音，再解除设备绑定"}
                >
                  {rebindPending ? "正在解除绑定…" : "解绑并重新绑定"}
                </button>
              </div>
            </section>
          ) : null}
        </div>
        <footer className="modal-footer">
          {saveError && (
            <p role="alert" className="settings-save-error">
              {saveError}
            </p>
          )}
          <button className="quiet-action" onClick={onClose}>
            取消
          </button>
          <button className="home-primary settings-save-action" onClick={save}>
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

function UpdateSetting({ update, recording, onError }) {
  const state = update || { status: "unsupported" };
  const recordingActive = ["recording", "starting"].includes(recording);
  const check = async () => {
    onError("");
    try {
      await shell?.checkForUpdates?.();
    } catch (error) {
      onError(error?.message || "检查更新失败，请稍后重试");
    }
  };
  const install = async () => {
    onError("");
    try {
      await shell?.installUpdate?.();
    } catch (error) {
      onError(error?.message || "更新安装未能开始，请稍后重试");
    }
  };
  const labels = {
    idle: "可检查新版本",
    checking: "正在检查更新",
    current: "当前已是最新版本",
    downloading: `正在下载 ${state.percent || 0}%`,
    ready: `新版本 v${state.availableVersion || "--"} 已下载`,
    installing: "正在重启并安装",
    error: state.error || "检查更新失败",
    unsupported: "便携版或开发版本不支持应用内更新",
  };

  return (
    <article className="update-setting">
      <div>
        <strong>软件更新</strong>
        <p>{labels[state.status] || labels.idle}</p>
        {state.status === "ready" && recordingActive ? (
          <small>正在录音，请先暂停录音后再安装更新。</small>
        ) : null}
      </div>
      {state.status === "ready" ? (
        <button
          className="secondary-action compact"
          onClick={install}
          disabled={recordingActive}
        >
          重启并安装
        </button>
      ) : (
        <button
          className="quiet-action compact"
          onClick={check}
          disabled={[
            "checking",
            "downloading",
            "installing",
            "unsupported",
          ].includes(state.status)}
        >
          {state.status === "checking"
            ? "正在检查…"
            : state.status === "downloading"
              ? `下载中 ${state.percent || 0}%`
              : "检查更新"}
        </button>
      )}
    </article>
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

function formatRecordingStatus(value) {
  const labels = {
    recording: "正在录音",
    paused: "录音已暂停",
    starting: "正在准备",
    idle: "录音尚未开始",
    microphone_unavailable: "无法录音",
    recording_error: "无法录音",
    error: "无法录音",
  };
  return labels[value] || "状态未知";
}

function formatElapsed(startedAt, now = Date.now()) {
  const start = Date.parse(startedAt || "");
  if (!Number.isFinite(start)) return "00:00:00";
  const seconds = Math.max(0, Math.floor((now - start) / 1000));
  const hours = String(Math.floor(seconds / 3600)).padStart(2, "0");
  const minutes = String(Math.floor((seconds % 3600) / 60)).padStart(2, "0");
  const remainder = String(seconds % 60).padStart(2, "0");
  return `${hours}:${minutes}:${remainder}`;
}

function countQueueStatuses(queueDiagnostics, statuses) {
  const counts = queueDiagnostics?.counts || {};
  return statuses.reduce(
    (total, status) => total + Number(counts[status] || 0),
    0
  );
}

function formatUploadSummary(snapshot, runtime) {
  if (snapshot.manualFlushActive) return "正在检查待处理录音并重试";
  const detail = snapshot.uploadDetail || {};
  if (detail.status === "started") {
    return detail.stage === "registration"
      ? "文件已上传，正在登记录音信息"
      : "正在上传录音文件";
  }
  const waitingRegistration = countQueueStatuses(snapshot.queueDiagnostics, [
    "uploaded",
    "registering",
    "metadata_failed",
  ]);
  const waitingUpload = countQueueStatuses(snapshot.queueDiagnostics, [
    "pending",
    "uploading",
    "failed",
  ]);
  if (waitingUpload > 0 && waitingRegistration > 0) {
    return `等待上传 ${waitingUpload} 段 · 等待登记 ${waitingRegistration} 段`;
  }
  if (waitingUpload > 0) return `等待上传 ${waitingUpload} 段`;
  if (waitingRegistration > 0)
    return `已上传，等待登记 ${waitingRegistration} 段`;
  return runtime.pending > 0
    ? `待处理 ${runtime.pending} 段`
    : "没有待处理的录音";
}

function formatDiagnosticStatus(status) {
  const labels = {
    available: "已获取",
    checking: "正在获取",
    failed: "获取失败",
  };
  return labels[status] || "尚未验证";
}

function formatOssTarget(diagnostics = {}) {
  const values = [diagnostics?.bucket, diagnostics?.endpoint].filter(Boolean);
  return values.length ? values.join(" · ") : "尚未获取";
}

function formatRetryAt(value) {
  const time = Number(value);
  if (!Number.isFinite(time) || time <= 0) return "无等待中的重试";
  return new Date(time).toLocaleString("zh-CN", { hour12: false });
}

function safeApiEnvironment(routes) {
  try {
    return detectApiEnvironment(routes);
  } catch {
    return "custom";
  }
}

createRoot(document.getElementById("root")).render(<App />);
