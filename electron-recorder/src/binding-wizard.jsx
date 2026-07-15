import React, { useEffect, useReducer, useState } from "react";
import {
  ArrowLeft,
  Building2,
  Check,
  CheckCircle2,
  LoaderCircle,
  MapPin,
  QrCode,
  Radio,
  RotateCcw,
  School,
  Smartphone,
  X,
} from "lucide-react";
import { QRCodeSVG } from "qrcode.react";

import {
  bindingFlowReducer,
  canSimulateScan,
  initialBindingFlow,
} from "./binding-flow.js";

const api = window.recorderShell;

export function BindingWizard({ open, isRebinding, bindingServiceMode, onClose, onBound }) {
  const [state, dispatch] = useReducer(bindingFlowReducer, initialBindingFlow);
  const [rebindApproved, setRebindApproved] = useState(false);
  const [remainingSeconds, setRemainingSeconds] = useState(0);

  useEffect(() => {
    if (!open) {
      setRebindApproved(false);
      dispatch({ type: "CLOSE" });
      return;
    }
    if (!isRebinding) dispatch({ type: "OPEN" });
  }, [open, isRebinding]);

  useEffect(() => {
    if (!open || state.phase !== "creating") return undefined;
    let active = true;
    api.createBindingSession()
      .then((session) => active && dispatch({ type: "SESSION_UPDATED", session }))
      .catch((error) => active && fail(dispatch, error));
    return () => { active = false; };
  }, [open, state.phase]);

  useEffect(() => {
    if (!open || state.phase !== "waiting" || !state.session?.id) return undefined;
    let active = true;
    const poll = () => api.getBindingSession(state.session.id)
      .then((session) => active && dispatch({ type: "SESSION_UPDATED", session }))
      .catch((error) => active && fail(dispatch, error));
    const timer = setInterval(poll, 800);
    return () => { active = false; clearInterval(timer); };
  }, [open, state.phase, state.session?.id]);

  useEffect(() => {
    if (!open || state.phase !== "scanned" || !state.session?.id) return undefined;
    let active = true;
    api.listBindingSchools(state.session.id)
      .then((schools) => active && dispatch({ type: "SCHOOLS_LOADED", schools }))
      .catch((error) => active && fail(dispatch, error));
    return () => { active = false; };
  }, [open, state.phase, state.session?.id]);

  useEffect(() => {
    if (!state.session?.expiresAt || state.phase !== "waiting") return undefined;
    const update = () => setRemainingSeconds(Math.max(0, Math.ceil((Date.parse(state.session.expiresAt) - Date.now()) / 1000)));
    update();
    const timer = setInterval(update, 1000);
    return () => clearInterval(timer);
  }, [state.phase, state.session?.expiresAt]);

  useEffect(() => {
    if (!open) return undefined;
    const onKeyDown = (event) => { if (event.key === "Escape" && state.phase !== "confirming") onClose(); };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open, onClose, state.phase]);

  const selectedSchool = state.schools.find(({ id }) => id === state.selection.schoolId);
  const selectedLocation = state.locations.find(({ id }) => id === state.selection.locationId);
  const step = stepNumber(state.phase);

  const selectLocationType = async (locationType) => {
    dispatch({ type: "SELECT_LOCATION_TYPE", locationType });
    try {
      const locations = await api.listBindingLocations(state.session.id, {
        schoolId: state.selection.schoolId,
        locationType,
      });
      dispatch({ type: "LOCATIONS_LOADED", locations });
    } catch (error) {
      fail(dispatch, error);
    }
  };

  const confirm = async () => {
    dispatch({ type: "CONFIRMING" });
    try {
      const binding = await api.confirmBinding(state.session.id, {
        schoolId: state.selection.schoolId,
        locationType: state.selection.locationType,
        locationId: state.selection.locationId,
      });
      dispatch({ type: "CONFIRMED", binding });
      onBound(binding);
      window.setTimeout(onClose, 650);
    } catch (error) {
      fail(dispatch, error);
    }
  };

  const simulateScan = async () => {
    try {
      await api.simulateBindingScan(state.session.id);
    } catch (error) {
      fail(dispatch, error);
    }
  };

  const approveRebind = () => {
    setRebindApproved(true);
    dispatch({ type: "OPEN" });
  };

  if (!open) return null;

  return (
    <div className="modal-backdrop binding-backdrop" role="presentation">
      <section className="binding-modal" role="dialog" aria-modal="true" aria-labelledby="binding-title" data-testid="binding-wizard">
        <header className="binding-modal-header">
          <div>
            <div className="binding-kicker"><Radio size={15} />设备配对台 {bindingServiceMode === "mock" ? <span className="mock-badge">模拟数据</span> : null}</div>
            <h2 id="binding-title">{isRebinding ? "重新绑定采集位置" : "绑定班级或录播室"}</h2>
          </div>
          <button className="icon-button" aria-label="关闭绑定向导" onClick={onClose} disabled={state.phase === "confirming"}><X size={22} /></button>
        </header>

        {isRebinding && !rebindApproved ? (
          <RebindConfirmation onCancel={onClose} onConfirm={approveRebind} />
        ) : (
          <div className="binding-workbench">
            <BindingIdentityPanel state={state} remainingSeconds={remainingSeconds} mode={bindingServiceMode} onSimulate={simulateScan} />
            <section className="binding-step-panel" data-binding-step={state.phase}>
              <div className="binding-step-track" aria-label={`绑定进度，第 ${step} 步，共 4 步`}>
                {[1, 2, 3, 4].map((index) => <span key={index} className={index <= step ? "active" : ""} />)}
              </div>
              <StepContent
                state={state}
                selectedSchool={selectedSchool}
                selectedLocation={selectedLocation}
                mode={bindingServiceMode}
                dispatch={dispatch}
                onSelectType={selectLocationType}
                onConfirm={confirm}
                onClose={onClose}
              />
            </section>
          </div>
        )}
      </section>
    </div>
  );
}

function BindingIdentityPanel({ state, remainingSeconds, mode, onSimulate }) {
  const qrVisible = state.session?.qrPayload && ["waiting", "scanned", "school", "locationType", "loadingLocations", "location", "review"].includes(state.phase);
  return (
    <aside className="binding-identity-panel">
      <div className="qr-frame">
        {qrVisible ? <QRCodeSVG value={state.session.qrPayload} size={190} level="M" marginSize={2} /> : <QrCode size={84} strokeWidth={1.3} />}
        <span className={`qr-signal ${state.phase === "waiting" ? "live" : ""}`} />
      </div>
      <div className="device-code"><span>本机设备</span><strong>{shortDevice(state.session?.deviceNo)}</strong></div>
      {state.phase === "waiting" ? <p className="qr-expiry">二维码有效期 {formatCountdown(remainingSeconds)}</p> : null}
      {canSimulateScan(mode) && state.phase === "waiting" ? (
        <button className="simulate-scan-button" onClick={onSimulate} data-testid="simulate-binding-scan"><Smartphone size={19} />模拟手机扫码</button>
      ) : null}
      <p className="binding-safety-note">绑定只会更新后续录音归属，历史音频和待上传记录保持原班级信息。</p>
    </aside>
  );
}

function StepContent({ state, selectedSchool, selectedLocation, mode, dispatch, onSelectType, onConfirm, onClose }) {
  if (["creating", "waiting"].includes(state.phase)) return <WaitingStep mode={mode} />;
  if (state.phase === "scanned") return <LoadingStep title="扫码成功" detail="正在读取可绑定的学校…" />;
  if (state.phase === "school") return <SchoolStep schools={state.schools} onSelect={(schoolId) => dispatch({ type: "SELECT_SCHOOL", schoolId })} />;
  if (state.phase === "locationType") return <LocationTypeStep school={selectedSchool} onBack={() => dispatch({ type: "BACK" })} onSelect={onSelectType} />;
  if (state.phase === "loadingLocations") return <LoadingStep title="正在同步位置" detail="准备班级和录播室清单…" />;
  if (state.phase === "location") return <LocationStep locations={state.locations} type={state.selection.locationType} onBack={() => dispatch({ type: "BACK" })} onSelect={(locationId) => dispatch({ type: "SELECT_LOCATION", locationId })} />;
  if (["review", "confirming"].includes(state.phase)) return <ReviewStep state={state} school={selectedSchool} location={selectedLocation} onBack={() => dispatch({ type: "BACK" })} onConfirm={onConfirm} />;
  if (state.phase === "expired") return <TerminalStep icon={<RotateCcw />} title="二维码已过期" detail="为保护设备绑定安全，请手动生成一个新二维码。" action="生成新二维码" onAction={() => dispatch({ type: "RESTART" })} />;
  if (state.phase === "confirmed") return <TerminalStep success icon={<CheckCircle2 />} title="绑定已生效" detail="录音 worker 已确认新位置，现在可以开始采集。" />;
  return <ErrorStep error={state.error} mode={mode} onRestart={() => dispatch({ type: "RESTART" })} onClose={onClose} />;
}

function WaitingStep({ mode }) {
  return <div className="binding-copy"><span className="step-label">第 1 步</span><h3>使用手机扫描设备码</h3><p>{mode === "mock" ? "这是内部流程演示。点击左侧“模拟手机扫码”，客户端仍会通过会话轮询进入下一步。" : "绑定服务尚未配置。正式版本接入服务后，将在这里显示可由手机扫描的设备码。"}</p><div className="waiting-wave"><i /><i /><i /><span>等待扫码</span></div></div>;
}

function SchoolStep({ schools, onSelect }) {
  return <div className="binding-copy"><span className="step-label">第 2 步</span><h3>选择设备所在学校</h3><p>模拟登录用户可访问以下学校。正式版本将由服务端返回授权范围。</p><div className="binding-choice-list">{schools.map((school) => <button key={school.id} onClick={() => onSelect(school.id)}><School /><span><strong>{school.name}</strong><small>学校编号 {school.id}</small></span><Check /></button>)}</div></div>;
}

function LocationTypeStep({ school, onBack, onSelect }) {
  return <div className="binding-copy"><BackButton onClick={onBack} /><span className="step-label">第 3 步 · {school?.name}</span><h3>这台设备安装在哪里？</h3><div className="location-type-grid"><button onClick={() => onSelect("classroom")}><Building2 /><strong>班级教室</strong><span>绑定已有班级和对应教室</span></button><button onClick={() => onSelect("studio")}><Radio /><strong>公共录播室</strong><span>不归属具体班级的采集位置</span></button></div></div>;
}

function LocationStep({ locations, type, onBack, onSelect }) {
  const title = type === "studio" ? "选择公共录播室" : "选择班级教室";
  return <div className="binding-copy"><BackButton onClick={onBack} /><span className="step-label">第 3 步</span><h3>{title}</h3><div className="binding-choice-list location-list">{locations.map((location) => <button key={location.id} onClick={() => onSelect(location.id)}><MapPin /><span><strong>{location.name}</strong><small>{location.className || "公共采集位置"}</small></span><Check /></button>)}</div>{locations.length === 0 ? <p className="empty-choice">当前没有可绑定位置。</p> : null}</div>;
}

function ReviewStep({ state, school, location, onBack, onConfirm }) {
  const busy = state.phase === "confirming";
  return <div className="binding-copy"><BackButton onClick={onBack} disabled={busy} /><span className="step-label">第 4 步</span><h3>确认设备归属</h3><dl className="binding-review"><div><dt>学校</dt><dd>{school?.name}</dd></div><div><dt>位置类型</dt><dd>{state.selection.locationType === "studio" ? "公共录播室" : "班级教室"}</dd></div><div><dt>目标位置</dt><dd>{location?.name}</dd></div>{location?.className ? <div><dt>班级</dt><dd>{location.className}</dd></div> : null}</dl><button className="binding-confirm-button" onClick={onConfirm} disabled={busy}>{busy ? <LoaderCircle className="spin" /> : <CheckCircle2 />}{busy ? "正在通知录音服务…" : "确认并应用绑定"}</button></div>;
}

function RebindConfirmation({ onCancel, onConfirm }) {
  return <div className="rebind-confirmation"><div className="rebind-orbit"><RotateCcw /></div><span className="step-label">变更提醒</span><h3>确认重新绑定这台设备？</h3><p>新绑定只影响后续录音。已经生成的音频和上传队列不会迁移到新班级。</p><div><button className="quiet-action" onClick={onCancel}>取消</button><button className="binding-confirm-button compact" onClick={onConfirm}>继续重新绑定</button></div></div>;
}

function LoadingStep({ title, detail }) { return <div className="binding-copy loading-step"><LoaderCircle className="spin" /><h3>{title}</h3><p>{detail}</p></div>; }
function TerminalStep({ icon, title, detail, action, onAction, success }) { return <div className={`binding-copy terminal-step ${success ? "success" : ""}`}><div>{icon}</div><h3>{title}</h3><p>{detail}</p>{action ? <button className="binding-confirm-button" onClick={onAction}>{action}</button> : null}</div>; }
function ErrorStep({ error, mode, onRestart, onClose }) { const unavailable = mode !== "mock" || error?.code === "BINDING_SERVICE_UNAVAILABLE"; return <div className="binding-copy terminal-step error"><div><X /></div><h3>{unavailable ? "绑定服务暂不可用" : "绑定没有完成"}</h3><p>{unavailable ? "正式绑定接口尚未接入。客户端不会自动切换到模拟数据。" : friendlyError(error)}</p><div className="terminal-actions"><button className="quiet-action" onClick={onClose}>关闭</button>{!unavailable ? <button className="binding-confirm-button compact" onClick={onRestart}>重新开始</button> : null}</div></div>; }
function BackButton(props) { return <button className="binding-back-button" {...props}><ArrowLeft size={17} />返回</button>; }

function fail(dispatch, error) { dispatch({ type: "ERROR", error: { code: error?.code || "", message: error?.message || String(error) } }); }
function friendlyError(error) { if (error?.code === "BINDING_SERVICE_UNAVAILABLE") return "正式绑定接口尚未接入。客户端不会自动切换到模拟数据。"; return error?.message || "请检查录音服务状态后重新尝试。"; }
function shortDevice(value) { const text = String(value || "正在识别…"); return text.length > 8 ? `${text.slice(0, 4)} · ${text.slice(-4)}` : text; }
function formatCountdown(seconds) { return `${String(Math.floor(seconds / 60)).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`; }
function stepNumber(phase) { if (["school", "scanned"].includes(phase)) return 2; if (["locationType", "loadingLocations", "location"].includes(phase)) return 3; if (["review", "confirming", "confirmed"].includes(phase)) return 4; return 1; }
