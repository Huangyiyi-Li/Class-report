# Windows 客户端事故记录

## WIN-REC-003：切换接口环境被录音目录锁定错误阻断

- 状态：已定位并修复，等待新候选安装包真机复测
- 影响版本：`recorder-v0.2.0-codex.3`
- 用户现象：客户端默认显示测试环境；Passport 登录后查询目录提示登录状态失效。切换正式环境并保存时，又提示“录音数据目录首次部署后不可修改，需重新部署”。
- 根因一：设置页把已锁定、不可编辑的录音目录仍作为普通设置提交。Windows 路径表示与启动时记录不完全一致时，被错误识别为目录迁移，连带阻断接口环境保存。
- 根因二：新部署默认接口仍指向测试环境，不符合学校正式使用流程。
- 根因三：数智家校控制台从登录用户的 `webId` 生成后续业务接口的 `Authorization` 请求头；客户端只复用了 Passport Cookie，没有携带该请求头，因此能读取教师身份，却在查询年级班级时被业务接口判定为未登录。
- 修复：已锁定的录音目录不再进入普通设置更新；正式环境改为新部署默认值；测试环境仍可在设置中主动选择；Passport 业务请求按控制台现役逻辑携带只保存在 Electron 主进程内的授权值；现有录音目录、录音文件和待上传队列均不迁移、不删除。
- 防回归：新增“锁定目录不进入普通设置更新”“首次部署仍提交所选目录”“新部署默认正式环境”“年级班级请求携带控制台同源授权值”自动化测试。

## WIN-REC-001：0.1.17 安装后主进程缺少模块

- 状态：已定位并修复；失败 Release 已删除
- 影响版本：`recorder-v0.1.17-beta.1`
- 用户错误：`ERR_MODULE_NOT_FOUND`，`src/main.js` 无法导入 `src/runtime-state.js`
- 根因：`electron-recorder/package.json` 的 `build.files` 是手工白名单，遗漏 `src/runtime-state.js`
- 修复提交：`450b0f5 fix(recorder): include runtime state in Windows package`
- 防回归：`src/package-resources.test.js` 从主入口递归检查所有相对 import 是否都包含在 `build.files`

### 复盘

原有测试只检查 worker 和 FFmpeg 是否存在，没有检查 Electron 主进程依赖闭包。此事故不是用户电脑造成的。

## WIN-REC-002：0.1.18-beta.2 真实安装后启动体验异常

- 状态：已在 Windows 10 x64 真机复现、修复并由新构建的本地 Setup 完成正常启动、worker 与真实麦克风验收；尚未发布新版本
- 首次报告：2026-07-14
- 影响版本：`recorder-v0.1.18-beta.2`
- 已知现象：干净首次启动正常打开，但在未配置数据盘时显示“请先选择非系统盘录音目录”；保存合法 E 盘目录后 worker 能启动，但会弹出可见控制台窗口。安装器本次还默认安装到系统盘 per-user Programs 目录。
- 当前结论：用户截图是预期的首次配置阻塞状态，不是 `WIN-REC-001` 的主进程缺模块错误。现场确认 `app.asar` 包含 `runtime-state.js`。可重复的 packaged 缺陷是 worker 构建未使用 Windows 无控制台子系统；`--noconsole` 修复后，本地候选 Setup 已明确安装到 E 盘并通过正常启动、无窗口 worker、真实录音和 Electron 重连验收。安装器仍允许用户选择系统盘，部署时必须继续把非系统盘选择作为门禁。
- 脱敏证据摘要：`docs/windows-recorder/evidence/WIN-REC-002-summary.md`

### 已确认的测试缺口

GitHub workflow 的 `Run packaged application smoke test` 设置 `ELECTRON_SMOKE_TEST=1`。`src/main.js` 在该模式下使用假的 WorkerClient 和假的 endpoint，只验证：

- Electron 主进程能够加载被打包的 JS 模块；
- renderer、preload、主窗口、悬浮球和设置弹窗能够渲染；
- 页面没有明显溢出。

它没有验证：

- 无测试环境变量时的正常启动；
- 首次启动、非系统盘配置和 locator 文件；
- `ClassroomRecorderWorker.exe` 能否真正启动；
- worker 的 PyInstaller 动态依赖和 PortAudio；
- loopback endpoint/token、detached 进程和重连；
- 麦克风录音、FFmpeg 编码和队列落盘。

### Windows 真机必须采集的原始证据

在修改代码前保存到一个新的本地诊断目录，不要提交令牌、密码、学校数据或真实录音：

1. 错误弹窗完整截图和可复制错误文本。
2. Windows 版本：`winver` 和 `Get-ComputerInfo | Select WindowsProductName, WindowsVersion, OsBuildNumber, OsArchitecture`。
3. 安装包文件名、来源 URL 和 SHA-256。
4. 实际安装目录和 `resources` 目录清单。
5. 是否为覆盖安装；旧版本是否卸载；同机是否运行过 Portable。
6. 正常启动控制台输出和退出码。
7. `%LOCALAPPDATA%` 下本应用 userData 中 locator 是否存在；只记录路径和结构，发布前脱敏内容。
8. 非系统盘 `.classroom-recorder`、`runtime`、配置和日志是否生成；内容必须脱敏。
9. worker 是否出现于任务管理器，手动运行 worker 时的标准错误。

### 0.1.18-beta.2 官方候选文件校验值

资产在发布后改为 ASCII 文件名，二进制内容未改变：

```text
Classroom-Recorder-0.1.18-Setup-x64.exe
SHA256 c914df39a0c6739a0991fdc779561440875373c820269cbdf712534107e11f20

Classroom-Recorder-0.1.18-Portable-x64.exe
SHA256 1bf1534daa34f6e2d7f02f84e38444701d872b381f2b59f3209c9fe3caabf732
```

如本机文件校验值不同，先解决下载缓存或文件来源问题，不进入代码定位。

### 修复完成条件

- 用失败证据写出可复现步骤和根因说明。
- 自动化能够覆盖的根因必须先加入失败测试。
- 新候选包必须在发生故障的 Windows 真机上走正常启动路径通过。
- 验证安装包内 worker、FFmpeg、主进程模块，并至少完成一次真实麦克风录音。
- 更新本文、交接文档和发布记录后才能创建新 prerelease。
