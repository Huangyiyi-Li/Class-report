# 测试与发布门禁

## 自动化检查

从干净检出的仓库执行：

```powershell
cd electron-recorder
python -m pip install -r worker\requirements-build.txt
python -m pytest worker
npm ci
npm test
npm run build
npm run electron:smoke
```

`npm test` 已包含 `node scripts/test-clean-checkout.mjs`，用于确认构建输入均被 Git 跟踪且没有提交 `node_modules`、`dist`、`release`、PyInstaller 或 FFmpeg 生成物。

## Windows 打包与资源检查

以下命令必须在受支持的 Windows x64 机器执行。`FFMPEG_EXE` 必须指向经团队校验来源、版本和许可证的 Windows `ffmpeg.exe`；该二进制作为打包输入复制到生成目录，不提交仓库。

```powershell
$env:FFMPEG_EXE = "C:\tools\ffmpeg\bin\ffmpeg.exe"
npm run dist:win
Test-Path .\build\worker\ClassroomRecorderWorker.exe
Test-Path .\build\ffmpeg\ffmpeg.exe
Get-ChildItem .\release -Recurse -Filter ClassroomRecorderWorker.exe
Get-ChildItem .\release -Recurse -Filter ffmpeg.exe
```

还需安装 NSIS 包和便携包各一次，并验证全新安装、覆盖升级、保留用户数据的卸载，以及重新安装。生成的 `build/worker`、`build/ffmpeg`、`dist` 和 `release` 都不得提交。

## 故障测试

在 Windows 真机逐项验证：

1. 缺失或不可执行的 worker：应用应显示明确阻塞状态，不能开始录音。
2. 缺失或损坏的 FFmpeg：分段编码失败应被记录，原始音频不得静默丢失。
3. 麦克风被占用、拔出或权限拒绝：不得假报正在录音。
4. 系统盘或无效目录、设备/学校/教室绑定不完整：手动和自动录音都必须被阻止。
5. 断网、服务端错误、磁盘空间不足和进程重启：队列可恢复且不会重复丢失文件。
6. Electron 退出时 worker 正在录音：worker 继续运行；Electron 重启后可重连。
7. 诊断导出：保存成功和失败均有明确反馈，且 password、token、secret、authorization、control token 等字段在任意嵌套层级均已脱敏。

技术验证可以使用受控的预置设备/学校/教室 binding fixture，仅用于验证上述安全门和采集恢复链路。该 fixture 不是生产用户绑定流程；小程序和 binding service 仓库当前不在本项目中，自助扫码绑定仍是外部集成阻塞项。

## 发布前人工门禁

Mac 自动化不能替代以下门禁；未在目标环境留存证据前不得发布：

- Windows 10/11 x64 真机完成上述安装、升级、卸载、资源和故障测试。
- 冰点/还原软件启用环境验证重启、数据盘持久化、开机启动和升级行为。
- 连续 72 小时稳定运行，覆盖定时自动录音、网络中断恢复、磁盘压力和 Electron 重启重连。

Windows 7 明确不受支持，不属于发布验收目标。
