# Windows 客户端教师登录与设备绑定方案

更新时间：2026-07-25

## 1. 已确认的产品边界

- Windows 客户端复用数智家校 Passport 登录；小程序当前不支持扫码，因此正式流程不再以扫码为前提。
- 教师、班主任、信息化管理员和学校管理员均可绑定、解绑和重新绑定，四类角色在本客户端内等价。
- 登录和绑定只用于取得设备所属学校及当前绑定目标，不用于区分客户端内操作权限，也不用于标记每段录音的授课教师。
- 上述任一角色完成一次登录和绑定即可，不要求日常切换账号。
- Passport Cookie 只用于登录、创建或补全用户资料、查询学校范围和确认绑定。
- 绑定成功后，正常启动、录音和上传不依赖用户持续在线，也不长期保活 Passport Cookie。
- 重新绑定、迁移设备或变更班级时重新登录。
- 班级和公共录播室采用同一套使用和维护权限；上述角色均可创建、重命名和合并绑定目标。
- 音频按上传时的设备当前绑定归属；重绑前录制、重绑后补传的音频归到新绑定目标。

## 2. 目标流程

1. 未绑定客户端显示“登录并绑定设备”。
2. 客户端打开现有数智家校 passport 登录页。
3. 操作者通过 Passport 当前支持的账号密码或验证码完成登录。
4. Passport 完成身份选择后跳转到 `https://szjx-console.xxt.cn/`；客户端只把该域视为登录完成，不能把中间页 `szjx.xxt.cn` 或 Passport 登录页当作成功。
5. 客户端使用同一隔离 Cookie 会话请求 `GET https://szjx-console.xxt.cn/api/user-data-v2/user/get-user-info-by-login`，取得当前身份的 `schoolId`、`schoolName`、`userName` 和 `userType`。现网页教师侧身份的 `userType` 为 `0`；客户端接受 `0` 并拒绝学生侧身份。
6. 操作者选择班级教室或公共教室。班级教室先调用年级列表，再按 `gradeCode` 调用班级列表；公共教室直接填写名称。
7. 服务端保存设备当前绑定，客户端不解析绑定接口的其他返回字段，而是用本次请求和当前登录身份构造 worker 所需的本地绑定。
8. 登录窗口结束；后续录音和上传只使用设备身份。

现有登录页：
https://passport.xxt.cn/login?app=szjx&url=https%3A%2F%2Fszjx.xxt.cn%2F

绑定记录至少包含：

```text
deviceNo + schoolId + bindType
+ classId（仅 bindType=1）
+ classroom（两种 bindType 均传展示名称）
+ boundByUserId + effectiveAt + revokedAt(可空)
```

客户端和现有接口中不存在 `locationId`，不再把它作为产品或接口前提。公共教室在客户端只是一段用户填写的 `classroom` 名称，客户端不管理公共教室实体或主键。

## 3. Cookie 会话

Web 前端现有调用：

```js
http.request({
  url: "/login-v2/login/keep-login-alive",
  method: "post",
  params: {},
});
```

该调用没有查询参数和业务请求体，但浏览器仍会自动携带匹配域的 Cookie，服务端仍须返回 HTTP 状态。前端忽略响应内容不等于接口没有响应。

客户端已实现和后续要求：

- Cookie 由 Electron 的隔离登录会话持有，不传给 React renderer 或 Python worker。
- 每次绑定或重绑均打开 Passport 窗口；身份选择完成后通过同一 Electron session 读取当前用户并调用年级、班级和绑定接口。
- 当前不依赖 keep-login-alive 完成绑定；其 TTL、状态码和必要性仍由服务端后续明确。
- Cookie 失效只会使新的绑定请求失败，不影响 worker 继续本地录音。
- Cookie 不写入普通 JSON、worker 配置、诊断包或日志。

服务端必须明确 Cookie 的域、路径、Secure、HttpOnly、SameSite、有效期，以及保活接口的状态码、TTL、Set-Cookie、限流和撤销行为。

## 4. deviceNo 与上传安全

`deviceNo` 使用电脑物理网卡 MAC 地址。卸载重装后重新读取同一 MAC，设备编号保持不变；更换网卡导致 MAC 变化时按新设备处理。上传不依赖 Passport Cookie 或用户 access token。已确认的服务端方案会先用设备签名换取短期 `Device-Access-Token`，再获取 OSS 凭证和登记文件。

MAC 用作设备编号和绑定查找键，但不能单独作为上传凭证：

- MAC 标识网卡而不是整台电脑，一台电脑可能有有线、无线和虚拟网卡。
- Windows 支持随机硬件地址；更换网卡或修改地址会改变 MAC。
- MAC 可被读取和仿冒；只提交 deviceNo 的公网接口无法阻止他人冒充设备上传。

因此必须区分：

- deviceNo：设备标识，用于服务端查找绑定。
- 设备证明：服务端确认请求确实来自已绑定电脑的凭据或签名。

### 推荐的无 access token 方案

绑定成功时由服务端生成随机 deviceSecret，客户端使用 Windows Credential Manager 或 DPAPI 保护。上传请求包含：

```text
Device-No
Device-Timestamp
Device-Nonce
Device-Signature = HMAC(deviceSecret, method + path + bodyHash + timestamp + nonce)
```

服务端验证设备有效、签名、时间窗口和 nonce，并限制文件类型、大小、频率和并发。这不是教师 access token，也不获得教师的平台权限。

若不采用 HMAC，必须提供等价的设备证明，例如设备专用 Cookie、客户端证书或可信内网/mTLS；仅凭 MAC 不能满足正式上线的接口防攻击要求。

### deviceNo 稳定性规则

- `deviceNo` 使用规范化后的物理网卡 MAC 地址，不使用 loopback、VPN 或虚拟网卡。
- 多网卡选择顺序为有线物理网卡优先、Wi-Fi 物理网卡其次；排除蓝牙、虚拟机、VPN、回环和临时适配器。
- 首次选定后在非系统盘持久化所选 MAC；网卡暂时断开、禁用或离线时仍沿用原 `deviceNo`，不得自动漂移到另一块网卡。
- 只有所选物理网卡被实际更换或永久移除，并由用户重新配置设备时，才使用新 MAC 并视为新设备。
- 普通重绑始终沿用已持久化的 MAC；客户端仅在用户明确选择“网卡已更换”后读取当前物理网卡并按新设备发起绑定。
- 客户端不提供直接编辑 `deviceNo` 的文本框。
- 同一物理网卡在卸载重装、覆盖安装和应用升级后必须生成相同 `deviceNo`。
- 更换作为设备身份来源的网卡后进入“新设备，需要绑定”，不迁移旧设备绑定。
- 设备证明仍与 `deviceNo` 分离；本地设备密钥使用 Windows Credential Manager 或 DPAPI 保护。

## 5. 服务端开发清单

### Passport 和登录

- 复用现有登录页和 Cookie 会话。
- 为 Electron 登录场景配置允许的跳转目标和安全域策略。
- 保持身份选择后的正式落点为 `szjx-console.xxt.cn`，并允许隔离 Electron session 携带 Cookie 调用当前用户和 REST 接口。

### 用户和班级范围

- 当前登录用户沿用 `GET /api/user-data-v2/user/get-user-info-by-login`。
- 年级列表使用 `POST /ai-lesson-eval/basic-data/get-grade-list`，请求体为空。
- 班级列表使用 `POST /ai-lesson-eval/basic-data/get-class-list`，请求体只传 `gradeCode`；`schoolId` 省略，由当前登录身份确定学校。
- “教师”代表全部教师侧身份，教师、班主任、信息化管理员和学校管理员均可进入绑定流程。
- 四类角色在绑定、解绑、重绑以及创建、重命名、合并绑定目标方面使用同一权限。
- 禁止客户端通过篡改学校或目标标识绑定到用户不所属的学校。

### 设备绑定

- 使用 Passport Cookie 验证操作者身份和学校归属。
- 保存操作者、设备、学校、`bindType`、`classId`（班级教室）和 `classroom` 展示名称。
- 支持幂等提交、撤销、重新绑定和历史查询。
- 返回客户端可直接应用到 worker 的完整正式绑定。
- 为设备建立上传证明；不得只把 MAC 当作秘密。

### 录音上传

- 上传和元数据登记不依赖 Passport Cookie。
- 按 deviceNo 查找当前有效绑定，并验证设备证明。
- OSS 临时凭据或上传地址只能在设备证明通过后签发。
- 元数据登记时按设备当前绑定确定归属；延迟补传采用上传时的新绑定。
- 提供限流、防重放、文件校验、审计、封禁和撤销能力。

## 6. 客户端实现状态

- 已新增 Passport 登录和绑定入口，生产环境不再使用 mock 扫码入口。
- 已使用隔离 Electron session 打开 Passport，renderer 和 Python worker 均不接触 Cookie。
- 已在 Electron 主进程封装当前用户、年级、班级、绑定和解绑 HTTP adapter。
- 已按 `bindType=1/2` 实现班级选择和公共教室名称输入，并从运行状态中删除 `locationId` 模型。
- 解绑先让 worker 持久化 `unbind_pending` 并停止生产上传，再调用服务端；任一步骤失败或重启都保持 `binding_required`，服务端幂等解绑成功后才清空本地绑定。
- 保持 binding-service.js 和 binding-controller.js 为绑定协议边界。
- 正式绑定应用成功前不能启动生产上传。
- Python worker 不保存或使用 Passport Cookie。
- 按物理网卡 MAC 生成稳定 `deviceNo`；设备密钥使用 Windows 安全存储。
- 诊断导出脱敏 Cookie、session、deviceSecret、签名和 nonce。
- Passport Cookie 过期只阻止新的绑定/重绑，不能停止本地录音。
- 上传认证失败时录音继续落盘，队列等待恢复。
- 首次运行默认采用 Windows 当前默认麦克风，允许选择并记住所选设备；已选择设备消失时必须显式告警，不静默改录其他设备。
- 设置页只把高影响设置放入维护锁；隐藏入口可用于减少误触，但不能代替口令或动态授权。

## 7. 服务端接口设计对齐

2026-07-25 收到《7. 录音设备与文件上报》服务端设计，已确认以下设备上传契约：

- `POST /wisdom/book-reading/device-auth`：沿用现有 `deviceNo + sign + timestamp` 设备认证，返回 `accessToken`。
- `POST /wisdom/ali-oss/get-ali-oss-upload-token`：使用 `Device-Access-Token`，返回 `bucketName`、`endpoint`、`expireDate` 和服务端授权的 `uploadDir`。
- `POST /ai-lesson-eval/audio/save-audio-file-info`：使用设备令牌保存文件元数据，客户端不传 `schoolId`，服务端从认证上下文和当前设备绑定中确定学校及绑定快照。
- `POST /ai-lesson-eval/recording-device/bind-device` 和 `unbind-device`：录音设备绑定和解绑接口。

最新确认的绑定请求契约：

| 字段         | 规则                                                                                                           |
| ------------ | -------------------------------------------------------------------------------------------------------------- |
| `schoolId`   | 必传，目标学校 ID                                                                                              |
| `deviceNo`   | 必传，规范化物理网卡 MAC                                                                                       |
| `deviceName` | 删除，不传                                                                                                     |
| `bindType`   | 必传，`1=班级教室`，`2=公共教室`                                                                               |
| `classId`    | `bindType=1` 时传；`bindType=2` 时不传                                                                         |
| `classroom`  | 两种类型均传。班级教室为“班级名+录音设备”，如“1.1班录音设备”；公共教室为用户自定义名称，如“多媒体教室录音设备” |

客户端只负责提交公共教室名称，不管理公共教室实体、主键、重命名或合并模型。

设备认证返回值的客户端使用规则：

- 客户端只读取并保存短期 `accessToken`，用于后续 OSS 凭证和音频文件信息接口。
- `schoolId`、`schoolName`、`groupId`、`groupName`、`city` 等其他返回字段不参与客户端状态、绑定恢复或上传归属判断。
- 不为公共教室新增 `bindType` 或 `classroom` 认证返回字段；学校和绑定归属由服务端在保存音频文件信息时根据设备当前绑定确定。

Windows worker 已按上述确认契约调整 OSS 凭证和音频元数据适配层：

- OSS 对象键必须使用服务端返回的 `uploadDir`，客户端不再自行拼接固定目录。
- 元数据使用 `fileName`、字节单位 `fileSize`、`fileFormat`、`recordStartTime`、`recordEndTime` 和 `uploadStatus`。
- `schoolId` 非必填，客户端不传；服务端根据设备认证上下文获取学校。
- `filePath` 提交可访问的文件 URL，不提交 OSS object key。
- `recordStartTime/recordEndTime` 固定使用东八区时间。
- 客户端不向元数据接口提交学校或位置作为权威归属，服务端在登记时按设备上传时的当前绑定保存归属。
- 上传成功提交 `uploadStatus=1`；客户端不提交状态 `2`；确认上传失败时提交 `uploadStatus=3`。
- `uploadStatus=3` 时 `filePath` 可空、`failReason` 必填；同一 `deviceNo + recordStartTime` 后续重试成功时允许从状态 `3` 更新为 `1`。

以下内容已经不再构成阻断：

1. `deviceNo` 使用物理网卡 MAC；更换网卡视为新设备。
2. 不区分管理员和教师的客户端操作权限，四类指定角色等价。
3. 客户端不使用 `locationId`；按服务端 `bindType + classId + classroom` 契约接入。
4. 重绑后补传采用上传时当前绑定，不保留录制时原班级归属。
5. `filePath` 传完整 URL；时间时区及 `uploadStatus` 的业务含义已经明确。

## 8. 待联调事项

客户端所需字段和流程已经明确，当前剩余项属于服务端实现与联调，不阻断客户端继续开发：

1. `rest.xxt.cn/ai-lesson-eval/...` 接口仍处于设计阶段，需服务端上线后验证真实 Cookie 跨域策略、公共响应包络和错误码。
2. 验证年级、班级、绑定和解绑接口在隔离 Electron session 中确实接收 Passport Cookie。
3. 验证重绑的服务端原子语义，避免先解绑成功、后绑定失败造成中间无绑定状态；客户端当前直接提交新的绑定。
4. 明确 keep-login-alive 是否为绑定窗口内的必要调用及其 TTL。
5. 验证 OSS 完整 URL 在私有桶策略下是否能被后续服务读取。

## 9. 设置、数据与隐私

- 自动录音默认开启；开机自启和自动录音仍是两个独立状态。
- 首次运行使用系统默认麦克风，用户可切换并记住选择。提供实时电平和短时试录，避免选到无声或错误输入。
- 推荐提供两种麦克风策略：“固定使用已选择设备”和“跟随系统默认设备”。正式部署默认前者；设备丢失时阻止录音并明确提示。
- 本阶段不做多麦混音和客户端无人声判断；音频全部上传，由服务端识别无人声并处理状态 `2`。
- `deviceNo` 只读；停用自动录音、切换数据盘、解绑/重绑等高影响操作进入维护锁。
- 维护锁采用每设备口令或服务端动态授权码，不使用全产品通用硬编码 key。“连续点击多次”可以作为隐藏入口，但不能作为安全校验。
- 主界面和托盘持续显示录音状态，学校负责完成师生告知和合法使用授权。
- Cookie、设备密钥、OSS 临时凭证不进入日志和诊断包；诊断包默认不包含音频。
- 本地音频目录限制到当前运行账号；学校电脑建议使用专用 Windows 账号和 BitLocker 数据盘。
- 上传成功文件按可配置保留期自动清理；失败和待传文件不得因普通网络故障删除，并设置磁盘预警和人工清理入口。
- 服务端使用 HTTPS、私有 OSS 权限、短期上传凭证和最小化保留策略；访问音频需审计。

## 10. 更新策略

- 支持启动后自动检查更新，以及设置页“检查更新”。
- 常规版本后台下载，下载完成后提示在安全时机重启更新；可由服务端设置灰度比例、暂停版本和最低可用版本。
- 录音中不安装更新。必须等当前音频安全落盘、worker 停止并确认队列完整后再替换程序和 worker。
- 自动更新沿用当前 NSIS 安装目标，发布物必须包含版本元数据、校验和并完成 Windows 代码签名。
- 更新失败保留当前可运行版本和本地数据；不得把应用、配置、音频或队列迁回系统盘。

## 11. 验收要求

- 未登录不能查询或提交绑定。
- 非四类指定角色以及不属于目标学校的用户不能通过篡改参数完成绑定。
- 任一指定角色绑定一次后，关闭登录窗口和重启 Windows 均可继续录音。
- Passport Cookie 过期后，已绑定设备仍能录音和上传；重新绑定要求再次登录。
- 仅知道 deviceNo 但没有设备证明时，不能获取 OSS 凭据、上传文件或登记录音。
- 断网和认证服务异常不停止录音，恢复后可补传且不会重复登记。
- 设备撤销后不能继续上传，但本地文件保留并给出可恢复状态。
- 同一网卡的卸载重装和自动更新后 `deviceNo` 保持不变；绑定、设置和待传队列保持不变。
- 保存的麦克风不存在时不静默切换，主界面明确显示阻塞原因和恢复动作。
