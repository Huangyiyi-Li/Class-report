# 课堂录音客户端悬浮窗：场景设计与白边排查

日期：2026-10-23。目标链路：`feat/recorder-first-use`，基线 `0.2.0-codex.35`，候选版本 `0.2.0-codex.37`。
状态：准备发布 `v0.2.0-codex.37` 内部测试候选；Windows 现场白边尚未复现，不能宣称已修复现场故障。

## 产品目标与交互

老师的主要任务是使用课件和白板授课。录音通常自动执行，需要能确认成功、临时暂停和处理故障，无需持续占用屏幕。

- 已配置数据目录的客户端启动到托盘；首次部署仍打开主窗口完成配置。录音自启设置与界面显示分别控制。
- 默认不显示悬浮窗；托盘和设置可主动开启。显示/隐藏偏好保存在非系统盘现有 `settings.json`，旧配置缺少字段时默认关闭，不重置其他设置。首次数据目录配置前仅本次会话有效。
- 按需显示的状态条现为 88×24 DIP 圆角胶囊，状态文字和颜色并用，关闭热区 24×24 DIP，可拖动。上一轮 104×36 直角方案被用户否定；本轮高度再减三分之一，面积较旧 62×62 原生窗口减少约 45%。24 DIP 热区偏鼠标操作，学校白板触摸仍需现场验证，不能宣称已验证触摸可用。
- × 仅隐藏；关闭主窗口或最小化不会重新弹出悬浮窗。加载期间隐藏也会取消待显示请求。
- 首次隐藏给出一次说明，后续不重复；点击状态打开主窗口，托盘保留开始、暂停、停止和恢复入口。
- 状态提示跟随真实快照：开始、恢复、暂停以及采集中断；同一持续故障仅提醒一次。初始化“正在启动录音服务”不提醒，上传进度、断网补传不触发采集中断提醒。
- 系统提示静音、不抢焦点；点击提示打开主界面。Windows 通知可能受系统设置/勿扰模式影响，托盘和主窗口仍是持续查看入口。客户端设置 AppUserModelID 与 NSIS 的 appId 一致，安装包的真实通知展示仍待验证。
- 退出界面明确提示录音继续；录音 worker 生命周期、录音说明和暂停/停止行为不因隐藏发生变化。

## 白边证据与判断

### 已从旧源码确认

1. 原生窗口 62×62、网页球 58×58，存在透明外围。
2. 同时使用 `transparent:true`、CSS 圆角、原生 `setShape()` 按整数扫描线构造圆形，存在多套轮廓。
3. CSS 自带白色 inset 高光、白色径向渐变和 ripple，不宜将所有亮边都归为操作系统故障。
4. `setShape()` 失败被空 catch 吞掉，降级后仍继续显示；缺少现场裁剪是否成功的证据。
5. 旧显示时机是 `did-finish-load`。该事件表示页面加载完成，不能证明首帧已绘制；官方建议使用 `ready-to-show` 避免加载闪烁。

### 官方资料与相似报告

- [Electron 35.7.5 BrowserWindow 文档](https://github.com/electron/electron/blob/v35.7.5/docs/api/browser-window.md)：首帧显示时机，`setShape()` 为 Windows/Linux 实验接口，限定绘制和鼠标区域。
- [Electron 35.7.5 窗口选项](https://github.com/electron/electron/blob/v35.7.5/docs/api/structures/base-window-options.md)：`thickFrame:false` 移除标准框架和阴影；Windows 11 原生圆角由 `roundedCorners` 控制，Windows 10 不同。
- [Electron issue #51662](https://github.com/electron/electron/issues/51662)：用户报告 Electron 35.0.0 / Windows 11 透明无框窗口失焦后出现白角，并报告 setShape 可阻止白角但有锯齿。该 issue 因缺少所需复现材料关闭，**并非维护者确认的根因或修复**。本项目 35.7.5 与其接近，属于待现场验证的假设。
- [Electron 通知说明](https://www.electronjs.org/docs/latest/tutorial/notifications)：Windows 通知需要匹配应用身份和开始菜单快捷方式；系统可能抑制通知。

不能仅凭资料判断用户现场属于白色高光、透明合成白角、缩放锯齿还是加载闪白。这些是不同现象，需要真机区分。

### 本次实现选择

最新方案为 88×24 圆角胶囊。Windows 使用不透明实色窗口、`frame:false`、`transparent:false`、`roundedCorners:false`、`thickFrame:false`、`hasShadow:false`，由一套按同样 88×24 尺寸计算的原生 capsule region 决定外部轮廓。网页填满同色背景；不保留旧 62×62 / 58×58 两套圆球轮廓，也不使用白色 inset 高光、外围透明圆环或波纹。网页 root 透明只表示不绘制网页底色，Windows 原生窗口本身仍为不透明背景。macOS 使用透明窗口配合 CSS 胶囊，无 Windows DWM 这条路径。

需要圆角后重新引入了单一原生 `setShape` 裁剪，但没有恢复旧透明圆球组合。原生裁剪仍有整数边缘及 DPI 风险，不能宣称锯齿问题已解决。裁剪失败会反馈“悬浮窗暂不可用”，继续通过托盘操作，不会静默退回有矩形外框的外形。仍在 `ready-to-show` 后显示，没有升级 Electron、关闭硬件加速或引入 DWM 补丁。

## 同类产品参考

- [Loom 隐藏录制控件](https://support.atlassian.com/loom/docs/hide-the-recording-controls/)：允许录制期间隐藏控件。借鉴用户控制可见性，不将快捷键作为教室触摸场景的唯一操作方式。
- [Bandicam 隐藏控件与托盘运行](https://www.bandicam.com/how-to-hide-bandicam-interface/)：支持隐藏控制条和托盘运行。注意“最终视频不显示”不等于实体课堂屏幕不受遮挡。

## 验证与验收边界

本地验证：Node 219 项通过及 clean-checkout 检查通过；Python worker/timeout 233 项通过、1 项跳过；Vite 构建通过；Mac 上 Electron 35.7.5 源码烟测通过（默认隐藏、显示、点击 × 隐藏、关闭主窗口仍隐藏、模拟录音状态不变、设置窗口可用）。Electron 下载文件核对官方 SHA-256。所有烟测均使用假的 worker，不能证明真实录音或 Windows 原生边缘无白边。浏览器截图 [胶囊预览](evidence/FLOATING-WINDOW-2026-10-23/preview.png) 使用真实编译页面置于 88×24 iframe，检查浅/深背景的页面样式；不是 Windows 原生窗口截图。

Windows 同一设备、同一新安装包必须补验：

1. Win10/Win11，100%、125%、150% 系统缩放；记录系统 build、应用版本、显示分辨率和缩放。
2. 浅/深课件背景，失焦、首次显示、反复隐藏/恢复、拖动、多屏不同缩放：检查白线、白角、白色矩形、闪白和鼠标拦截。
3. 正常/全屏 PPT、白板书写：默认无覆盖；主动开启时点击 × 有效，隐藏后不重新出现且录音持续落盘。
4. 触摸操作能准确关闭、拖动；24 DIP 热区仅为本地设计起点，未证明在学校白板可用。
5. 退出重开保留显示偏好；无数据盘、保存失败时不回退系统盘，提示结果准确。
6. 实际开始、暂停、恢复、拔麦、磁盘不可用；同一持续故障不重复提醒，恢复后再次故障可提醒。
7. 断网/补传失败仍录音时不提示“录音中断”；通知点击能打开主界面。分别检查系统通知开启/关闭/勿扰状态。
8. 不使用 `ELECTRON_SMOKE_TEST` 的真实 worker 录音和正常安装包启动。

## `.36` Windows 构建阻断与 `.37` 修正

[Windows CI 39888240585](https://github.com/Huangyiyi-Li/Class-report/actions/runs/39888240585) 在 `.36` 观察到请求 88×24、实际渲染视口 88×39；其余绑定、设置、隐藏交互通过，界面烟测整体失败，Release 未创建。原布局 `height:100vh` 会跟随原生最小高度变厚，底部还可能被 24px 原生 region 裁切。

`.37` 将可见组件固定为 88×24，不依赖原生最小高度；Windows 外围仍由同样 88×24 的胶囊 region 限定。界面烟测同时检查可见组件尺寸、关闭按钮完整位于 24px 内，以及主动将原生视口增至 48px 后可见组件仍为 24px。允许原生视口高于组件并非放行更厚的可见状态条。

[上游 issue #23200](https://github.com/electron/electron/issues/23200) 也有 Windows 最小窗口高度及用 setShape 限定可见部分的历史反馈；本次 39px 以自己的 CI 输出为直接证据。`.36` 标签保留且不复用。
