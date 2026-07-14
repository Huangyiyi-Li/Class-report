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

当前结论：`0.1.18-beta.2` 在 GitHub Windows 构建和打包烟测中通过，但用户真实安装后仍然报错，不能作为可用版本交付。下一步必须在 Windows 10/11 x64 真机上复现正常启动路径。
