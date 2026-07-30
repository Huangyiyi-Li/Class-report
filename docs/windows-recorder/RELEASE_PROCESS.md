# Windows 客户端构建、发布与验收

## 1. 发布原则

- `feat/windows-recorder-production` 是当前开发分支，PR #1 保持 Draft。
- 每个可供客户端更新的候选版本使用新的 semver prerelease 标签，例如 `v0.2.0-codex.5`。
- 不复用、不移动已经触发构建的标签。
- GitHub Actions 成功只说明自动化和 CI 环境通过，不等于用户真机验收通过。
- 失败版本应从 Releases 撤下或明确标记不可用，避免用户继续下载。

## 2. 发布前自动化

提交代码时，`electron-recorder/.husky/pre-commit` 会对暂存文件执行
Prettier，并运行 Node.js 测试和桌面界面构建。首次执行 `npm ci` 或
`npm install` 后，`prepare` 脚本会自动安装该版本化钩子。

本地钩子用于提前发现问题，但可以被开发者跳过，不能替代 GitHub Actions。
Pull Request 和 `feat/windows-recorder-production` 分支推送必须以
`.github/workflows/windows-recorder.yml` 的结果为准。

在干净检出中执行：

```powershell
cd electron-recorder
python -m pip install -r worker\requirements-build.txt
python -m pytest worker ..\windows_client\test_timeouts.py -q
npm ci
npm test
npm run build
```

Windows 本地构建：

```powershell
$env:FFMPEG_EXE = "C:\tools\ffmpeg\bin\ffmpeg.exe"
npm run dist:win
```

构建完成后，除 renderer 烟测外，还必须执行不设置 `ELECTRON_SMOKE_TEST` 的正常启动门禁：

```powershell
$app = Get-ChildItem release\win-unpacked -Filter *.exe | Select-Object -First 1
.\scripts\test-packaged-normal-start.ps1 -AppPath $app.FullName
```

该门禁使用临时非系统盘目录启动真实 packaged worker，等待 loopback endpoint/token，完成认证并确认 worker 没有打开可见控制台。它不替代真实麦克风录音验收。

## 3. 每个候选包的真机验收

### 启动和安装

- Setup 全新安装后正常启动，无主进程错误。
- `win-unpacked`、Setup、Portable 三种形态至少各启动一次。
- 覆盖升级保留非系统盘配置和录音数据。
- 卸载移除应用文件和快捷方式，不删除录音数据和待传队列。
- 重装后能够读取保留数据或给出明确迁移提示。

### 录音和恢复

- 未选择非系统盘、未绑定、麦克风不可用时拒绝录音且状态准确。
- 合法数据盘和受控 binding fixture 下，真实麦克风能够录音。
- `BINDING_SERVICE_MODE=mock` 仅用于内部流程验收；此时上传状态必须为 `mock_blocked`，队列保持 `pending` 且两类尝试计数为 0。任何 mock 录音进入生产上传都必须阻止发布。
- 录音状态只在音频耐久写入后显示“录音中”。
- 断网继续录音，恢复网络后补传。
- Electron 退出不终止 worker；重开后恢复连接。
- Windows 重启后配置和待传数据仍在。

### 资源和诊断

- `resources\worker\ClassroomRecorderWorker.exe` 存在且可运行。
- `resources\ffmpeg\ffmpeg.exe` 存在且可执行。
- `app.asar` 包含主进程全部相对 import。
- 诊断导出成功，任意层级的 password、token、secret、authorization 和 control token 已脱敏。

## 4. GitHub 候选发布

在版本号、变更记录和上述真机证据齐全后：

```powershell
git status --short
git tag v0.2.0-codex.5
git push origin feat/windows-recorder-production
git push origin v0.2.0-codex.5
```

监控 `.github/workflows/windows-recorder.yml`，必须确认以下步骤全部成功：

- Python checks；
- Node.js checks；
- worker build；
- renderer build；
- NSIS 和 Portable build；
- packaged resource verification；
- packaged UI smoke；
- packaged normal-start test；
- installer upload；
- `codex.yml` 和 Setup blockmap 更新元数据；
- prerelease publish。

GitHub 仓库还应把 `Windows Recorder CI / build-windows-installer` 配置为
合并到 `master` 前的必需状态检查。该保护规则属于 GitHub 仓库设置，不能只靠
工作流文件替代。

下载 Release 中实际生成的 Setup 文件，再执行一次 SHA-256 校验和真机快速回归。测试的必须是 Release 资产，不能只测试本地 `release` 目录。

## 5. 正式发布前仍需完成

- Windows 10/11 x64 完整故障矩阵。
- 冰点/还原软件开启时的安装、重启、开机自启、升级和非系统盘持久化。
- 连续 72 小时稳定运行。
- 正式 Passport 登录与绑定的端到端联调。
- 使用真实 HTTP binding adapter 验证登录会话过期、学校归属、四类角色、公共录播室维护和确认幂等；生产模式不得回退 mock。
- Windows 代码签名和 SmartScreen 策略。
- 定期执行依赖漏洞审计，并在发布候选版本前关闭高危、严重风险或形成书面例外。

上述事项未完成前，只能发布内部测试版，不能宣称正式可部署。
