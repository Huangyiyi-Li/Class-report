# Windows 录音采集客户端交接

- 更新日期：2026-07-14
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
- 正式目标流程是微信扫码、登录小程序、选择账号已加入的学校，再选择或创建采集位置。
- 当前仓库不含小程序和 binding service，因此扫码自助绑定尚未实现，是外部集成阻断项。

### 采集位置

- 班级教室必须关联系统已有班级及 `classId`。
- 录播教室是公共教室，没有 `classId`，以系统中的设备位置 `locationId` 归属。
- 两类位置都允许“匹配已有位置”；缺少位置时按规则新建。
- 客户端最终绑定关系是 `deviceId + schoolId + locationId`。
- 后端创建报告时通过“设备位置 + 日期”选择录音，再选择有效时间段。

## 3. 当前技术结构

- `electron-recorder/src/`：Electron 主进程、React 界面、设置、诊断和 worker 客户端。
- `electron-recorder/worker/`：Python 独立录音进程、音频 journal、SQLite 队列、上传和恢复。
- Electron 与 worker 通过仅监听 `127.0.0.1` 的带随机令牌控制通道通信。
- worker 以 detached 进程运行；Electron 退出不应停止正在进行的录音。
- `electron-recorder/scripts/build-worker.py` 使用 PyInstaller 生成 `ClassroomRecorderWorker.exe`。
- 安装包必须包含 worker 和 `ffmpeg.exe`，目标电脑不需要另装 Python、Node.js 或 FFmpeg。
- `.github/workflows/windows-recorder.yml` 在 GitHub Windows runner 上运行检查并生成 NSIS/Portable 包。

## 4. 已完成但不能过度解读的验证

- Python worker 自动化测试、Node 自动化测试和 Vite 构建已通过。
- GitHub Actions 已成功生成 `0.1.18-beta.2` 的 Setup 和 Portable 文件。
- `0.1.18-beta.2` 的打包烟测成功加载主窗口、悬浮球和设置窗口。
- 该烟测设置了 `ELECTRON_SMOKE_TEST=1`，使用假的 worker endpoint，绕过真实首次配置、worker exe 启动、麦克风和数据盘。因此它不能证明真实正常启动可用。
- Windows 真机安装/升级/卸载矩阵、冰点环境和连续 72 小时运行均未完成。

## 5. 当前风险与阻断项

1. `WIN-REC-002` 已修复并通过本地候选 Setup 真机验收，但尚未发布新候选；证据见 `docs/windows-recorder/evidence/WIN-REC-002-summary.md`。
2. CI 已新增“不设置 `ELECTRON_SMOKE_TEST`”的 packaged 正常启动门禁；它验证真实 worker、endpoint/token、鉴权和无可见控制台，但不替代真机麦克风。
3. 首次启动未选择非系统盘时的阻塞提示已确认符合设计；安装器仍允许选到系统盘，部署验收必须记录并强制选择非系统盘。
4. 本地候选已验证 PyInstaller worker、PortAudio/sounddevice、FFmpeg、detached 续录和 Electron 重连；GitHub Actions 尚未运行本次未发布改动。
5. 扫码绑定依赖外部小程序和服务端仓库，当前只能使用受控预配置 fixture 做技术测试。
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
