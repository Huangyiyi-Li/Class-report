import fs from "node:fs";
import path from "node:path";

const options = parseArgs(process.argv.slice(2));
const endpoint = options.endpoint || "http://127.0.0.1:9333";
const outputDir = path.resolve(options.output || "output/playwright/packaged-binding");
fs.mkdirSync(outputDir, { recursive: true });

const target = await waitForTarget(endpoint);
const socket = new WebSocket(target.webSocketDebuggerUrl);
await new Promise((resolve, reject) => {
  socket.addEventListener("open", resolve, { once: true });
  socket.addEventListener("error", reject, { once: true });
});

let nextId = 1;
const pending = new Map();
socket.addEventListener("message", (event) => {
  const message = JSON.parse(event.data);
  if (!message.id || !pending.has(message.id)) return;
  const { resolve, reject } = pending.get(message.id);
  pending.delete(message.id);
  if (message.error) reject(new Error(message.error.message));
  else resolve(message.result);
});

function command(method, params = {}) {
  const id = nextId++;
  return new Promise((resolve, reject) => {
    pending.set(id, { resolve, reject });
    socket.send(JSON.stringify({ id, method, params }));
  });
}

async function evaluate(expression) {
  const result = await command("Runtime.evaluate", {
    expression,
    awaitPromise: true,
    returnByValue: true,
    userGesture: true,
  });
  if (result.exceptionDetails) {
    throw new Error(result.exceptionDetails.exception?.description || result.exceptionDetails.text);
  }
  return result.result.value;
}

async function waitFor(expression, label, timeoutMs = 30_000) {
  const started = Date.now();
  while (Date.now() - started < timeoutMs) {
    if (await evaluate(`(async () => Boolean(await (${expression})))()`)) return;
    await delay(150);
  }
  throw new Error(`timed out waiting for ${label}`);
}

async function screenshot(name) {
  const result = await command("Page.captureScreenshot", { format: "png", captureBeyondViewport: false });
  fs.writeFileSync(path.join(outputDir, name), Buffer.from(result.data, "base64"));
}

async function click(selector, label) {
  const clicked = await evaluate(`(() => { const node = document.querySelector(${JSON.stringify(selector)}); if (!node) return false; node.click(); return true; })()`);
  if (!clicked) throw new Error(`missing ${label}: ${selector}`);
}

async function snapshot() {
  return evaluate("window.recorderShell.getSnapshot()");
}

await command("Runtime.enable");
await command("Page.enable");
await waitFor("document.querySelector('[data-testid=\"open-binding\"]')", "binding entry");

const initial = await snapshot();
assert(initial.health === "binding_required", `expected binding_required, got ${initial.health}`);
assert(initial.bindingServiceMode === "mock", `expected mock mode, got ${initial.bindingServiceMode}`);
await screenshot("01-binding-required.png");

await click('[data-testid="open-binding"]', "binding entry");
await waitFor("document.querySelector('[data-testid=\"simulate-binding-scan\"]') && document.querySelector('.qr-frame svg')", "mock QR wizard");
assert(await evaluate("document.querySelector('[data-testid=\"binding-wizard\"]').innerText.includes('模拟数据')"), "mock badge is missing");
await screenshot("02-mock-qr.png");

await click('[data-testid="simulate-binding-scan"]', "simulate scan");
await waitFor("document.querySelector('[data-binding-step=\"school\"]')", "school selection");
await screenshot("03-school-selection.png");
await click(".binding-choice-list button", "school choice");
await waitFor("document.querySelector('[data-binding-step=\"locationType\"]')", "location type selection");
await click(".location-type-grid button:first-child", "classroom type");
await waitFor("document.querySelector('[data-binding-step=\"location\"]')", "classroom location selection");
await click(".binding-choice-list.location-list button", "classroom location");
await waitFor("document.querySelector('[data-binding-step=\"review\"]')", "classroom review");
await screenshot("04-classroom-review.png");
await click(".binding-confirm-button", "classroom confirmation");
await waitFor("!document.querySelector('[data-testid=\"binding-wizard\"]')", "classroom binding acknowledgement");
await waitFor("window.recorderShell.getSnapshot().then(value => value.health === 'healthy' && value.binding?.locationType === 'classroom')", "healthy classroom binding");

const classroom = await snapshot();
assert(classroom.binding?.classId, "classroom binding did not persist classId");
await screenshot("05-classroom-bound.png");

await click(".primary-actions .primary-action", "start recording");
await waitFor("window.recorderShell.getSnapshot().then(value => value.recording === 'recording')", "real microphone recording", 45_000);
await waitFor("document.querySelector('[data-testid=\"open-binding\"]')?.disabled === true", "rebind disabled while recording");
await screenshot("06-recording-and-rebind-disabled.png");
await delay(4_000);
if (options["pause-before-stop"] === "true") {
  await click(".primary-actions .danger-action", "pause recording");
  await waitFor("window.recorderShell.getSnapshot().then(value => value.recording === 'paused')", "recording pause", 45_000);
  await screenshot("06b-paused-without-console.png");
  await delay(1_500);
}
await click(".primary-actions .secondary-action", "stop recording");
await waitFor("window.recorderShell.getSnapshot().then(value => value.recording === 'idle')", "recording stop", 45_000);
await waitFor("window.recorderShell.getSnapshot().then(value => value.pending >= 1 && value.upload === 'mock_blocked')", "local-only mock queue", 45_000);

await click('[data-testid="open-binding"]', "rebind entry");
await waitFor("document.querySelector('.rebind-confirmation')", "rebind confirmation");
await click(".rebind-confirmation .binding-confirm-button", "approve rebind");
await waitFor("document.querySelector('[data-testid=\"simulate-binding-scan\"]')", "rebind QR");
await click('[data-testid="simulate-binding-scan"]', "simulate rebind scan");
await waitFor("document.querySelector('[data-binding-step=\"school\"]')", "rebind school selection");
await click(".binding-choice-list button", "rebind school choice");
await waitFor("document.querySelector('[data-binding-step=\"locationType\"]')", "rebind location type");
await click(".location-type-grid button:nth-child(2)", "studio type");
await waitFor("document.querySelector('[data-binding-step=\"location\"]')", "studio location selection");
await click(".binding-choice-list.location-list button", "studio location");
await waitFor("document.querySelector('[data-binding-step=\"review\"]')", "studio review");
await click(".binding-confirm-button", "studio confirmation");
await waitFor("!document.querySelector('[data-testid=\"binding-wizard\"]')", "studio binding acknowledgement");
await waitFor("window.recorderShell.getSnapshot().then(value => value.health === 'healthy' && value.binding?.locationType === 'studio')", "healthy studio binding");

const final = await snapshot();
assert(final.binding?.classId === "", "studio binding retained a classId");
assert(final.binding?.className === "", "studio binding retained a className");
await screenshot("07-studio-bound.png");

const result = {
  target: { title: target.title, url: target.url },
  initial: summarize(initial),
  classroom: summarize(classroom),
  final: summarize(final),
  verifiedAt: new Date().toISOString(),
};
fs.writeFileSync(path.join(outputDir, "result.json"), `${JSON.stringify(result, null, 2)}\n`, "utf8");
console.log(JSON.stringify(result, null, 2));
socket.close();

function summarize(value) {
  return {
    recording: value.recording,
    upload: value.upload,
    health: value.health,
    pending: value.pending,
    binding: value.binding,
    dataRoot: value.dataRoot,
    latestError: value.latestError,
  };
}

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

function delay(milliseconds) {
  return new Promise((resolve) => setTimeout(resolve, milliseconds));
}

function parseArgs(args) {
  const parsed = {};
  for (let index = 0; index < args.length; index += 1) {
    const argument = args[index];
    if (!argument.startsWith("--")) continue;
    const [key, inline] = argument.slice(2).split("=", 2);
    parsed[key] = inline ?? args[++index];
  }
  return parsed;
}

async function waitForTarget(baseUrl) {
  const started = Date.now();
  while (Date.now() - started < 30_000) {
    try {
      const targets = await fetch(`${baseUrl}/json/list`).then((response) => response.json());
      const match = targets.find((candidate) => candidate.type === "page" && candidate.title === "课堂录音采集助手");
      if (match?.webSocketDebuggerUrl) return match;
    } catch {}
    await delay(200);
  }
  throw new Error(`timed out waiting for packaged Electron target at ${baseUrl}`);
}
