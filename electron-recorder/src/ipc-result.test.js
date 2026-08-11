import assert from "node:assert/strict";
import { createRequire } from "node:module";
import test from "node:test";

const require = createRequire(import.meta.url);
const { failureResult, unwrapResult } = require("./ipc-result.cjs");

test("structured IPC errors preserve business fields without Electron prefixes", () => {
  const source = Object.assign(new Error("设备已绑定其他的班级或者教室"), {
    code: "BINDING_REJECTED",
    businessCode: 7,
    operation: "bind",
    unbound: false,
  });
  const result = failureResult(source);

  assert.throws(() => unwrapResult(result), {
    code: "BINDING_REJECTED",
    businessCode: 7,
    operation: "bind",
    message: "设备已绑定其他的班级或者教室",
  });
});
