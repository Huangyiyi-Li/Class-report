import assert from "node:assert/strict";
import { mkdtempSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import test from "node:test";

import { redactDiagnostics, writeDiagnosticFile } from "./diagnostics.js";
import * as diagnosticTools from "./diagnostics.js";

test("redacts sensitive fields recursively without mutating the source", () => {
  const source = {
    password: "top-level",
    nested: {
      apiToken: "token-value",
      client_secret: "secret-value",
      Authorization: "Bearer abc",
      controlToken: "control-value",
      safe: "visible",
    },
    rows: [{ access_token: "row-token", count: 2 }],
  };

  assert.deepEqual(redactDiagnostics(source), {
    password: "[REDACTED]",
    nested: {
      apiToken: "[REDACTED]",
      client_secret: "[REDACTED]",
      Authorization: "[REDACTED]",
      controlToken: "[REDACTED]",
      safe: "visible",
    },
    rows: [{ access_token: "[REDACTED]", count: 2 }],
  });
  assert.equal(source.nested.apiToken, "token-value");
});

test("writes a redacted diagnostic JSON file", () => {
  const filePath = path.join(
    mkdtempSync(path.join(tmpdir(), "recorder-diagnostics-")),
    "diagnostics.json"
  );
  writeDiagnosticFile(filePath, { token: "hidden", status: "healthy" });
  assert.deepEqual(JSON.parse(readFileSync(filePath, "utf8")), {
    token: "[REDACTED]",
    status: "healthy",
  });
});

test("keeps the OSS route visible while redacting actual access tokens", () => {
  const source = {
    settings: {
      apiRoutes: {
        ossToken: "https://rest-test.xxt.cn/wisdom/ali-oss/get-ali-oss-token",
      },
    },
    accessToken: "device-token",
  };

  assert.deepEqual(redactDiagnostics(source), {
    settings: {
      apiRoutes: {
        ossToken: "https://rest-test.xxt.cn/wisdom/ali-oss/get-ali-oss-token",
      },
    },
    accessToken: "[REDACTED]",
  });
});

test("binding failure tracker keeps a safe actionable diagnostic summary", () => {
  assert.equal(typeof diagnosticTools.createBindingFailureTracker, "function");
  if (typeof diagnosticTools.createBindingFailureTracker !== "function") return;
  const tracker = diagnosticTools.createBindingFailureTracker({
    now: () => new Date("2026-09-03T09:00:00.000Z"),
  });
  tracker.capture("confirm", {
    code: "BINDING_REJECTED",
    message: "设备绑定请求被拒绝",
    businessCode: 12,
    operation: "bind",
    stack: "must not be exported",
    authorization: "must not be exported",
  });

  assert.deepEqual(tracker.latest(), {
    occurredAt: "2026-09-03T09:00:00.000Z",
    stage: "confirm",
    problemCode: "BIND-12",
    code: "BINDING_REJECTED",
    businessCode: 12,
    operation: "bind",
    message: "设备绑定请求被拒绝",
  });
});

test("binding failure tracker does not invent a zero business code", () => {
  const tracker = diagnosticTools.createBindingFailureTracker();
  tracker.capture("confirm", {
    code: "BINDING_REJECTED",
    businessCode: null,
    operation: "bind",
    message: "网关没有返回业务码",
  });

  assert.equal(tracker.latest().businessCode, null);
  assert.equal(tracker.latest().problemCode, "BIND-C10");
});

test("main process records binding failures in exported diagnostics", () => {
  const mainSource = readFileSync(
    new URL("./main.js", import.meta.url),
    "utf8"
  );
  assert.match(mainSource, /bindingFailureTracker\.capture/u);
  assert.match(
    mainSource,
    /latestBindingError:\s*bindingFailureTracker\.latest\(\)/u
  );
});
