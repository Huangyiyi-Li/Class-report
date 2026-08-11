import assert from "node:assert/strict";
import test from "node:test";

import { bindingErrorView } from "./binding-error-view.js";

test("binding technical errors show a photo-ready device number and problem code", () => {
  assert.deepEqual(
    bindingErrorView(
      { operation: "bind", businessCode: 4 },
      { deviceNo: "AABBCCDDEEFF-9001" }
    ),
    {
      title: "设备编号已被使用",
      detail: "当前设备编号与系统中的已有记录冲突，暂时无法完成绑定。",
      guidance: "请将本页面拍照并联系技术人员处理。",
      primary: "close",
      deviceNo: "AABBCCDDEEFF-9001",
      problemCode: "BIND-04",
    }
  );
});

test("binding code 7 offers reselect and replacement for the chosen target", () => {
  const view = bindingErrorView(
    { operation: "bind", businessCode: 7 },
    { deviceNo: "AABBCCDDEEFF-9001", className: "二年级 3 班" }
  );
  assert.equal(view.title, "设备已绑定其他班级或教室");
  assert.match(view.detail, /二年级 3 班/);
  assert.equal(view.primary, "replace");
  assert.equal(view.secondary, "reselect");
});

test("partial replacement failure explains that the original binding is gone", () => {
  const view = bindingErrorView({
    operation: "bind",
    businessCode: 5,
    unbound: true,
  });

  assert.equal(view.title, "原绑定已解除，新绑定未完成");
  assert.equal(view.primary, "replace");
  assert.equal(view.secondary, "reselect");
});

test("unbind code 3 directs the user to the device school", () => {
  const view = bindingErrorView(
    { operation: "unbind", businessCode: 3 },
    {
      deviceNo: "AABBCCDDEEFF-9001",
      boundSchoolName: "星河实验学校",
      currentSchoolName: "育才实验学校",
    }
  );
  assert.equal(view.title, "当前账号不能解绑此设备");
  assert.equal(view.primary, "switch_identity");
  assert.match(view.detail, /星河实验学校/);
});
