# Windows 安装验证

本客户端支持 Windows 10/11 x64；Windows 7 不受支持。正式安装包不要求用户安装 Node.js 或 Python。

## 构建人员

在 Windows x64 的干净检出中先执行 [docs/TESTING.md](docs/TESTING.md) 的全部自动化命令，再设置可信 Windows FFmpeg 输入并打包：

```powershell
$env:FFMPEG_EXE = "C:\tools\ffmpeg\bin\ffmpeg.exe"
npm run dist:win
```

缺少 `FFMPEG_EXE`、PyInstaller、worker 构建失败或资源不存在时，打包必须失败。不要提交 `build/worker`、`build/ffmpeg`、`dist`、`release` 或依赖目录。

## 测试人员

分别验证 NSIS 安装包和便携包。NSIS 需覆盖：

1. 全新安装及首次启动。
2. 从上一正式版本覆盖升级，设置与录音数据不丢失。
3. 卸载后应用文件和快捷方式移除，用户录音数据保留。
4. 重新安装后可正常启动和绑定。

必须检查安装目录的 `resources\worker\ClassroomRecorderWorker.exe` 和 `resources\ffmpeg\ffmpeg.exe`。SmartScreen 对未签名测试包的告警不代表功能通过；正式发布仍需代码签名。

## 不可跳过的发布门禁

- Windows 10/11 x64 真机故障矩阵。
- 冰点/还原软件环境的重启与持久化验证。
- 连续 72 小时稳定运行验证。

具体步骤和失败预期见 [docs/TESTING.md](docs/TESTING.md)。上述门禁不能由 Mac 构建或自动化测试代替。
