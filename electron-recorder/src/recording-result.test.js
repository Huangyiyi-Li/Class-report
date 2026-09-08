import assert from "node:assert/strict";
import test from "node:test";
const { recordingResult } = await import("./recording-result.js").catch(
  () => ({})
);
test("only a stopped run with all segments registered is complete", () => {
  assert.equal(typeof recordingResult, "function");
  const run = {
    endedAt: "2026-09-08T03:00:00Z",
    segments: 25,
    expected: 25,
    completed: 0,
    saved: 25,
    counts: { uploaded: 25 },
  };
  assert.equal(recordingResult(run).complete, false);
  assert.equal(recordingResult({ ...run, completed: 25 }).complete, true);
  assert.equal(
    recordingResult({ ...run, completed: 25, endedAt: null }).complete,
    false
  );
});
test("empty, missing or interrupted recordings cannot claim full success", () => {
  assert.equal(typeof recordingResult, "function");
  assert.equal(
    recordingResult({ segments: 0, completed: 0, endedAt: "x" }).complete,
    false
  );
  const run = {
    segments: 1,
    expected: 2,
    completed: 1,
    saved: 1,
    endedAt: "x",
  };
  assert.equal(recordingResult(run).complete, false);
  assert.equal(
    recordingResult({ ...run, expected: 1, interrupted: true }).complete,
    false
  );
  assert.match(
    recordingResult({ ...run, expected: 1, completed: 0, saved: 0 }).local,
    /缺失/
  );
});

test("an active segment awaiting finalization is not an interruption", () => {
  const result = recordingResult({
    endedAt: null,
    expected: 2,
    segments: 1,
    saved: 1,
    completed: 1,
  });
  assert.equal(result.warning, "");
  assert.equal(result.complete, false);
});
