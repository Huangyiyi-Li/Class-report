import assert from "node:assert/strict";
import { mkdtempSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import test from "node:test";

import { redactDiagnostics, writeDiagnosticFile } from "./diagnostics.js";

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
  const filePath = path.join(mkdtempSync(path.join(tmpdir(), "recorder-diagnostics-")), "diagnostics.json");
  writeDiagnosticFile(filePath, { token: "hidden", status: "healthy" });
  assert.deepEqual(JSON.parse(readFileSync(filePath, "utf8")), {
    token: "[REDACTED]",
    status: "healthy",
  });
});
