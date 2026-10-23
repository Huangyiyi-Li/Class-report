import assert from "node:assert/strict";
import test from "node:test";
import { createRecordingFeedback } from "./recording-feedback.js";

test("normal recording announces start once; upload/network changes stay quiet", () => {
  const feedback = createRecordingFeedback();
  assert.equal(feedback({ recording: "idle", health: "healthy" }), null);
  assert.equal(
    feedback({ recording: "recording", health: "healthy" }).title,
    "已开始录音"
  );
  assert.equal(
    feedback({
      recording: "recording",
      health: "healthy",
      upload: "waiting_network",
    }),
    null
  );
  assert.equal(
    feedback({ recording: "recording", health: "healthy", upload: "failed" }),
    null
  );
});

test("capture interruption alerts once and resets after recovery", () => {
  const feedback = createRecordingFeedback();
  feedback({ recording: "recording", health: "healthy" });
  const failed = { recording: "error", health: "microphone_unavailable" };
  assert.equal(feedback(failed).title, "录音已中断");
  assert.equal(feedback(failed), null);
  assert.equal(feedback({ ...failed, pending: 3 }), null);
  assert.equal(
    feedback({ recording: "recording", health: "healthy" }).title,
    "录音已恢复"
  );
  assert.equal(feedback(failed).title, "录音已中断");
});

test("pause is explicit, initialization is quiet, initial actionable faults are reported", () => {
  const feedback = createRecordingFeedback();
  assert.equal(
    feedback({ health: "blocked", latestError: "正在启动录音服务" }),
    null
  );
  assert.equal(feedback({ health: "binding_required" }).title, "尚未开始录音");
  feedback({ recording: "recording", health: "healthy" });
  assert.equal(
    feedback({ recording: "paused", health: "healthy" }).title,
    "录音已暂停"
  );
  assert.equal(feedback({ recording: "paused", health: "healthy" }), null);
});
