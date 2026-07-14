# ICAS 智能课堂分析系统

基于大模型的课堂录音分析工具集，支持课堂诊断、扩展分析、学科差异化评课、教师分层和三视角报告。

这个仓库按“并列版本”维护，不按“线性升级”维护。不同版本对应不同结果形态，最终通过统一入口手动选择运行。

## Windows 录音采集客户端

Windows 10/11 录音客户端位于 `electron-recorder/`。当前仍处于开发和真机排障阶段，尚未达到用户试用条件。

新开发电脑或新 Codex 任务请先阅读 [Windows 客户端文档入口](docs/windows-recorder/README.md)。其中记录了产品决策、当前事故、Windows 真机复现步骤、构建发布流程和接续提示词。

## 快速开始

```bash
# 1) 安装依赖
pip install -r requirements.txt

# 2) 配置 API Key（Windows PowerShell）
$env:ARK_API_KEY="你的火山/ARK API Key"

# 3) 查看可用版本
python run_version.py --list

# 4) 交互式选择版本
python run_version.py
```

也可以直接双击 [启动版本选择器.bat](启动版本选择器.bat)。

## 版本选择

当前保留的版本定义：

| 版本 ID | 定义 | 当前入口 |
| --- | --- | --- |
| `v1.0` | 单次报告，当前实际运行版本 | `versions/v1_0/auto_analyze_simple.py` |
| `v1.1.a` | 单次报告，尝试扩充内容但未校验 | `src/auto_analyze_simple.py` |
| `v1.1.b` | 单次报告，强化学科区分但未校验 | `v3.0/auto_analyze_v3.py` |
| `v1.2.0` | 总览版本 demo | `versions/v1_2_0/run.py` |

示例：

```bash
python run_version.py v1.0 "课程文件夹"
python run_version.py v1.1.a "课程文件夹"
python run_version.py v1.1.b "课程文件夹" --subject 语文 --lesson-type 新课
python run_version.py v1.2.0 "课次数据目录"
```

更详细的版本说明见 [versions/README.md](versions/README.md)，按结果看的样本说明见 [docs/按结果选版本.md](docs/按结果选版本.md)。

## 环境变量

项目不再在代码里写死 API Key。请使用环境变量：

```bash
ARK_API_KEY=你的 API Key
ARK_MODEL_NAME=ep-20251223144447-7946z
ARK_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
```

可参考 [.env.example](.env.example)。

## 项目结构

```text
ICAS_AI/
├── src/                 # 主版本线：Web / 目录分析 / 核心分析模块
├── v3.0/                # 学科增强版本线
├── versions/            # 版本清单与说明
├── docs/                # 设计、PRD、技术说明
├── examples/            # 示例输入
├── data/                # 运行期 SQLite 数据（自动创建，不提交）
├── run_version.py       # 统一版本选择入口
├── 启动版本选择器.bat
└── requirements.txt
```

## 常用命令

```bash
# 列出可用学科
python v3.0/auto_analyze_v3.py --list-subjects

# 列出可用课型
python v3.0/auto_analyze_v3.py --list-lesson-types

# 启动 Web 版
streamlit run src/app.py
```

## 三版本验证

如果你是从 GitHub 拉下项目后想直接验证三个单次报告版本，可以走这个入口：

```bash
pip install -r requirements.txt
streamlit run src/report_validator_app.py
```

或直接双击 [启动三版本验证器.bat](启动三版本验证器.bat)。

验证器会要求你：

- 填入自己的 API Key
- 上传 1 个课堂 Excel
- 上传 1 个教案文件
- 为 `v1.1.b` 选择学科和课型

然后顺序输出：

- `v1.0`
- `v1.1.a`
- `v1.1.b`

三版报告会落在仓库下的 `runs/<时间戳>_.../` 目录中，并可直接打包下载。
