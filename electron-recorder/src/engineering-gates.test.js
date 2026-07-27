import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const recorderDir = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  ".."
);
const repositoryDir = path.resolve(recorderDir, "..");

test("Windows recorder CI validates pull requests with least-privilege permissions", () => {
  const workflow = fs.readFileSync(
    path.join(repositoryDir, ".github", "workflows", "windows-recorder.yml"),
    "utf8"
  );

  assert.match(workflow, /^\s{2}pull_request:\s*$/m);
  assert.match(workflow, /^permissions:\s*\n\s{2}contents: read\s*$/m);
  assert.match(
    workflow,
    /^\s{2}publish-github-prerelease:[\s\S]*?^\s{4}permissions:\s*\n\s{6}contents: write\s*$/m
  );
  assert.match(workflow, /^\s{6}- name: Check quality-gate formatting\s*$/m);
  assert.match(workflow, /\bnpx prettier --check\b/);
  assert.match(workflow, /^\s{10}GH_REPO: \$\{\{ github\.repository \}\}\s*$/m);
});

test("versioned pre-commit hook runs formatting, tests, and build", () => {
  const packageJson = JSON.parse(
    fs.readFileSync(path.join(recorderDir, "package.json"), "utf8")
  );
  const hook = fs.readFileSync(
    path.join(recorderDir, ".husky", "pre-commit"),
    "utf8"
  );
  const lintStaged = JSON.parse(
    fs.readFileSync(path.join(repositoryDir, ".lintstagedrc"), "utf8")
  );

  assert.equal(
    packageJson.scripts.prepare,
    "cd .. && husky electron-recorder/.husky"
  );
  assert.ok(packageJson.devDependencies.husky);
  assert.ok(packageJson.devDependencies["lint-staged"]);
  assert.ok(packageJson.devDependencies.prettier);
  assert.match(hook, /^set -e$/m);
  assert.match(
    hook,
    /^npm --prefix electron-recorder exec -- lint-staged --cwd \. --config \.lintstagedrc$/m
  );
  assert.match(hook, /^npm --prefix electron-recorder test$/m);
  assert.match(hook, /^npm --prefix electron-recorder run build$/m);
  assert.deepEqual(lintStaged, {
    "*": "prettier --ignore-unknown --write",
  });
});

test("hook tooling and CI use a compatible Node.js baseline", () => {
  const packageJson = JSON.parse(
    fs.readFileSync(path.join(recorderDir, "package.json"), "utf8")
  );
  const workflow = fs.readFileSync(
    path.join(repositoryDir, ".github", "workflows", "windows-recorder.yml"),
    "utf8"
  );

  assert.equal(packageJson.engines.node, ">=22.22.1");
  assert.match(workflow, /^\s{10}node-version: "22\.22\.1"\s*$/m);
});
