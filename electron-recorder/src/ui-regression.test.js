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
  assert.match(renderer, /<select[\s\S]*?<\/select>/);
  assert.match(renderer, /系统默认麦克风/);
  assert.match(renderer, /listInputDevices/);
  assert.match(renderer, />录音保存位置</);
  assert.match(renderer, /chooseDataRoot/);
  assert.match(renderer, /选择文件夹/);
  assert.match(renderer, /打开文件夹/);
  assert.match(renderer, /保存位置已固定，避免影响现有录音和待上传文件/);
  assert.doesNotMatch(renderer, />麦克风设备 ID</);
});

test("preload and main process expose bounded device and directory pickers", () => {
  const preload = readFileSync(path.join(root, "preload.cjs"), "utf8");
  const main = readFileSync(path.join(root, "main.js"), "utf8");
  assert.match(preload, /listInputDevices/);
  assert.match(preload, /chooseDataRoot/);
  assert.match(main, /recorder:list-input-devices/);
  assert.match(main, /recorder:choose-data-root/);
  assert.match(main, /showOpenDialog/);
  assert.match(main, /openDirectory/);
});

test("rebind is exposed only as unbind followed by a fresh binding flow", () => {
  assert.match(renderer, /解绑并重新绑定/);
  assert.doesNotMatch(renderer, /绑定其他班级/);
  assert.doesNotMatch(wizard, /继续重新绑定/);
  assert.doesNotMatch(wizard, /isRebinding/);
});

test("recording and upload actions expose progress instead of failing silently", () => {
  assert.match(renderer, /runRecorderAction/);
  assert.match(renderer, /正在启动…/);
  assert.match(renderer, /正在重试…/);
  assert.match(renderer, /actionError/);
});

test("settings distinguish missing local files from retryable uploads", () => {
  assert.match(renderer, /本地文件已缺失/);
  assert.match(renderer, /snapshot\.localMissing/);
});

test("recording home shows elapsed time and completed local segments", () => {
  assert.match(renderer, /录音时长/);
  assert.match(renderer, /recordingStartedAt/);
  assert.match(renderer, /recordingSegments/);
});

test("upload diagnostics explain auth credentials cloud upload and registration", () => {
  assert.match(renderer, /设备认证/);
  assert.match(renderer, /上传凭证/);
  assert.match(renderer, /OSS/);
  assert.match(renderer, /等待登记/);
  assert.match(renderer, /queueDiagnostics/);
  assert.match(renderer, /uploadDiagnostics/);
  assert.match(renderer, /retryAt/);
  assert.match(renderer, /latestUploadError/);
});
