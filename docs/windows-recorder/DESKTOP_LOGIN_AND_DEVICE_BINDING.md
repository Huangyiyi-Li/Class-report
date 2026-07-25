# Windows 客户端教师登录与设备绑定方案

更新时间：2026-07-25

## 1. 已确认的产品边界

- Windows 客户端使用数智家校的具体教师个人账号登录。
- 登录只用于证明操作者有权把电脑绑定到目标班级或采集位置，不用于标记每段录音的授课教师。
- 同班任意一位有权限教师完成一次登录和绑定即可，不要求日常切换账号。
- 教师 Cookie 只用于登录、创建或补全教师资料、查询授权范围和确认绑定。
- 绑定成功后，正常启动、录音和上传不依赖教师持续在线，也不长期保活教师 Cookie。
- 重新绑定、迁移设备或变更班级时重新登录。
- 上传以设备和采集位置归属，不以绑定时登录的教师归属。

## 2. 目标流程

1. 未绑定客户端显示“登录并绑定班级”。
2. 客户端打开现有数智家校 passport 登录页。
3. 教师通过扫码、账号密码或验证码完成登录。
4. 客户端使用登录 Cookie 查询当前教师身份。
5. 服务端创建或补全教师记录，返回该教师可管理的学校和班级。
6. 教师选择学校、班级教室或公共录播室并确认。
7. 服务端保存绑定关系和操作教师，客户端把正式绑定应用到 worker。
8. 登录窗口结束；后续录音和上传只使用设备身份。

现有登录页：
https://passport.xxt.cn/login?app=szjx&url=https%3A%2F%2Fszjx.xxt.cn%2F

绑定记录至少包含：

~~~text
deviceId/deviceNo + schoolId + locationId + classId(可空)
+ boundByTeacherId + effectiveAt + revokedAt(可空)
~~~

公共录播室没有 classId，但必须有 locationId。历史音频保留采集当时的绑定信息，重新绑定不能迁移旧录音。

## 3. Cookie 与保活接口

Web 前端现有调用：

~~~js
http.request({
  url: "/login-v2/login/keep-login-alive",
  method: "post",
  params: {},
});
~~~

该调用没有查询参数和业务请求体，但浏览器仍会自动携带匹配域的 Cookie，服务端仍须返回 HTTP 状态。前端忽略响应内容不等于接口没有响应。

客户端接入要求：

- Cookie 由 Electron 的隔离登录会话持有，不传给 React renderer 或 Python worker。
- 打开绑定流程时先调用一次保活接口；绑定过程中按服务端 TTL 调用。
- 2xx 表示会话有效；401/403 表示必须重新登录。
- 保活只能延长尚未失效的会话，不能恢复已过期或被撤销的 Cookie。
- 绑定成功后停止保活并结束教师会话；录音不中断。
- Cookie 不写入普通 JSON、worker 配置、诊断包或日志。

服务端必须明确 Cookie 的域、路径、Secure、HttpOnly、SameSite、有效期，以及保活接口的状态码、TTL、Set-Cookie、限流和撤销行为。

## 4. deviceNo 与上传安全

当前产品倾向把电脑 MAC 地址作为 deviceNo；上传不依赖教师 Cookie，也不使用 access token。

MAC 可以用于设备查找和兼容现有数据，但不能单独证明请求来自真实设备：

- MAC 标识网卡而不是整台电脑，一台电脑可能有有线、无线和虚拟网卡。
- Windows 支持随机硬件地址；更换网卡或修改地址会改变 MAC。
- MAC 可被读取和仿冒；只提交 deviceNo 的公网接口无法阻止他人冒充设备上传。

因此必须区分：

- deviceNo：设备标识，用于服务端查找绑定。
- 设备证明：服务端确认请求确实来自已绑定电脑的凭据或签名。

### 推荐的无 access token 方案

绑定成功时由服务端生成随机 deviceSecret，客户端使用 Windows Credential Manager 或 DPAPI 保护。上传请求包含：

~~~text
Device-No
Device-Timestamp
Device-Nonce
Device-Signature = HMAC(deviceSecret, method + path + bodyHash + timestamp + nonce)
~~~

服务端验证设备有效、签名、时间窗口和 nonce，并限制文件类型、大小、频率和并发。这不是教师 access token，也不获得教师的平台权限。

若不采用 HMAC，必须提供等价的设备证明，例如设备专用 Cookie、客户端证书或可信内网/mTLS；仅凭 MAC 不能满足正式上线的接口防攻击要求。

### deviceNo 稳定性规则

- 首次安装按明确优先级选择物理网卡，排除 loopback、虚拟机、VPN 和临时适配器。
- 选定后持久化规范化 deviceNo，后续启动不能随当前联网网卡漂移。
- 更换网卡或 deviceNo 变化时进入“设备身份异常”，不得静默创建新绑定。
- 服务端保存 MAC 属性，同时保留独立的内部 deviceId。

## 5. 服务端开发清单

### Passport 和登录

- 复用现有登录页和 Cookie 会话。
- 为 Electron 登录场景配置允许的跳转目标和安全域策略。
- 明确保活接口状态码、TTL、限流和撤销行为。

### 教师和授权范围

- 查询当前登录教师。
- 按账号创建或补全教师资料，操作必须幂等。
- 返回教师有权绑定的学校、班级、教室和公共录播室。
- 禁止客户端篡改学校、班级或位置 ID 绕过授权范围。

### 设备绑定

- 使用教师 Cookie 验证绑定权限。
- 保存操作者、设备、学校、位置、班级和生效时间。
- 支持幂等提交、撤销、重新绑定和历史查询。
- 返回客户端可直接应用到 worker 的完整正式绑定。
- 为设备建立上传证明；不得只把 MAC 当作秘密。

### 录音上传

- 上传和元数据登记不依赖教师 Cookie。
- 按 deviceNo 查找当前有效绑定，并验证设备证明。
- OSS 临时凭据或上传地址只能在设备证明通过后签发。
- 保存录音采集时的绑定快照，避免重绑改变历史归属。
- 提供限流、防重放、文件校验、审计、封禁和撤销能力。

## 6. 客户端开发清单

- 新增登录状态和绑定入口，替换生产环境 mock 扫码入口。
- 使用隔离 Electron session 打开 passport，renderer 不接触 Cookie。
- 在 Electron 主进程封装保活、当前教师和绑定 HTTP adapter。
- 保持 binding-service.js 和 binding-controller.js 为绑定协议边界。
- 正式绑定应用成功前不能启动生产上传。
- Python worker 不保存或使用教师 Cookie。
- 持久化稳定 deviceNo；设备密钥使用 Windows 安全存储。
- 诊断导出脱敏 Cookie、session、deviceSecret、签名和 nonce。
- Cookie 过期只阻止新的绑定/重绑，不能停止本地录音。
- 上传认证失败时录音继续落盘，队列等待恢复。

## 7. 接口契约待服务端确认

1. Passport 登录完成如何通知 Electron。
2. 登录 Cookie 是否可被隔离 Electron session 正常保存和发送。
3. keep-login-alive 的状态码、TTL 和 Set-Cookie 行为。
4. 当前教师、学校、班级、位置、教师补全和确认绑定接口。
5. MAC 选择规则是否与既有 Android/服务端 deviceNo 规则一致。
6. 上传最终采用 HMAC、设备专用 Cookie、客户端证书还是其他设备证明。
7. 旧接口 /wisdom/book-reading/device-auth 的迁移与兼容策略。

## 8. 验收要求

- 未登录不能查询或提交绑定。
- 无目标班级权限的教师不能通过篡改 ID 完成绑定。
- 任一有权限教师绑定一次后，关闭登录窗口和重启 Windows 均可继续录音。
- 教师 Cookie 过期后，已绑定设备仍能录音和上传；重新绑定要求再次登录。
- 仅知道 deviceNo 但没有设备证明时，不能获取 OSS 凭据、上传文件或登记录音。
- 断网和认证服务异常不停止录音，恢复后可补传且不会重复登记。
- 设备撤销后不能继续上传，但本地文件保留并给出可恢复状态。
