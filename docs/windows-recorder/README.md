# Windows 录音客户端文档入口

新电脑或新 Codex 任务从这里开始：

1. [项目交接与当前状态](HANDOFF.md)
2. [已知事故与排查结论](INCIDENTS.md)
3. [Windows 真机开发与复现流程](WINDOWS_DEVELOPMENT.md)
4. [构建、发布与验收流程](RELEASE_PROCESS.md)
5. [当前启动故障修复计划](../superpowers/plans/2026-07-14-windows-recorder-live-debug.md)
6. [模拟扫码绑定与安装包录音证据](evidence/WIN-REC-BINDING-MOCK-2026-07-15.md)
7. [教师登录、设备绑定与上传鉴权方案](DESKTOP_LOGIN_AND_DEVICE_BINDING.md)

产品设计和历史整改资料：

- [正式版产品设计](../superpowers/specs/2026-07-07-windows-recorder-production-design.md)
- [稳定性整改设计](../superpowers/specs/2026-07-13-windows-recorder-stability-remediation-design.md)
- [稳定性整改实施计划](../superpowers/plans/2026-07-13-windows-recorder-stability-remediation.md)
- [开发进度与历史任务报告](../../.superpowers/sdd/progress.md)

当前结论：`WIN-REC-002` 已在 Windows 10 Pro x64 真机复现。用户截图是首次未选择非系统盘时的预期阻塞提示；可重复的产品缺陷是 packaged worker 弹出控制台窗口。源码已使用无控制台 PyInstaller 子系统修复，并由本地 `0.1.19-beta.1` 候选 Setup 完成非系统盘安装、正常启动、真实 worker、真实麦克风录音和 Electron 重连验收。2026-07-15 又使用新构建并实际安装的 Setup 走通 mock 扫码绑定、教室录音与公共录播室重绑；mock 上传已强制阻断并只保留本地队列。该候选包尚未发布，最新公开候选仍是不可交付的 `0.1.18-beta.2`。
