import React, { useEffect, useReducer, useState } from "react";
import {
  ArrowLeft,
  Building2,
  Check,
  CheckCircle2,
  LoaderCircle,
  Radio,
  RotateCcw,
  School,
  UserRound,
  X,
} from "lucide-react";

import { bindingFlowReducer, initialBindingFlow } from "./binding-flow.js";

const api = window.recorderShell;

export function BindingWizard({ open, isRebinding, bindingServiceMode, onClose, onBound }) {
  const [state, dispatch] = useReducer(bindingFlowReducer, initialBindingFlow);
  const [rebindApproved, setRebindApproved] = useState(false);
  const [replaceDevice, setReplaceDevice] = useState(false);

  useEffect(() => {
    if (!open) {
      setRebindApproved(false);
      setReplaceDevice(false);
      dispatch({ type: "CLOSE" });
      return;
    }
    if (!isRebinding) dispatch({ type: "OPEN" });
  }, [open, isRebinding]);

  useEffect(() => {
    if (!open || state.phase !== "creating") return undefined;
    let active = true;
    const createSession = replaceDevice
      ? api.createReplacementBindingSession
      : api.createBindingSession;
    createSession()
      .then((session) => active && dispatch({ type: "SESSION_UPDATED", session }))
      .catch((error) => active && fail(dispatch, error));
    return () => { active = false; };
  }, [open, replaceDevice, state.phase]);

  useEffect(() => {
    if (!open) return undefined;
    const onKeyDown = (event) => {
      if (event.key === "Escape" && state.phase !== "confirming") onClose();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open, onClose, state.phase]);

  const selectBindType = async (bindType) => {
    dispatch({ type: "SELECT_BIND_TYPE", bindType });
    if (bindType !== 1) return;
    try {
      const grades = await api.listBindingGrades(state.session.id);
      dispatch({ type: "GRADES_LOADED", grades });
    } catch (error) {
      fail(dispatch, error);
    }
  };

  const selectGrade = async (gradeCode) => {
    dispatch({ type: "SELECT_GRADE", gradeCode });
    try {
      const classes = await api.listBindingClasses(state.session.id, { gradeCode });
      dispatch({ type: "CLASSES_LOADED", classes });
    } catch (error) {
      fail(dispatch, error);
    }
  };

  const confirm = async () => {
    dispatch({ type: "CONFIRMING" });
    try {
      const binding = await api.confirmBinding(state.session.id, state.selection);
      dispatch({ type: "CONFIRMED", binding });
      onBound(binding);
      window.setTimeout(onClose, 650);
    } catch (error) {
      fail(dispatch, error);
    }
  };

  if (!open) return null;
  return (
    <div className="modal-backdrop binding-backdrop" role="presentation">
      <section className="binding-modal" role="dialog" aria-modal="true" aria-labelledby="binding-title" data-testid="binding-wizard">
        <header className="binding-modal-header">
          <div>
            <div className="binding-kicker"><Radio size={15} />设备绑定 {bindingServiceMode === "mock" ? <span className="mock-badge">模拟数据</span> : null}</div>
            <h2 id="binding-title">{isRebinding ? "重新绑定录音设备" : "绑定录音设备"}</h2>
          </div>
          <button className="icon-button" aria-label="关闭绑定向导" onClick={onClose} disabled={state.phase === "confirming"}><X size={22} /></button>
        </header>
        {isRebinding && !rebindApproved ? (
          <RebindConfirmation
            onCancel={onClose}
            onConfirm={() => {
              setRebindApproved(true);
              dispatch({ type: "OPEN" });
            }}
            onReplaceDevice={() => {
              setReplaceDevice(true);
              setRebindApproved(true);
              dispatch({ type: "OPEN" });
            }}
          />
        ) : (
          <div className="binding-workbench">
            <IdentityPanel state={state} mode={bindingServiceMode} />
            <section className="binding-step-panel" data-binding-step={state.phase}>
              <StepTrack phase={state.phase} />
              <StepContent
                state={state}
                mode={bindingServiceMode}
                dispatch={dispatch}
                onSelectType={selectBindType}
                onSelectGrade={selectGrade}
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

function IdentityPanel({ state, mode }) {
  const user = state.session?.user;
  return (
    <aside className="binding-identity-panel">
      <div className="qr-frame"><UserRound size={84} strokeWidth={1.3} /></div>
      <div className="device-code"><span>本机设备</span><strong>{shortDevice(state.session?.deviceNo)}</strong></div>
      {user ? (
        <div className="binding-review">
          <div><dt>当前学校</dt><dd>{user.schoolName}</dd></div>
          <div><dt>登录身份</dt><dd>{user.userName}</dd></div>
        </div>
      ) : <p>{mode === "mock" ? "正在载入模拟登录身份…" : "请在弹出的 Passport 窗口完成登录和身份选择。"}</p>}
      <p className="binding-safety-note">重新绑定只影响上传时的设备归属；本机设备编号仍使用已选定的物理网卡 MAC。</p>
    </aside>
  );
}

function StepTrack({ phase }) {
  const step = stepNumber(phase);
  return (
    <div className="binding-step-track" aria-label={`绑定进度，第 ${step} 步，共 4 步`}>
      {[1, 2, 3, 4].map((index) => <span key={index} className={index <= step ? "active" : ""} />)}
    </div>
  );
}

function StepContent({ state, mode, dispatch, onSelectType, onSelectGrade, onConfirm, onClose }) {
  if (state.phase === "creating") {
    return <LoadingStep title={mode === "mock" ? "正在准备模拟身份" : "等待 Passport 登录"} detail={mode === "mock" ? "正在载入学校身份…" : "请在弹出的窗口登录，并选择本次要使用的学校身份。"} />;
  }
  if (state.phase === "bindingType") return <BindingTypeStep user={state.session?.user} onSelect={onSelectType} />;
  if (state.phase === "loadingGrades") return <LoadingStep title="正在获取年级" detail="从当前学校读取可用年级列表…" />;
  if (state.phase === "grade") return <GradeStep grades={state.grades} onBack={() => dispatch({ type: "BACK" })} onSelect={onSelectGrade} />;
  if (state.phase === "loadingClasses") return <LoadingStep title="正在获取班级" detail="从所选年级读取班级列表…" />;
  if (state.phase === "class") return <ClassStep classes={state.classes} onBack={() => dispatch({ type: "BACK" })} onSelect={(classId) => dispatch({ type: "SELECT_CLASS", classId })} />;
  if (state.phase === "publicClassroom") return <PublicClassroomStep onBack={() => dispatch({ type: "BACK" })} onContinue={(classroom) => dispatch({ type: "REVIEW_PUBLIC", classroom })} />;
  if (["review", "confirming"].includes(state.phase)) return <ReviewStep state={state} onBack={() => dispatch({ type: "BACK" })} onConfirm={onConfirm} />;
  if (state.phase === "confirmed") return <TerminalStep success icon={<CheckCircle2 />} title="绑定已生效" detail="录音服务已应用新的设备归属。" />;
  return <ErrorStep error={state.error} onRestart={() => dispatch({ type: "RESTART" })} onClose={onClose} />;
}

function BindingTypeStep({ user, onSelect }) {
  return <div className="binding-copy"><span className="step-label">第 2 步 · {user?.schoolName}</span><h3>创建哪种教室？</h3><p>当前身份：{user?.userName}</p><div className="location-type-grid"><button onClick={() => onSelect(1)}><Building2 /><strong>班级教室</strong><span>从年级和班级列表中选择</span></button><button onClick={() => onSelect(2)}><Radio /><strong>公共教室</strong><span>输入一个便于识别的教室名称</span></button></div></div>;
}

function GradeStep({ grades, onBack, onSelect }) {
  return <div className="binding-copy"><BackButton onClick={onBack} /><span className="step-label">第 3 步</span><h3>选择年级</h3><ChoiceList items={grades} itemKey="gradeCode" titleKey="gradeName" onSelect={onSelect} empty="当前学校没有可用年级。" /></div>;
}

function ClassStep({ classes, onBack, onSelect }) {
  return <div className="binding-copy"><BackButton onClick={onBack} /><span className="step-label">第 3 步</span><h3>选择班级</h3><ChoiceList items={classes} itemKey="classId" titleKey="className" onSelect={onSelect} empty="当前年级没有可用班级。" /></div>;
}

function ChoiceList({ items, itemKey, titleKey, onSelect, empty }) {
  return <div className="binding-choice-list">{items.map((item) => <button key={item[itemKey]} onClick={() => onSelect(item[itemKey])}><School /><span><strong>{item[titleKey]}</strong></span><Check /></button>)}{items.length === 0 ? <p className="empty-choice">{empty}</p> : null}</div>;
}

function PublicClassroomStep({ onBack, onContinue }) {
  const [value, setValue] = useState("");
  const normalized = value.trim();
  return <div className="binding-copy"><BackButton onClick={onBack} /><span className="step-label">第 3 步</span><h3>填写公共教室名称</h3><p>例如：多媒体教室录音设备。这里仅保存并上传名称，不创建额外的位置编号。</p><label className="settings-field"><span>教室名称</span><input value={value} maxLength={256} autoFocus onChange={(event) => setValue(event.target.value)} placeholder="多媒体教室录音设备" /></label><button className="binding-confirm-button" disabled={!normalized} onClick={() => onContinue(normalized)}>继续确认</button></div>;
}

function ReviewStep({ state, onBack, onConfirm }) {
  const busy = state.phase === "confirming";
  const classroom = state.selection.bindType === 1 ? `${state.selection.className}录音设备` : state.selection.classroom;
  return <div className="binding-copy"><BackButton onClick={onBack} disabled={busy} /><span className="step-label">第 4 步</span><h3>确认设备归属</h3><dl className="binding-review"><div><dt>学校</dt><dd>{state.session?.user?.schoolName}</dd></div><div><dt>教室类型</dt><dd>{state.selection.bindType === 1 ? "班级教室" : "公共教室"}</dd></div><div><dt>教室名称</dt><dd>{classroom}</dd></div>{state.selection.className ? <div><dt>班级</dt><dd>{state.selection.className}</dd></div> : null}</dl><button className="binding-confirm-button" onClick={onConfirm} disabled={busy}>{busy ? <LoaderCircle className="spin" /> : <CheckCircle2 />}{busy ? "正在绑定…" : "确认并应用绑定"}</button></div>;
}

function RebindConfirmation({ onCancel, onConfirm, onReplaceDevice }) {
  return <div className="rebind-confirmation"><div className="rebind-orbit"><RotateCcw /></div><span className="step-label">变更提醒</span><h3>确认重新绑定这台设备？</h3><p>普通重绑继续使用已保存的物理网卡 MAC。只有身份网卡确已更换时，才按当前网卡创建新设备。</p><div><button className="quiet-action" onClick={onCancel}>取消</button><button className="quiet-action" onClick={onReplaceDevice}>网卡已更换</button><button className="binding-confirm-button compact" onClick={onConfirm}>继续重新绑定</button></div></div>;
}

function LoadingStep({ title, detail }) { return <div className="binding-copy loading-step"><LoaderCircle className="spin" /><h3>{title}</h3><p>{detail}</p></div>; }
function TerminalStep({ icon, title, detail, success }) { return <div className={`binding-copy terminal-step ${success ? "success" : ""}`}><div>{icon}</div><h3>{title}</h3><p>{detail}</p></div>; }
function ErrorStep({ error, onRestart, onClose }) { return <div className="binding-copy terminal-step error"><div><X /></div><h3>绑定没有完成</h3><p>{friendlyError(error)}</p><div className="terminal-actions"><button className="quiet-action" onClick={onClose}>关闭</button><button className="binding-confirm-button compact" onClick={onRestart}>重新开始</button></div></div>; }
function BackButton(props) { return <button className="binding-back-button" {...props}><ArrowLeft size={17} />返回</button>; }
function fail(dispatch, error) { dispatch({ type: "ERROR", error: { code: error?.code || "", message: error?.message || String(error) } }); }
function friendlyError(error) { if (error?.code === "PASSPORT_LOGIN_CANCELLED") return "Passport 登录窗口已关闭，请重新开始。"; return error?.message || "请检查网络和录音服务状态后重试。"; }
function shortDevice(value) { const text = String(value || "正在识别…"); return text.length > 8 ? `${text.slice(0, 4)} · ${text.slice(-4)}` : text; }
function stepNumber(phase) { if (phase === "creating") return 1; if (phase === "bindingType") return 2; if (["loadingGrades", "grade", "loadingClasses", "class", "publicClassroom"].includes(phase)) return 3; return 4; }
