# Windows 客户端事故记录

## WIN-REC-001：0.1.17 安装后主进程缺少模块

- 状态：已定位并修复；失败 Release 已删除
- 影响版本：`recorder-v0.1.17-beta.1`
- 用户错误：`ERR_MODULE_NOT_FOUND`，`src/main.js` 无法导入 `src/runtime-state.js`
- 根因：`electron-recorder/package.json` 的 `build.files` 是手工白名单，遗漏 `src/runtime-state.js`
- 修复提交：`450b0f5 fix(recorder): include runtime state in Windows package`
- 防回归：`src/package-resources.test.js` 从主入口递归检查所有相对 import 是否都包含在 `build.files`

### 复盘

原有测试只检查 worker 和 FFmpeg 是否存在，没有检查 Electron 主进程依赖闭包。此事故不是用户电脑造成的。

## WIN-REC-002：0.1.18-beta.2 真实安装后仍报错

- 状态：打开，阻断所有新发布和用户试用
- 首次报告：2026-07-14
- 影响版本：`recorder-v0.1.18-beta.2`
- 已知现象：用户确认安装后仍报错；本仓库尚未保存本次错误弹窗、完整错误文字和诊断文件
- 当前结论：不能假定与 `WIN-REC-001` 相同，也不能因为 CI 烟测通过就判定程序可用

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
