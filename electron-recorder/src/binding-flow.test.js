import assert from "node:assert/strict";
import test from "node:test";

import {
  beginFullRebinding,
  bindingFlowReducer,
  canRebind,
  initialBindingFlow,
} from "./binding-flow.js";

const session = {
  id: "session-1",
  status: "authenticated",
  deviceNo: "AABBCCDDEEFF",
  user: {
    schoolId: 1001,
    schoolName: "星河实验学校",
    userName: "黄老师",
    userType: 0,
  },
};

test("authenticated Passport session advances directly to binding type", () => {
  let state = bindingFlowReducer(initialBindingFlow, { type: "OPEN" });
  assert.equal(state.phase, "creating");
  state = bindingFlowReducer(state, { type: "SESSION_UPDATED", session });
  assert.equal(state.phase, "bindingType");
  assert.equal(state.session.user.schoolName, "星河实验学校");
});

test("classroom flow loads grades and classes before review", () => {
  let state = { ...initialBindingFlow, phase: "bindingType", session };
  state = bindingFlowReducer(state, { type: "SELECT_BIND_TYPE", bindType: 1 });
  assert.equal(state.phase, "loadingGrades");
  state = bindingFlowReducer(state, {
    type: "GRADES_LOADED",
    grades: [{ gradeCode: 1, gradeName: "一年级" }],
  });
  assert.equal(state.phase, "grade");
  state = bindingFlowReducer(state, { type: "SELECT_GRADE", gradeCode: 1 });
  assert.equal(state.phase, "loadingClasses");
  state = bindingFlowReducer(state, {
    type: "CLASSES_LOADED",
    classes: [{ classId: 101, className: "1.1班" }],
  });
  state = bindingFlowReducer(state, { type: "SELECT_CLASS", classId: 101 });
  assert.equal(state.phase, "review");
  assert.deepEqual(state.selection, {
    bindType: 1,
    gradeCode: 1,
    classId: 101,
    className: "1.1班",
  });
});

test("public classroom flow requires a trimmed name", () => {
  let state = { ...initialBindingFlow, phase: "bindingType", session };
  state = bindingFlowReducer(state, { type: "SELECT_BIND_TYPE", bindType: 2 });
  assert.equal(state.phase, "publicClassroom");
  state = bindingFlowReducer(state, {
    type: "REVIEW_PUBLIC",
    classroom: "  多媒体教室录音设备  ",
  });
  assert.equal(state.phase, "review");
  assert.deepEqual(state.selection, {
    bindType: 2,
    classroom: "多媒体教室录音设备",
  });
});

test("back navigation does not retain stale class or public data", () => {
  const classBack = bindingFlowReducer(
    {
      ...initialBindingFlow,
      phase: "grade",
      selection: { bindType: 1 },
    },
    { type: "BACK" }
  );
  assert.equal(classBack.phase, "bindingType");
  assert.deepEqual(classBack.selection, {});

  const publicBack = bindingFlowReducer(
    {
      ...initialBindingFlow,
      phase: "review",
      selection: { bindType: 2, classroom: "多媒体教室录音设备" },
    },
    { type: "BACK" }
  );
  assert.equal(publicBack.phase, "publicClassroom");
});

test("confirmed binding is retained until the wizard closes", () => {
  const confirmed = bindingFlowReducer(
    { ...initialBindingFlow, phase: "confirming" },
    {
      type: "CONFIRMED",
      binding: { bindType: 1, classroom: "1.1班录音设备" },
    }
  );
  assert.equal(confirmed.phase, "confirmed");
  assert.equal(confirmed.binding.classroom, "1.1班录音设备");
  assert.deepEqual(
    bindingFlowReducer(confirmed, { type: "CLOSE" }),
    initialBindingFlow
  );
});

test("rebind is available only when the recorder is idle", () => {
  assert.equal(canRebind({ recording: "idle" }), true);
  assert.equal(canRebind({ recordingState: "recording" }), false);
  assert.equal(canRebind({ runtime: { recording: "paused" } }), false);
});

test("full rebind unbinds first and opens a fresh login binding flow", async () => {
  const calls = [];
  const started = await beginFullRebinding({
    confirm: () => true,
    unbindDevice: async () => calls.push("unbind"),
    openBinding: () => calls.push("open"),
  });

  assert.equal(started, true);
  assert.deepEqual(calls, ["unbind", "open"]);
});

test("full rebind neither unbinds nor opens when the user cancels", async () => {
  const calls = [];
  const started = await beginFullRebinding({
    confirm: () => false,
    unbindDevice: async () => calls.push("unbind"),
    openBinding: () => calls.push("open"),
  });

  assert.equal(started, false);
  assert.deepEqual(calls, []);
});

test("full rebind does not open binding when server unbind fails", async () => {
  const calls = [];
  await assert.rejects(
    beginFullRebinding({
      confirm: () => true,
      unbindDevice: async () => {
        calls.push("unbind");
        throw new Error("解绑失败");
      },
      openBinding: () => calls.push("open"),
    }),
    /解绑失败/
  );
  assert.deepEqual(calls, ["unbind"]);
});
