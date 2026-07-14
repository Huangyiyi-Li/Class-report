# Windows 客户端构建、发布与验收

## 1. 发布原则

- `feat/windows-recorder-production` 是当前开发分支，PR #1 保持 Draft。
- 每个候选版本使用新的 semver prerelease 标签，例如 `recorder-v0.1.19-beta.1`。
- 不复用、不移动已经触发构建的标签。
- GitHub Actions 成功只说明自动化和 CI 环境通过，不等于用户真机验收通过。
- 失败版本应从 Releases 撤下或明确标记不可用，避免用户继续下载。

## 2. 发布前自动化

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
git tag recorder-v0.1.19-beta.1
git push origin feat/windows-recorder-production
git push origin recorder-v0.1.19-beta.1
```

监控 `.github/workflows/windows-recorder.yml`，必须确认以下步骤全部成功：

- Python checks；
- Node.js checks；
- worker build；
- renderer build；
- NSIS 和 Portable build；
- packaged resource verification；
- packaged UI smoke；
- installer upload；
- prerelease publish。

下载 Release 中实际生成的 Setup 文件，再执行一次 SHA-256 校验和真机快速回归。测试的必须是 Release 资产，不能只测试本地 `release` 目录。

## 5. 正式发布前仍需完成

- Windows 10/11 x64 完整故障矩阵。
- 冰点/还原软件开启时的安装、重启、开机自启、升级和非系统盘持久化。
- 连续 72 小时稳定运行。
- 正式扫码绑定的端到端联调。
- Windows 代码签名和 SmartScreen 策略。

上述事项未完成前，只能发布内部测试版，不能宣称正式可部署。
