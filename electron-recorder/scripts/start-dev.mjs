import { spawn } from "node:child_process";

const isWindows = process.platform === "win32";
const npmCommand = isWindows ? "npm.cmd" : "npm";

const vite = spawn(npmCommand, ["run", "dev"], {
  stdio: "inherit",
  shell: false,
});

const electron = spawn(npmCommand, ["run", "electron:dev:app"], {
  env: {
    ...process.env,
    ELECTRON_RENDERER_URL: "http://localhost:5180",
  },
  stdio: "inherit",
  shell: false,
});

function shutdown(code = 0) {
  if (!vite.killed) vite.kill();
  if (!electron.killed) electron.kill();
  process.exit(code);
}

vite.on("exit", (code) => {
  if (code) shutdown(code);
});

electron.on("exit", (code) => {
  shutdown(code ?? 0);
});

process.on("SIGINT", () => shutdown(0));
process.on("SIGTERM", () => shutdown(0));
