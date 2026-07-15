import assert from "node:assert/strict";
import test from "node:test";

import { getUploadMeta } from "./state.js";

test("mock binding upload state explicitly says audio stays local", () => {
  assert.deepEqual(getUploadMeta("mock_blocked"), {
    label: "模拟模式，仅保存本地",
    tone: "mock",
  });
});
