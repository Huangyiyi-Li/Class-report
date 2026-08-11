import assert from "node:assert/strict";
import test from "node:test";

import { authIssueView } from "./auth-issue-view.js";

test("clock mismatch offers automatic calibration before manual settings", () => {
  const view = authIssueView({ reason: "clock_invalid" });
  assert.equal(view.primary, "calibrate_clock");
  assert.equal(view.secondary, "open_clock_settings");
  assert.match(view.notice, /北京时间/);
});

test("signature failure gives a photo-ready support reference", () => {
  const view = authIssueView(
    { reason: "signature_invalid" },
    { deviceNo: "AABBCCDDEEFF-9001" }
  );
  assert.equal(view.primary, "recheck_auth");
  assert.equal(view.problemCode, "AUTH-03");
  assert.equal(view.deviceNo, "AABBCCDDEEFF-9001");
  assert.doesNotMatch(view.notice, /Error|signature/i);
});

test("missing class directs the teacher to select a new classroom", () => {
  const view = authIssueView({
    reason: "class_not_found",
    rebindRequired: true,
  });
  assert.equal(view.primary, "bind");
  assert.equal(view.primaryLabel, "重新选择班级或教室");
});
