# Windows 录音客户端文档入口

新电脑或新 Codex 任务从这里开始：

1. [项目交接与当前状态](HANDOFF.md)
2. [已知事故与排查结论](INCIDENTS.md)
3. [Windows 真机开发与复现流程](WINDOWS_DEVELOPMENT.md)
4. [构建、发布与验收流程](RELEASE_PROCESS.md)
5. [当前启动故障修复计划](../superpowers/plans/2026-07-14-windows-recorder-live-debug.md)

产品设计和历史整改资料：

- [正式版产品设计](../superpowers/specs/2026-07-07-windows-recorder-production-design.md)
- [稳定性整改设计](../superpowers/specs/2026-07-13-windows-recorder-stability-remediation-design.md)
- [稳定性整改实施计划](../superpowers/plans/2026-07-13-windows-recorder-stability-remediation.md)
- [开发进度与历史任务报告](../../.superpowers/sdd/progress.md)

当前结论：`WIN-REC-002` 已在 Windows 10 Pro x64 真机复现。用户截图是首次未选择非系统盘时的预期阻塞提示；可重复的产品缺陷是 packaged worker 弹出控制台窗口。源码已使用无控制台 PyInstaller 子系统修复，并由本地 `0.1.19-beta.1` 候选 Setup 完成非系统盘安装、正常启动、真实 worker、真实麦克风录音和 Electron 重连验收。该候选包尚未发布，最新公开候选仍是不可交付的 `0.1.18-beta.2`。
