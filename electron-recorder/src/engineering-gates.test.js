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

test("Git normalizes text files to LF before cross-platform formatting checks", () => {
  const attributes = fs.readFileSync(
    path.join(repositoryDir, ".gitattributes"),
    "utf8"
  );
  const workflow = fs.readFileSync(
    path.join(repositoryDir, ".github", "workflows", "windows-recorder.yml"),
    "utf8"
  );

  assert.match(attributes, /^\* text=auto eol=lf$/m);
  assert.equal(workflow.match(/^\s{6}- "\.gitattributes"$/gm)?.length, 2);
});

test("Windows distributions are separate direct artifacts and tags publish a prerelease", () => {
  const workflow = fs.readFileSync(
    path.join(repositoryDir, ".github", "workflows", "windows-recorder.yml"),
    "utf8"
  );

  assert.match(workflow, /uses: actions\/checkout@v7/);
  assert.match(workflow, /uses: actions\/setup-node@v7/);
  assert.match(workflow, /uses: actions\/setup-python@v7/);
  assert.equal(workflow.match(/uses: actions\/upload-artifact@v7/g)?.length, 3);
  assert.equal(
    workflow.match(/uses: actions\/download-artifact@v8/g)?.length,
    3
  );
  assert.doesNotMatch(
    workflow,
    /uses: actions\/(?:checkout@v4|setup-node@v4|setup-python@v[56]|upload-artifact@v4|download-artifact@v[47])/
  );

  assert.match(workflow, /^\s{6}- name: Upload Windows Setup\s*$/m);
  assert.match(workflow, /^\s{10}path: .*\*-Setup-x64\.exe\s*$/m);
  assert.match(workflow, /^\s{6}- name: Upload Windows Portable\s*$/m);
  assert.match(workflow, /^\s{10}path: .*\*-Portable-x64\.exe\s*$/m);
  assert.equal(workflow.match(/^\s{10}archive: false\s*$/gm)?.length, 3);

  assert.match(workflow, /^\s{6}- name: Download Windows Setup\s*$/m);
  assert.match(workflow, /^\s{10}pattern: "\*-Setup-x64\.exe"\s*$/m);
  assert.match(workflow, /^\s{6}- name: Download Windows Portable\s*$/m);
  assert.match(workflow, /^\s{10}pattern: "\*-Portable-x64\.exe"\s*$/m);
  assert.equal(workflow.match(/^\s{10}merge-multiple: true\s*$/gm)?.length, 2);
  assert.match(workflow, /\bgh release create\b.*\s--prerelease\b/);
  assert.match(
    workflow,
    /优先下载 Setup 安装版；Portable 仅用于临时免安装测试。/
  );
});

test("successful feature-branch pushes allocate a new beta tag and publish a prerelease", () => {
  const workflow = fs.readFileSync(
    path.join(repositoryDir, ".github", "workflows", "windows-recorder.yml"),
    "utf8"
  );

  assert.match(
    workflow,
    /github\.event_name == 'push' && github\.ref == 'refs\/heads\/feat\/windows-recorder-production'/
  );
  assert.match(workflow, /^\s{6}- name: Determine release identity\s*$/m);
  assert.match(workflow, /\$nextBeta = \$highestBeta \+ 1/);
  assert.match(
    workflow,
    /npm version --no-git-tag-version "\$\{\{ steps\.release_meta\.outputs\.version \}\}"/
  );
  assert.match(
    workflow,
    /gh release create \$releaseTag \$assets --target \$env:GITHUB_SHA --prerelease/
  );
});
