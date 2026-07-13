# Windows 录音客户端稳定性整改设计

- 状态：已确认
- 日期：2026-07-13
- 前置设计：`2026-07-07-windows-recorder-production-design.md`

## 1. 目标

修复核心实现复核发现的交付阻断项，使客户端能够从干净仓库构建，并让“非系统盘、绑定后录音、启动后自动录音、Electron 崩溃续录”成为真实运行约束，而不只是界面或测试中的字段。

## 2. 仓库可复现

正式构建所需的 `package.json`、锁文件、Vite 配置、构建脚本、应用图标和交付文档必须纳入版本控制。`node_modules`、`dist`、安装包和生成的 worker 可执行文件不得提交。干净检出后运行 `npm ci` 即可恢复依赖并执行测试和构建。

## 3. 启动安全门禁

worker 启动时必须验证：

1. `dataRoot` 是 Windows 绝对路径且不在系统盘；
2. 数据目录可创建、可写；
3. 剩余空间不少于 5 GiB；
4. `deviceNo`、`schoolId`、`locationId` 均已配置；
5. 麦克风可打开。

前四项不满足时禁止开始录音，并分别返回 `storage_unavailable`、`disk_low` 或 `binding_required`。不得回退到当前目录，也不得使用 `unconfigured-device`。网络不可用不属于录音门禁。

## 4. 独立 worker 生命周期

录音 worker 作为独立常驻进程运行，Electron 不是其生命周期所有者。两者通过仅监听 `127.0.0.1` 的本机控制通道交换换行分隔 JSON；worker 使用随机控制令牌校验连接，并通过锁文件/端口信息保证单实例。

Electron 启动时先连接现有 worker；连接失败时以 detached 模式启动 worker，再重试连接。Electron 正常退出或崩溃均只断开控制连接，不发送停止录音命令。只有用户明确执行“停止录音”才停止采集。worker 自身崩溃由下一次 Electron 启动恢复未完成日志；首版不增加 Windows 服务守护。

## 5. 设置与自动行为

- `autoLaunchEnabled`、`autoRecordEnabled`、麦克风、数据目录和绑定信息持久化到非系统盘配置文件。
- 客户端不得在首次启动时默认开启开机自启。
- 开机自启显示“已开启并验证、已设置但未验证、注册失败/不存在”三态。
- worker 完成安全检查后，如果 `autoRecordEnabled=true` 且当前未录音，自动开始录音。
- 设置值必须校验类型、长度和路径；录音中不得变更影响采集或存储的设置。

## 6. 诊断与打包

诊断导出生成脱敏 JSON 文件，不包含密码、令牌、临时密钥或控制令牌。Windows 安装包必须包含独立 worker 和 Windows `ffmpeg.exe`，且目标机器无需安装 Python。Windows 真实打包和冰点验证仍在 Task 7 完成。

## 7. 验收

除现有自动化测试外，至少新增以下可重复验证：

- 空数据目录、系统盘目录和未绑定状态均拒绝录音；
- 合法非系统盘且已绑定时允许录音；
- 自动录音设置在 worker 重启后生效；
- Electron 控制连接断开后录音状态保持；
- Electron 重启后重新连接同一 worker；
- 非法 IPC 设置不会写入配置；
- 干净仓库不依赖未跟踪文件即可安装依赖、测试和构建。

