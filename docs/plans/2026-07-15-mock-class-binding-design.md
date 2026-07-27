# 模拟扫码绑定班级设计

- 日期：2026-07-15
- 状态：已确认
- 适用范围：Windows 录音客户端的开发与内部测试构建

## 1. 目标

在服务端 binding service 和微信小程序尚未可用时，先完成 Windows 客户端内可操作、可测试、可替换的扫码绑定流程。用户能够从“设备尚未绑定”进入二维码向导，完成学校、位置类型和班级或录播教室选择，确认后解除 `binding_required`。未来接入真实服务时只替换服务实现，不重写界面、状态机、worker 持久化或录音门禁。

本阶段不实现真实微信登录、真实学校数据、真实二维码跨设备通信或生产绑定接口，也不允许正式模式在网络失败时回退到 mock。

## 2. 用户流程

未绑定时，主界面显示可用的“扫码绑定设备”按钮。点击后打开绑定向导：

1. 创建绑定会话并展示二维码、有效期和刷新入口；
2. 状态为 `waiting`，内部测试模式显示“模拟手机扫码”；
3. 模拟扫码后仍通过会话轮询进入 `scanned`，不由 UI 直接跳转；
4. 展示模拟登录用户并加载其学校列表；
5. 选择学校；
6. 选择“班级教室”或“录播教室”；
7. 班级教室选择已有班级，录播教室选择公共采集位置；
8. 展示完整摘要并确认绑定；
9. worker 持久化成功后展示当前绑定并解除录音门禁。

二维码会话状态为 `waiting | scanned | confirmed | expired | failed`。过期后允许生成新会话；列表或确认失败允许重试。关闭未完成向导不改变现有绑定。

已绑定时主界面显示学校、位置类型和班级或录播教室名称。空闲时可“重新绑定”，确认前给出二次提示；录音中禁止重新绑定。第一版不提供单独解绑入口。

## 3. 客户端架构

新增统一的 `BindingService` 契约，React 向导只依赖以下能力：

```js
createSession({ deviceNo })
getSession(sessionId)
simulateScan(sessionId) // 仅 Mock 实现和内部测试 UI 使用
listSchools(sessionId)
listLocations(sessionId, { schoolId, locationType })
confirmBinding(sessionId, selection)
```

`MockBindingService` 在进程内维护有生命周期的会话，返回固定、完全虚构的数据，并模拟等待、扫码、过期、确认和失败。`HttpBindingService` 保留同一契约，正式服务端接口确定后实现网络调用。

Electron 主进程持有 service 和当前客户端模式，通过窄 IPC 暴露绑定操作。renderer 不接触文件系统、worker token 或网络凭据。preload 只暴露具体绑定方法，不开放任意 IPC。

服务模式由主进程配置选择：只有显式 `BINDING_SERVICE_MODE=mock` 时启用模拟入口；默认值为 `remote`。正式模式没有服务端配置时显示明确不可用状态，绝不自动降级为模拟绑定。

## 4. 绑定数据

绑定记录包含：

```json
{
  "device_no": "本机生成、用户不可编辑",
  "school_id": 1,
  "school_name": "示例学校",
  "location_type": "classroom",
  "location_id": "location-101",
  "location_name": "一年级一班教室",
  "class_id": "class-101",
  "class_name": "一年级一班",
  "binding_source": "mock",
  "bound_at": "2026-07-15T00:00:00.000Z"
}
```

`location_type` 只能是 `classroom` 或 `studio`。班级教室必须有 `class_id` 和 `class_name`；录播教室的班级字段必须为空。所有字符串校验类型、长度和控制字符。模拟记录必须标记 `binding_source=mock`，正式服务记录标记 `remote`。

现有 `device_no`、`school_id`、`location_id`、`location_name` 继续作为录音和上传所需的权威字段；新增展示字段同样保存在非系统盘 `worker-config.json`。不在 Electron userData 中复制绑定记录。

## 5. worker 写入边界

控制协议新增 `apply_binding` 命令。Electron 收到服务确认结果后把完整绑定记录发送给 worker。worker 负责：

- 拒绝录音中的重新绑定；
- 校验绑定记录的结构和交叉字段；
- 保留不可由绑定响应覆盖的运行设置；
- 通过现有原子配置写入机制落盘；
- 更新内存配置和启动门禁；
- 广播包含新位置与绑定展示信息的快照。

Electron 不直接写 `worker-config.json`，避免双写入者。失败时 worker 保留原配置和原绑定。

重新绑定不修改历史 journal 或队列记录。每个音频段继续保存录制当时的 `device_no`、`school_id` 和 `location_id`，因此旧音频不会被归到新班级。

## 6. UI 规则

绑定向导使用现有视觉系统，采用单个 modal 和明确的步骤标题。二维码页显示倒计时、刷新与关闭；内部测试模式显示醒目的“模拟流程”标识。学校和位置使用单选卡片，班级教室与录播教室分别显示不同说明。确认页列出设备、学校、位置类型和目标位置。

绑定成功后主界面展示当前绑定卡片；模拟记录始终显示“模拟数据”，不得伪装成生产绑定。重新绑定按钮在 `recording` 或 `starting` 状态禁用，并解释“请先停止录音”。

所有异步操作都有 loading、空列表、失败和重试状态。二维码过期不会自动生成无限会话；用户明确点击后才刷新。关闭或失败不会写配置。

## 7. 测试与验收

自动化覆盖：

- Mock 会话的等待、扫码、确认、过期和非法状态转换；
- 两类位置列表与绑定结果结构；
- 正式模式不创建 Mock service，也不自动回退；
- IPC 参数校验和 renderer 隔离；
- `apply_binding` 的成功、录音中拒绝、非法记录拒绝和失败原子性；
- 重绑定后历史队列仍保留原归属；
- renderer 从未绑定到绑定成功的完整向导；
- 二维码过期、列表失败、确认失败和重试；
- 重启 Electron/worker 后绑定展示和录音门禁保持一致。

内部候选验收使用 `BINDING_SERVICE_MODE=mock`，从全新 userData 完成两种位置流程，确认 worker 从 `binding_required` 变为 `healthy`，并至少完成一次真实麦克风开始/停止。正式构建则验证模拟入口完全不可见。

## 8. 非目标

- 微信授权与小程序页面；
- binding service 数据库与管理后台；
- 真实学校、用户或班级资料；
- 解绑、设备迁移审批或远程策略；
- 网络失败时使用模拟数据兜底；
- 改变现有音频上传协议。
