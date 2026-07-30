import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const root = path.dirname(fileURLToPath(import.meta.url));
const wizard = readFileSync(path.join(root, "binding-wizard.jsx"), "utf8");
const renderer = readFileSync(path.join(root, "renderer.jsx"), "utf8");
const styles = readFileSync(path.join(root, "styles.css"), "utf8");

test("public classroom name uses a dedicated accessible field and specific action", () => {
  assert.match(wizard, /className="binding-field"/);
  assert.match(wizard, /id="public-classroom-name"/);
  assert.match(wizard, /htmlFor="public-classroom-name"/);
  assert.match(wizard, /下一步：确认归属/);
  assert.match(styles, /\.binding-field input\s*\{/);
});

test("settings diagnostics preserve readable columns and stack on compact windows", () => {
  assert.match(
    styles,
    /\.setting-row\s*\{[^}]*grid-template-columns:\s*minmax\(0,\s*1fr\)\s+auto/s
  );
  assert.match(
    styles,
    /@media \(max-width:\s*760px\)[\s\S]*?\.settings-grid\s*\{\s*grid-template-columns:\s*1fr/s
  );
});

test("settings labels describe user-facing choices instead of implementation fields", () => {
  assert.match(renderer, />麦克风设备</);
  assert.match(renderer, />录音保存位置</);
  assert.match(renderer, /保存位置已固定，避免影响现有录音和待上传文件/);
  assert.doesNotMatch(renderer, />麦克风设备 ID</);
});

test("rebind is exposed only as unbind followed by a fresh binding flow", () => {
  assert.match(renderer, /解绑并重新绑定/);
  assert.doesNotMatch(renderer, /绑定其他班级/);
  assert.doesNotMatch(wizard, /继续重新绑定/);
  assert.doesNotMatch(wizard, /isRebinding/);
});
