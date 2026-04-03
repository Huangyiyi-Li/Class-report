# 课堂录音分析自动化技能 - 使用指南

## 🎯 技能概述

浮浮酱已经为主人创建了一个全新的自动化技能,可以一键完成课堂录音的AI分析,再也不用手动操作Streamlit界面啦！o(*￣︶￣*)o

## 📁 新增文件

```
ICAS_AI/
├── icas_core.py              # 核心分析模块(从app.py提取)
├── analyze_classroom.py      # 命令行自动化脚本
└── .claude/skills/课堂录音分析/
    └── SKILL.md              # 技能配置文件
```

## 🚀 快速开始

### 方式1: 分析文本转录文件

```bash
python analyze_classroom.py -t transcript.txt
```

### 方式2: 分析Excel录音文件(自动读取F列)

```bash
python analyze_classroom.py -e recording.xlsx
```

### 方式3: 分析录音+教案对比(推荐!)

```bash
python analyze_classroom.py -e recording.xlsx -d lesson_plan.docx
```

### 方式4: 指定输出文件名

```bash
python analyze_classroom.py -t transcript.txt -o my_report.html
```

### 方式5: 不自动打开浏览器

```bash
python analyze_classroom.py -t transcript.txt --no-browser
```

## 📋 命令行参数说明

| 参数 | 说明 | 必需 |
|------|------|------|
| `-t, --transcript` | 录音转录文本文件(.txt) | 录音输入二选一 |
| `-e, --excel` | 录音Excel文件(.xlsx/.xls,读取F列) | 录音输入二选一 |
| `-d, --design` | 教学设计/教案文件(.docx/.txt) | 可选 |
| `-o, --output` | 输出HTML文件路径 | 可选 |
| `--no-browser` | 不自动打开浏览器 | 可选 |

## 🔄 与原版app.py的对比

### 原版流程(手动)
1. 运行 `启动应用.bat`
2. 在浏览器打开Streamlit界面
3. 手动上传Excel/粘贴文本
4. 手动上传教案/粘贴教案
5. 点击"启动深度诊断"按钮
6. 等待分析完成
7. 在浏览器查看报告
8. 手动点击打印/另存为PDF

### 新版流程(自动化)
```bash
# 一条命令搞定!
python analyze_classroom.py -e recording.xlsx -d lesson_plan.docx
```

自动完成:
- ✅ 读取录音文件
- ✅ 读取教案文件
- ✅ 执行AI分析
- ✅ 生成HTML报告
- ✅ 在浏览器打开报告
- ✅ 直接打印为PDF

## 💡 使用技巧

### 技巧1: 批量分析多个录音
创建批处理脚本 `batch_analyze.bat`:
```batch
@echo off
python analyze_classroom.py -e class1.xlsx -o report1.html --no-browser
python analyze_classroom.py -e class2.xlsx -o report2.html --no-browser
python analyze_classroom.py -e class3.xlsx -o report3.html --no-browser
echo 所有分析完成!
pause
```

### 技巧2: 直接分析Excel F列
```bash
# 最简单的方式 - 只需提供Excel文件
python analyze_classroom.py -e 录音文件.xlsx
```

### 技巧3: 对比教学设计
```bash
# 提供教案可以获得"教学设计契合度评价"
python analyze_classroom.py -e recording.xlsx -d lesson_plan.docx
```

## 📊 报告内容

生成的HTML报告包含:

✨ **宏观分析**
- 教学风格画像
- 关键词提取
- 宏观综述
- 教学设计契合度评价(如提供教案)

📈 **数据可视化**
- 时间分配饼图
- 五维能力雷达图
- 知识图谱
- Bloom认知层次柱状图
- Hattie反馈质量饼图

🎯 **深度分析**
- 知识脚手架搭建分析
- 关键互动切片(Micro-Teaching)
- 学生认知诊断
- 导师改进建议

## ⚙️ 技术架构

```
analyze_classroom.py (命令行入口)
    ↓
icas_core.py (核心分析逻辑)
    ↓
火山引擎 Doubao AI (深度分析)
    ↓
generate_ultimate_html() (HTML报告生成)
    ↓
浏览器打开 + PDF导出
```

## 🛡️ 错误处理

脚本包含完善的错误处理:

- ✅ 文件不存在检测
- ✅ 文件读取错误处理
- ✅ API调用失败捕获
- ✅ JSON解析错误处理
- ✅ 详细的错误提示

## 📝 示例输出

```
============================================================
              🚀 ICAS 课堂录音分析系统
============================================================

📂 正在读取Excel文件: recording.xlsx
✅ 成功从F列读取 15234 个字符

📂 正在读取教学设计文件: lesson_plan.docx
✅ 成功读取教学设计 3456 个字符

⏳⏳⏳⏳⏳⏳⏳⏳⏳⏳⏳⏳⏳⏳⏳⏳⏳⏳⏳⏳⏳⏳⏳⏳⏳
            开始AI深度分析...
⏳⏳⏳⏳⏳⏳⏳⏳⏳⏳⏳⏳⏳⏳⏳⏳⏳⏳⏳⏳⏳⏳⏳⏳⏳

⏳ Agent B: 梳理教学脉络与时间分配...
⏳ Agent Deep: 计算五维雷达与风格...
⏳ Agent Content: 显微镜式扫描互动切片...
⏳ Agent F: 撰写万字长文诊断书...
✅ 深度诊断完成!

⏱️  分析完成! 耗时: 35.42 秒

📄 正在生成HTML报告...
✅ 报告已保存: C:\...\ICAS_Report_20260113_1425.html

🌐 正在打开浏览器...
✅ 已在浏览器中打开报告

============================================================
                  ✨ 分析完成!
============================================================

💡 提示:
   - 在浏览器中按 Ctrl+P 可将报告另存为PDF
   - HTML报告包含完整的交互式图表
   - 所有数据已自动保存
```

## 🎉 总结

现在主人可以通过简单的命令行操作,一键完成课堂录音的AI分析,完全不需要手动操作Streamlit界面了喵～ ฅ'ω'ฅ

浮浮酱已经帮主人把复杂的流程简化成了一条命令,真是太高效了呢！(*^▽^*)

---

**创建者**: 浮浮酱
**创建日期**: 2026-01-13
**版本**: v1.0
