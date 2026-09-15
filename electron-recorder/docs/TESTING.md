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

### Passport 错误跨隔离边界回归

运行 `npm run test:binding-bridge`（需要已安装 Electron 和桌面环境）。脚本使用真实的 sandboxed preload 与 contextBridge，核对页面收到的登录取消、绑定业务错误、解绑业务错误及部分解绑状态，与主进程诊断一致。仅运行 Node 单元测试无法覆盖 Electron 丢弃 Error 自定义字段的行为。脚本不登录真实账号、不启动录音 worker。

Windows 安装包还需核对：关闭 Passport 后页面与诊断均为 `BIND-C01`。

运行 `npm run test:passport-redirect` 验证真实 Electron 中旧首页 301 至 `szjx.xinzx.cn` 后能读取身份并自动关窗。该测试使用拦截的首页和模拟身份，不访问真实账号。2026-09-15 已通过公开首页的真实导航确认该域名跳转。Windows 真机仍需从新进程登录、选校，确认第一次就能自动关窗并进入绑定选择；保留同进程重试检查，不能以模拟身份测试代替真实 Passport 验收。

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

技术验证可以显式设置 `BINDING_SERVICE_MODE=mock`，走完扫码、选学校、选教室/录播室、确认和空闲时重绑流程。mock 模式必须同时满足：

- 界面明确显示“模拟模式”，上传状态显示“模拟模式，仅保存本地”。
- worker 不创建生产上传服务、不启动上传线程；录音队列保持 `pending`，`attempts` 和 `metadata_attempts` 都为 0。
- mock 绑定仅用于内部流程验证，不得作为发布候选的生产配置；未设置环境变量时默认使用 remote adapter，服务未实现时必须失败关闭，不能静默回退到 mock。

安装包端到端验证可使用：

```powershell
node scripts\verify-packaged-binding.mjs `
  --endpoint http://127.0.0.1:9335 `
  --output ..\docs\windows-recorder\evidence\binding-assets
```

脚本通过 Electron DevTools Protocol 操作真实 packaged 页面，要求真实麦克风成功录音，并验证录音期间禁止重绑、停止后音频只在本地排队。正式扫码绑定仍依赖待开发的 HTTP binding service 和小程序；客户端现有 `binding-service.js`/`binding-controller.js` 是未来 adapter 边界。

## 发布前人工门禁

Mac 自动化不能替代以下门禁；未在目标环境留存证据前不得发布：

- Windows 10/11 x64 真机完成上述安装、升级、卸载、资源和故障测试。
- 冰点/还原软件启用环境验证重启、数据盘持久化、开机启动和升级行为。
- 连续 72 小时稳定运行，覆盖定时自动录音、网络中断恢复、磁盘压力和 Electron 重启重连。

Windows 7 明确不受支持，不属于发布验收目标。
