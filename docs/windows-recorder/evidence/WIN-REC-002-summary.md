# WIN-REC-002 Windows 现场证据摘要

- 采集日期：2026-07-14
- 测试系统：Windows 10 Pro x64，build 19045
- 测试资产：`Classroom-Recorder-0.1.18-Setup-x64.exe`
- 资产来源：GitHub Release `recorder-v0.1.18-beta.2`
- 文件大小：143,862,036 bytes
- SHA-256：`c914df39a0c6739a0991fdc779561440875373c820269cbdf712534107e11f20`
- 安装方式：卸载旧安装并原地改名备份旧 userData 后，全新 per-user 安装

## 复现结果

1. Setup 正常安装并自动启动 Electron；没有主进程错误弹窗，5 个 Electron 进程持续运行。
2. 安装器本次未展示目录选择步骤，实际安装到系统盘的 per-user Programs 目录。该行为违反“程序安装在非系统盘”的部署约束，需作为独立发布门禁处理。
3. 干净首次启动时 locator 不存在，主界面和设置界面正常打开。界面显示“请先选择非系统盘录音目录”，与用户截图一致。
4. 在设置界面输入新的 E 盘测试目录并保存后，locator、worker 配置、runtime 目录、worker endpoint 和 token 文件均成功生成。
5. packaged `ClassroomRecorderWorker.exe` 成功启动。两个同名进程构成 PyInstaller one-file 父子进程，进程树稳定；Electron 能获得 `binding_required` 状态。
6. worker 启动时出现可见黑色控制台窗口。源码构建脚本使用 PyInstaller `--onefile`，但没有 `--noconsole` 或 `--windowed`，现有自动化也未约束该行为。
7. 退出 Electron 后 worker PID 保持不变；不设置 `ELECTRON_SMOKE_TEST` 重开 Electron 后，仍连接同一 worker，主进程持续运行且 stdout/stderr 为空。

## 结论

用户截图中的“请选择非系统盘录音目录”是设计要求的首次配置阻塞状态，不是主进程崩溃。现场能够稳定复现的启动缺陷是 worker 启动时弹出控制台窗口；此外，安装器默认落到系统盘违反部署约束。修复不得绕过非系统盘、安全绑定或麦克风门禁。

本摘要不包含 locator 内容、worker control token、学校/设备绑定信息或录音内容。完整截图、进程快照和目录清单只保存在本机未跟踪证据目录中。

## 修复与本地候选验收

- 根因修复：`scripts/build-worker.py` 为 PyInstaller 增加 `--noconsole`；构建日志确认使用 Windows `runw.exe` bootloader。
- 回归门禁：新增不设置 `ELECTRON_SMOKE_TEST` 的 packaged 正常启动脚本和 CI 步骤，验证真实 worker endpoint/token、loopback 鉴权、ready 快照以及 worker 无可见窗口。
- 本地候选：`课堂录音采集助手-0.1.19-beta.1-Setup-x64.exe`，143,853,850 bytes，SHA-256 `16f44849b35128962d5e569c5bd90a34835f2f26e3d17d86172f647b17934977`。未创建标签、未上传、未发布。
- 安装位置：使用同一候选 Setup 安装到 `E:\WIN-REC-002\candidate-install`；卸载注册项版本为 `0.1.19-beta.1`。安装内容包含主程序、worker、FFmpeg 和 `app.asar`。
- 干净首次启动：不设置 smoke 环境变量，从已安装 exe 启动后有 5 个 Electron 进程、主窗口和悬浮球；locator 不存在时不启动 worker，符合首次配置阻塞设计。
- 真实 worker：使用非系统盘受控 binding fixture 后，由安装目录内 worker 启动 one-file 父子两个进程，均 `MainWindowHandle=0`；endpoint/token 生成，鉴权快照为 `idle/healthy`。
- 真实麦克风：使用本机默认 Realtek 输入完成两次开始/停止，形成两段约 5.1 秒 OGG；安装包自带 FFmpeg 解码退出码为 0，音量峰值分别为 -14.4 dB 和 -16.0 dB。
- detached 恢复：第三次录音中退出 Electron 后 worker 保持两个进程且 PCM 从 321,152 bytes 增长到 640,640 bytes；重开 Electron 后 ready 快照仍为 `recording/healthy`，停止后生成 60.04 秒、213,792 bytes 的 OGG，FFmpeg 解码退出码为 0，峰值 -7.0 dB。
- 隐私隔离：fixture 使用 `http://127.0.0.1:9` 作为不可达本机上传地址，不包含真实学校、账号或设备绑定数据；录音文件只保存在本机未跟踪的 E 盘证据目录，不提交仓库。
