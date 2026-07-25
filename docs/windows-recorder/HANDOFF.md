# Windows 录音采集客户端交接

- 更新日期：2026-07-25
- 当前状态：开发中，尚未达到用户试用条件
- 仓库：`https://github.com/Huangyiyi-Li/Class-report.git`
- 工作分支：`feat/windows-recorder-production`
- Draft PR：`https://github.com/Huangyiyi-Li/Class-report/pull/1`
- 当前源码版本：`0.1.19-beta.1`（仅本地候选，未创建标签或 Release）
- 最新候选标签：`recorder-v0.1.18-beta.2`
- 最新状态：`WIN-REC-002` 已在 Windows 10 x64 真机完成本地修复验收；最新公开候选仍是不可交付的 `recorder-v0.1.18-beta.2`

## 1. 新 Windows 电脑接手步骤

安装 Codex Windows 客户端、Git、Node.js 22、Python 3.11 和 GitHub CLI。不要使用 Python 3.14 构建当前 worker；CI 和现有依赖基线是 Python 3.11。

```powershell
winget install --id Git.Git
winget install --id OpenJS.NodeJS.LTS
winget install --id Python.Python.3.11
winget install --id GitHub.cli
gh auth login
git clone https://github.com/Huangyiyi-Li/Class-report.git
cd Class-report
git switch feat/windows-recorder-production
```

在 Codex 中打开 `Class-report` 文件夹，新建任务并发送：

```text
先阅读仓库根目录 AGENTS.md，以及 docs/windows-recorder 下的全部文档。
继续处理 WIN-REC-002：0.1.18-beta.2 安装后在真实 Windows 正常启动路径报错。
先复现和保留原始证据，再定位根因；不要先猜测或发布新版本。
修复后必须使用新构建的安装包完成正常启动、worker 启动和麦克风录音验证。
```

不要依赖旧对话继续开发。仓库文档、Git 历史、PR 和事故记录是正式上下文。

## 2. 已确认的产品决策

### 平台和部署

- 首版仅支持 Windows 10/11 x64。
- Windows 7 不兼容是明确风险项，不在本阶段处理。
- 程序安装在非系统盘。
- 配置、音频、上传队列、运行状态和日志都必须放在非系统盘。
- 学校的冰点/还原系统通常还原系统盘；客户端不尝试绕过冰点。
- 开机启动项可能被冰点还原，部署时需要解冻固化或加白名单；失败时客户端必须显示实际状态。

### 录音行为

- “开机自启”和“启动后自动录音”是两个独立设置。
- 开启自动录音后，只要程序启动并通过安全检查，就开始录音。
- 客户端不读取课表，也不根据课表决定是否采集。
- 课表仅供后端在音频上传后切课和生成报告。
- 断网不能停止录音；网络恢复后补传。
- 音频 16 kHz、单声道、16 bit，5 分钟分段，至少每 10 秒形成安全落盘点。

### 用户与设备绑定

- 正式部署前，老师必须先通过现有资料导入流程加入系统。
- 一个登录账号可能属于多所学校，也可能尚未加入目标学校。
- 用户必须能自己完成全流程，不依赖运维或技术人员现场输入班级 ID。
- 最新确认的正式目标是 Windows 客户端打开现有数智家校 Passport；小程序当前不支持扫码，正式客户端不再以扫码流程为前提。
- 教师、班主任、信息化管理员和学校管理员均可绑定、解绑和重绑，四类角色在本客户端内等价；绑定只用于获取学校和设备当前归属，不承担客户端权限划分。
- Passport Cookie 只用于读取当前身份、查询年级/班级和确认绑定。绑定成功后，正常录音和上传不依赖登录会话；重新绑定时再次登录。
- `deviceNo` 使用规范化物理网卡 MAC；卸载重装后同一网卡编号不变，更换网卡视为新设备。设备编号不能代替上传凭证，正式接口仍须提供设备证明。
- 多网卡按有线物理网卡、Wi-Fi 物理网卡的顺序选择，排除蓝牙、虚拟机、VPN 和回环设备；首次选定后即使网卡暂时离线也不漂移，实际更换后才视为新设备。
- 普通重绑沿用已持久化的 MAC；只有用户明确选择“网卡已更换”才按当前物理网卡创建新设备。
- `/wisdom/book-reading/device-auth` 的客户端只消费 `accessToken`；其他返回字段不用于恢复学校或教室绑定，也不要求为公共教室新增返回字段。
- 音频信息使用 `POST /ai-lesson-eval/audio/save-audio-file-info`；`schoolId` 非必填且客户端不传，由服务端根据设备认证上下文获取。
- `filePath` 传完整 URL；状态 `3` 时 URL 可空且 `failReason` 必填，同一分片重试成功后允许更新为状态 `1`。
- 重绑前录制、重绑后补传的文件按上传时的当前绑定归属。
- 完整决策、服务端开发清单和接口待确认项见 docs/windows-recorder/DESKTOP_LOGIN_AND_DEVICE_BINDING.md。
- 客户端已实现正式 Passport 绑定流程：登录及身份选择后读取当前学校，班级教室按年级/班级选择，公共教室填写名称，空闲时可重绑。mock 模式复用同一界面和数据契约，仅用于内部流程验证。
- 解绑采用持久化两阶段安全门：先停止本地生产上传并写入待解绑状态，再调用服务端幂等解绑，最后清空本地绑定。
- 当前仓库已包含隔离 Cookie 的 Passport 登录协调器和 HTTP binding service。生产模式不回退 mock；由于 `rest.xxt.cn/ai-lesson-eval/...` 尚未开发，真实接口联调仍是外部阻断项。

### 采集位置

- 班级教室必须关联系统已有班级及 `classId`。
- 客户端和现有服务端接口中不存在 `locationId`，不得再以它作为开发前提。
- 当前绑定接口为 `POST /ai-lesson-eval/recording-device/bind-device`，按 `deviceNo + schoolId + bindType + classId + classroom` 表达，不传 `deviceName`。
- 班级和公共录播室使用同一套维护权限，四类指定角色均可创建、重命名和合并。
- `bindType=1` 时传 `classId` 和“班级名+录音设备”的 `classroom`；`bindType=2` 时不传 `classId`，只传用户自定义的 `classroom` 名称。
- 客户端不管理公共教室实体或主键。
- 后端创建报告时通过“设备当前绑定 + 日期”选择录音，再选择有效时间段。

### 麦克风、设置与更新

- 首次运行使用系统默认麦克风，允许切换并记住所选设备；保存设备丢失后明确阻塞，不静默切换。
- 本阶段不做多麦混音和本地无人声判断，无人声由服务端处理。
- 自动录音默认开启。高影响设置使用每设备维护口令或服务端动态授权码；多次点击只能隐藏入口，不能代替鉴权。
- 支持自动检查、后台下载和设置页手动检查更新；录音中不得安装更新，升级必须保留非系统盘数据和设备身份。
- 数据与隐私基线、更新安全门禁见 docs/windows-recorder/DESKTOP_LOGIN_AND_DEVICE_BINDING.md。

## 3. 当前技术结构

- `electron-recorder/src/`：Electron 主进程、React 界面、设置、诊断和 worker 客户端。
- `electron-recorder/worker/`：Python 独立录音进程、音频 journal、SQLite 队列、上传和恢复。
- Electron 与 worker 通过仅监听 `127.0.0.1` 的带随机令牌控制通道通信。
- worker 以 detached 进程运行；Electron 退出不应停止正在进行的录音。
- `electron-recorder/scripts/build-worker.py` 使用 PyInstaller 生成 `ClassroomRecorderWorker.exe`。
- 安装包必须包含 worker 和 `ffmpeg.exe`，目标电脑不需要另装 Python、Node.js 或 FFmpeg。
- `.github/workflows/windows-recorder.yml` 在 GitHub Windows runner 上运行检查并生成 NSIS/Portable 包。
- `electron-recorder/src/binding-service.js` 和 `binding-controller.js` 隔离绑定协议与界面；服务端就绪后应在该 adapter 边界接入 HTTP，不应改写录音核心状态机。

## 4. 已完成但不能过度解读的验证

- Python worker 自动化测试、Node 自动化测试和 Vite 构建已通过。
- GitHub Actions 已成功生成 `0.1.18-beta.2` 的 Setup 和 Portable 文件。
- `0.1.18-beta.2` 的打包烟测成功加载主窗口、悬浮球和设置窗口。
- 该烟测设置了 `ELECTRON_SMOKE_TEST=1`，使用假的 worker endpoint，绕过真实首次配置、worker exe 启动、麦克风和数据盘。因此它不能证明真实正常启动可用。
- Windows 真机安装/升级/卸载矩阵、冰点环境和连续 72 小时运行均未完成。
- 2026-07-15 本地 `0.1.19-beta.1` 新构建 Setup 已完成 mock 扫码、教室绑定、真实麦克风录音、录音中禁止重绑、公共录播室重绑验证；证据见 `docs/windows-recorder/evidence/WIN-REC-BINDING-MOCK-2026-07-15.md`。

## 5. 当前风险与阻断项

1. `WIN-REC-002` 已修复并通过本地候选 Setup 真机验收，但尚未发布新候选；证据见 `docs/windows-recorder/evidence/WIN-REC-002-summary.md`。
2. CI 已新增“不设置 `ELECTRON_SMOKE_TEST`”的 packaged 正常启动门禁；它验证真实 worker、endpoint/token、鉴权和无可见控制台，但不替代真机麦克风。
3. 首次启动未选择非系统盘时的阻塞提示已确认符合设计；安装器仍允许选到系统盘，部署验收必须记录并强制选择非系统盘。
4. 本地候选已验证 PyInstaller worker、PortAudio/sounddevice、FFmpeg、detached 续录和 Electron 重连；GitHub Actions 尚未运行本次未发布改动。
5. 服务端设计已确认设备认证、OSS 凭证、音频元数据和绑定接口；客户端适配层已按契约实现。`rest.xxt.cn/ai-lesson-eval/...` 尚未开发，当前只能用 mock 验证完整界面和本地 worker 边界，不能证明生产上传及 Cookie 联调成功。
6. 正式安装包尚未配置 Windows 代码签名证书。
7. 开机自启和冰点白名单行为未知。

## 6. 交付定义

只有同时满足以下条件，才能把版本交给用户试用：

- 使用发布页下载的同一份 Setup 安装包，在干净 Windows 10/11 x64 真机安装。
- 不设置测试环境变量，程序正常打开且没有主进程错误弹窗。
- 首次选择非系统盘后能生成配置、启动 worker 并展示真实状态。
- 使用真实麦克风开始录音、形成耐久文件、停止并再次启动。
- Electron 退出时 worker 继续录音，Electron 重开后能重新连接。
- 重启 Windows 后配置和待传文件仍在，开机自启实际状态与界面一致。
- 自动化测试和 GitHub Actions 同时通过。
- 新候选版本使用新的 prerelease 标签，旧失败版本明确撤下或标为不可用。
