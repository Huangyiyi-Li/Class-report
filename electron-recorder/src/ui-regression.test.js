import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const root = path.dirname(fileURLToPath(import.meta.url));
const wizard = readFileSync(path.join(root, "binding-wizard.jsx"), "utf8");
const renderer = readFileSync(path.join(root, "renderer.jsx"), "utf8");
const styles = readFileSync(path.join(root, "styles.css"), "utf8");
const main = readFileSync(path.join(root, "main.js"), "utf8");

test("public classroom name uses a dedicated accessible field and specific action", () => {
  assert.match(wizard, /className="binding-field"/);
  assert.match(wizard, /id="public-classroom-name"/);
  assert.match(wizard, /htmlFor="public-classroom-name"/);
  assert.match(wizard, /下一步：确认归属/);
  assert.match(styles, /\.binding-field input\s*\{/);
});

test("binding wizard uses one focused task column without the decorative device workbench", () => {
  assert.match(wizard, /className="binding-context-bar"/);
  assert.match(wizard, /登录[\s\S]*选择类型[\s\S]*选择教室[\s\S]*确认绑定/);
  assert.match(styles, /\.binding-modal\s*\{[^}]*width:\s*720px/s);
  assert.match(styles, /\.binding-workbench\s*\{[^}]*display:\s*block/s);
  assert.doesNotMatch(wizard, /className="binding-identity-panel"/);
  assert.doesNotMatch(wizard, /className="qr-frame"/);
  assert.doesNotMatch(styles, /PAIR \/ 01/);
  assert.doesNotMatch(wizard, /创建哪种教室/);
});

test("packaged smoke checks authenticated binding context after the binding step is ready", () => {
  assert.match(
    main,
    /const bindingTypeStep = await waitFor\('\[data-binding-step="bindingType"\]'\);[\s\S]*const contextBar = wizard\?\.querySelector\('\.binding-context-bar'\);/
  );
});

test("settings use a single readable flow and preserve compact window rules", () => {
  assert.match(styles, /\.settings-flow\s*\{[^}]*display:\s*block/s);
  assert.match(
    styles,
    /@media \(max-width:\s*1024px\),\s*\(max-height:\s*680px\)/s
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

test("recording home shows elapsed time without exposing segment counters", () => {
  assert.match(renderer, /recording-elapsed/);
  assert.match(renderer, /recordingStartedAt/);
  assert.doesNotMatch(renderer, /recordingSegments/);
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

test("approved home and settings hierarchy keeps actions while hiding technical noise", () => {
  assert.match(renderer, /className="desktop-location"/);
  assert.match(renderer, /title: "正在录音"/);
  assert.match(renderer, /暂停录音/);
  assert.match(renderer, /停止录音/);
  assert.match(renderer, /立即重试/);
  assert.match(renderer, />当前设备</);
  assert.match(renderer, />录音</);
  assert.match(renderer, />软件</);
  assert.match(renderer, />高级设置</);
  assert.match(renderer, />设备管理</);
  assert.match(renderer, /显示录音悬浮窗/);
  assert.doesNotMatch(renderer, /运行设置与诊断/);
  assert.doesNotMatch(renderer, /采集服务正在持续写入本地文件/);
  assert.doesNotMatch(renderer, /音频会先安全写入本地/);
  assert.doesNotMatch(renderer, /最近录音分段处理记录/);
});
