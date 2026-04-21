# 版本说明

这个仓库按“并列版本”组织，不按“线性升级”组织。

当前版本定义已经按实际结果回填：

| 版本 ID | 定义 | 当前入口 |
| --- | --- | --- |
| `v1.0` | 单次报告，当前实际运行版本 | `versions/v1_0/auto_analyze_simple.py` |
| `v1.1.a` | 单次报告，尝试扩充内容但未校验 | `src/auto_analyze_simple.py` |
| `v1.1.b` | 单次报告，强化学科区分但未校验 | `v3.0/auto_analyze_v3.py` |
| `v1.2.0` | 总览版本 demo | `versions/v1_2_0/run.py` |

## 使用方式

```bash
python run_version.py --list
python run_version.py
python run_version.py v1.0 "课程目录"
python run_version.py v1.1.a "课程目录"
python run_version.py v1.1.b "课程目录" --subject 语文 --lesson-type 新课
python run_version.py v1.2.0 "课次数据目录"
```
