# Windows 真机开发与故障复现

## 1. 推荐环境

- Windows 10/11 x64 真机，不使用 Windows 7。
- 仓库放在 Windows 本地磁盘；若使用 WSL，只将它作为辅助 shell，不把 Windows 安装和录音测试放进 WSL。
- Node.js `22.22.1` 或更高版本。
- Python `3.11`，与 GitHub workflow 一致。
- Git、GitHub CLI、PowerShell 7 可选。
- 一个真实可用麦克风和一个非系统盘，例如 `D:` 或 `E:`。

## 2. 首次准备

```powershell
git clone https://github.com/Huangyiyi-Li/Class-report.git
cd Class-report
git switch feat/windows-recorder-production
cd electron-recorder
python -m pip install -r worker\requirements-build.txt
npm ci
```

基线检查：

```powershell
python -m pytest worker ..\windows_client\test_timeouts.py -q
npm test
npm run build
```

## 3. 先复现已发布安装包

不要先运行源码。先用用户实际下载的安装包复现，确认测试对象一致：

```powershell
Get-FileHash .\Classroom-Recorder-0.1.18-Setup-x64.exe -Algorithm SHA256
```

预期 SHA-256 见 `INCIDENTS.md`。记录是全新安装还是覆盖安装，并记录用户选择的安装目录。

从 PowerShell 启动已安装 exe，保留 stdout/stderr：

```powershell
$env:ELECTRON_ENABLE_LOGGING = "1"
& "E:\实际安装目录\课堂录音采集助手.exe" --enable-logging 2>&1 |
  Tee-Object -FilePath "$env:TEMP\classroom-recorder-main.log"
$LASTEXITCODE
```

不要在此复现步骤设置 `ELECTRON_SMOKE_TEST`。

检查安装内容：

```powershell
$resources = "E:\实际安装目录\resources"
Get-ChildItem $resources -Recurse | Select-Object FullName, Length
Test-Path "$resources\worker\ClassroomRecorderWorker.exe"
Test-Path "$resources\ffmpeg\ffmpeg.exe"
```

如错误指向 `app.asar` 中的模块，使用项目依赖检查实际包内容：

```powershell
npx asar list "$resources\app.asar" | Select-String "src|runtime-state|worker-bootstrap"
```

## 4. 本地源码调试顺序

先跑 Electron 正常开发入口，不设置烟测变量：

```powershell
npm run electron
```

如果问题只出现在打包后，准备可信 FFmpeg 并生成本地包：

```powershell
$env:FFMPEG_EXE = "C:\tools\ffmpeg\bin\ffmpeg.exe"
npm run dist:win
```

按以下顺序测试，失败后立即保存证据，不要连续修改多个层面：

1. `release\win-unpacked` 中的 exe 正常启动。
2. 首次启动不选择数据盘时，界面可打开并显示阻塞提示。
3. 选择非系统盘后，worker 配置和 runtime 目录生成。
4. worker 启动并产生 endpoint/token；Electron 能连接。
5. 真实麦克风开始录音并产生耐久文件。
6. 停止、再次开始和退出 Electron。
7. Electron 退出时 worker 继续录音，重开 Electron 后恢复连接。
8. NSIS 全新安装。
9. NSIS 覆盖升级、卸载和重装。
10. Portable 包单独运行，避免与安装版同时测试。

## 5. 正常启动测试与烟测的边界

`npm run electron:smoke` 和 CI 的 `ELECTRON_SMOKE_TEST=1` 只用于快速验证 Electron 包装和界面。它不能替代以下测试：

- 不设置测试变量的 packaged normal start；
- 真实 worker exe 启动和连接；
- 首次数据盘配置；
- 麦克风录音；
- 录音持久化和队列恢复。

修复 `WIN-REC-002` 时，应新增一个 Windows 正常路径集成测试。若首次配置无法无人值守，可以通过测试专用的临时非系统盘配置 fixture 启动真实 worker，但不能把假的 WorkerClient 当作发布证据。

## 6. 证据和隐私

可以提交：

- 错误堆栈、测试输出、脱敏后的目录结构；
- 安装包 SHA-256、Windows build、应用版本；
- 不含账号、令牌和学校信息的最小复现 fixture。

不得提交：

- 密码、token、Authorization、OSS 临时密钥、worker control token；
- 真实学校、班级、教师、设备绑定数据；
- 真实课堂录音；
- 生成的安装包、worker、FFmpeg 或整个诊断数据目录。

## 7. 每次修复的最小闭环

1. 保留真实失败证据。
2. 将根因收敛到一个层面。
3. 添加聚焦失败测试。
4. 做最小修复。
5. 跑自动化基线。
6. 重新构建安装包。
7. 在同一真机用正常路径复测。
8. 更新 `INCIDENTS.md`。
9. 提交并推送分支。
10. 只有发布门禁通过后才创建新标签。
