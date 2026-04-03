# 脚本说明 📜

本目录包含课堂录音处理系统的所有核心脚本。

## 📁 文件列表

### 主控制脚本
- **controller.py** - 统一控制入口 ⭐
  - 功能：智能识别处理模式，协调AI分析和音频处理
  - 运行：`python controller.py --course "第七次课0318"`

### AI分析脚本
- **auto_analyze_simple.py** - AI分析命令行脚本
  - 功能：读取录音和教案，执行AI深度分析
  - 运行：`python auto_analyze_simple.py "第七次课0318"`

- **icas_core.py** - AI核心分析引擎
  - 功能：多维度教学分析、报告生成
  - 被auto_analyze_simple.py调用

### 音频处理脚本
- **audio_processor.py** - 音频下载、转换、合并
  - 功能：从Excel下载音频，转换为高质量MP3并合并
  - 运行：`python audio_processor.py`

## 🚀 快速开始

### 1. 使用主控制器（推荐）⭐

```bash
# 智能模式（自动判断）
python controller.py --course "第七次课0318"

# 仅AI分析
python controller.py --course "第七次课0318" --mode analyze

# 仅音频处理
python controller.py --course "第七次课0318" --mode audio

# 完整处理
python controller.py --course "第七次课0318" --mode full

# 不打开浏览器
python controller.py --course "第七次课0318" --no-open
```

### 2. 直接运行子脚本

**AI分析**：
```bash
python auto_analyze_simple.py "第七次课0318"
```

**音频处理**：
```bash
# 需要先修改audio_processor.py的配置
# 然后运行
python audio_processor.py
```

## 📊 脚本功能对比

| 脚本 | AI分析 | 音频处理 | 智能识别 | 并行执行 |
|------|--------|---------|---------|---------|
| controller.py ⭐ | ✓ | ✓ | ✓ | ✓ |
| auto_analyze_simple.py | ✓ | ✗ | ✗ | ✗ |
| audio_processor.py | ✗ | ✓ | ✗ | ✗ |

## 🔧 核心函数

### controller.py

| 函数 | 功能 |
|------|------|
| `scan_course_folder()` | 扫描文件夹，判断可用功能 |
| `run_ai_analysis()` | 运行AI分析 |
| `run_audio_processing()` | 运行音频处理 |
| `main()` | 主流程，处理命令行参数 |

### auto_analyze_simple.py

| 函数 | 功能 |
|------|------|
| `scan_course_folder()` | 扫描课程文件夹 |
| `read_transcript()` | 读取录音文件 |
| `read_lesson_plan()` | 读取教案文件 |
| `run_icas_analysis()` | 执行ICAS分析 |
| `generate_pdf_report()` | 生成PDF报告 |

### audio_processor.py

| 函数 | 功能 |
|------|------|
| `read_excel_links()` | 从Excel读取音频链接 |
| `download_audio_files()` | 批量下载音频 |
| `convert_to_mp3()` | 转换为高质量MP3 |
| `merge_mp3_files()` | 合并音频文件 |

## 📋 工作流程

### controller.py流程

```
1. 解析命令行参数
   ↓
2. 扫描课程文件夹
   ↓
3. 判断可用功能
   ├─ 有转录文本 → AI分析
   ├─ 有音频链接 → 音频处理
   └─ 两者都有 → 完整处理
   ↓
4. 并行执行（如果需要）
   ↓
5. 显示结果
   ↓
6. 打开浏览器（可选）
```

### AI分析流程

```
auto_analyze_simple.py
    ↓
读取录音和教案
    ↓
调用 icas_core.py
    ↓
多维度AI分析
    ↓
生成HTML报告
    ↓
生成PDF报告
    ↓
打开浏览器
```

### 音频处理流程

```
audio_processor.py
    ↓
读取Excel (file_path列)
    ↓
批量下载音频
    ↓
转换为MP3 (320kbps)
    ↓
按顺序合并
    ↓
输出完整MP3
```

## ⚙️ 配置参数

### audio_processor.py配置

```python
EXCEL_FILE = "第七次课0318/语文-7段-0918-0948.xlsx"
DOWNLOAD_DIR = "第七次课0318/downloads"
CONVERTED_DIR = "第七次课0318/converted"
OUTPUT_FILE = "第七次课0318/0918-0948.mp3"
FFMPEG_PATH = "ffmpeg-2025-12-22-git-c50e5c7778-essentials_build/bin/ffmpeg.exe"
```

### MP3质量参数

```python
MP3_QUALITY_PARAMS = [
    "-codec:a", "libmp3lame",
    "-b:a", "320k",           # 比特率
    "-ar", "48000",           # 采样率
    "-ac", "2",               # 声道数
    "-q:a", "0"               # 质量等级
]
```

## 🐛 调试技巧

### 查看详细输出

**controller.py**:
```bash
# 显示完整输出
python controller.py --course "第七次课0318" --mode analyze
```

**audio_processor.py**:
```python
# 在脚本中添加调试信息
print(f"命令: {cmd}")
print(f"返回码: {result.returncode}")
print(f"错误: {result.stderr}")
```

### 测试单个功能

**测试AI分析**：
```bash
cd scripts
python auto_analyze_simple.py "../第七次课0318"
```

**测试音频下载**：
```bash
# 只下载不转换
# 修改audio_processor.py，注释掉转换和合并部分
python audio_processor.py
```

### 验证文件

**检查Excel**：
```python
import pandas as pd
df = pd.read_excel("语文-7段-0918-0948.xlsx")
print(df.columns)
print(df.head())
```

**检查ffmpeg**：
```bash
ffmpeg -version
ffmpeg -h
```

## 📝 注意事项

### Windows路径问题

**问题**：路径中的反斜杠

**解决**：
```python
# 使用原始字符串
path = r"C:\path\to\file.mp3"

# 或使用Path对象
from pathlib import Path
path = Path("C:/path/to/file.mp3")
```

### 编码问题

**问题**：Windows终端中文乱码

**解决**（已包含在脚本中）：
```python
import sys
import io

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
```

### 权限问题

**问题**：无法创建目录或写入文件

**解决**：
```python
# 检查权限
import os
os.access('.', os.W_OK)

# 或以管理员身份运行
```

## 🔗 相关资源

- [ffmpeg官方文档](https://ffmpeg.org/documentation.html)
- [libmp3lame参数](https://trac.ffmpeg.org/wiki/Encode/MP3)
- [Python pandas文档](https://pandas.pydata.org/docs/)
- [Playwright文档](https://playwright.dev/python/)

## 💡 最佳实践

### 1. 使用主控制器
```bash
# 推荐：使用controller.py
python controller.py --course "第七次课0318"
```

### 2. 批量处理
```bash
# 创建批处理脚本
for course in 第六次课0318 第七次课0318 第八次课0318; do
    python controller.py --course "$course"
done
```

### 3. 日志记录
```python
import logging

logging.basicConfig(
    filename='course_processing.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
```

### 4. 错误处理
```python
try:
    result = subprocess.run(cmd, check=True)
except subprocess.CalledProcessError as e:
    logging.error(f"命令执行失败: {e}")
```

---

**脚本版本**: v2.0
**最后更新**: 2026-03-18
**维护者**: 浮浮酱 ฅ'ω'ฅ
