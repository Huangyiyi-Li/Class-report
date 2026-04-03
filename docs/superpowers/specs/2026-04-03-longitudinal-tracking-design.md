# ICAS 纵向追踪能力设计文档

## 一、目标

将 ICAS 从"单次课堂分析工具"升级为"数据持续积累、按需查询生成报告"的平台化架构。

核心转变：SQLite 从"缓存层"升级为"数据仓库层"——分析结果按学校/教师/课次维度结构化存储，报告从仓库查询生成，不从文件系统凑。

## 二、约束

- PM 做 demo 阶段，本地 Python 跑通即可
- 不改动 `icas_core.py`、`icas_extended.py` 的分析逻辑
- 复用现有 ECharts + HTML 报告模板
- 小规模数据（<50 节课），SQLite 够用
- 11 次课是同一学校、不同老师/年级/学科

## 三、现状分析

### 3.1 现有数据结构

**core_cache 表**（缓存思维，key=内容哈希）：
```
cache_key(PK) | folder_name | trans_hash | design_hash | full_data(JSON) | created_at | duration_sec
```

**core_cache JSON 结构**：
```json
{
  "structure": {
    "segments": [{"phase", "type", "summary", "percentage", "duration_minutes"}],
    "overall_stats": {"total_lecture_minutes", "total_interaction_minutes", ...}
  },
  "deep": {
    "bloom_stats": [{"level", "count"}],      // 6层
    "hattie_stats": {"task_level", "process_level", "self_level"},
    "radar_scores": [85, 70, 60, 90, 80],      // 5维 0-100
    "persona": {"tag", "keywords"}
  },
  "content": {
    "knowledge_graph": {"root", "nodes", "logic"},
    "micro_moments": [...]
  },
  "report": {
    "macro_review", "logic_analysis", "student_cognition", "recommendations"
  }
}
```

**extended_cache JSON 结构**：
```json
{
  "st_analysis": {"rt", "ch", "classroom_type", "teacher_minutes", "student_minutes"},
  "qa_analysis": {"total_questions", "fourmat", "openness", "question_chains"},
  "student_analysis": {"student_thinking", "student_response", "teacher_feedback"},
  "word_freq": [{"word", "count"}]
}
```

### 3.2 纵向对比可用的数值型字段

| 字段 | 路径 | 类型 | 纵向意义 |
|------|------|------|---------|
| 五维雷达 | `deep.radar_scores` | `[int×5]` | 教学能力变化曲线 |
| Bloom分布 | `deep.bloom_stats` | `[{level,count}]` | 高阶思维占比趋势 |
| Hattie反馈 | `deep.hattie_stats` | `{int×3}` | 反馈质量演进 |
| 时间分配 | `structure.overall_stats` | `{float×4}` | 讲授vs互动比例变化 |
| Rt/Ch | `st_analysis.rt/ch` | `float` | 师生行为模式变化 |
| 4MAT | `qa_analysis.fourmat` | `{int×4}` | 高阶问题占比变化 |
| 开放性 | `qa_analysis.openness` | `{open,closed}` | 开放性问题比例 |
| 学生应答 | `student_analysis.student_response` | `{pct}` | 学生主动性变化 |

## 四、设计方案

### 4.1 数据库 Schema（新增 3 张维度表）

```sql
-- 学校表
CREATE TABLE IF NOT EXISTS schools (
    school_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 教师表
CREATE TABLE IF NOT EXISTS teachers (
    teacher_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    school_id   INTEGER REFERENCES schools(school_id),
    subject     TEXT,           -- 学科
    grade       TEXT,           -- 年级
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(name, school_id)
);

-- 课次表（一次分析的元数据）
CREATE TABLE IF NOT EXISTS lessons (
    lesson_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    teacher_id    INTEGER REFERENCES teachers(teacher_id),
    school_id     INTEGER REFERENCES schools(school_id),
    folder_name   TEXT,           -- 原始文件夹名
    lesson_date   DATE,           -- 授课日期
    lesson_title  TEXT,           -- 课题名
    subject       TEXT,           -- 学科（可覆盖教师默认值）
    grade         TEXT,           -- 年级
    -- 关联分析结果
    core_cache_key    TEXT,       -- 关联 core_cache
    extended_cache_key TEXT,      -- 关联 extended_cache
    -- 提取的关键指标（冗余存储，加速查询）
    radar_logic       REAL,
    radar_interaction REAL,
    radar_questioning REAL,
    radar_support     REAL,
    radar_management  REAL,
    rt_value          REAL,
    ch_value          REAL,
    bloom_memory      INTEGER,
    bloom_understand  INTEGER,
    bloom_apply       INTEGER,
    bloom_analyze     INTEGER,
    bloom_evaluate    INTEGER,
    bloom_create      INTEGER,
    hattie_task       INTEGER,
    hattie_process    INTEGER,
    hattie_self       INTEGER,
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**设计决策：**
- `lessons` 表冗余存储关键数值指标（radar_scores 展开为 5 列、bloom 展开为 6 列），避免每次查询都解析 JSON
- `core_cache_key` / `extended_cache_key` 保留对原始缓存表的引用，需要完整数据时回查
- 原有 `core_cache` 和 `extended_cache` 表完全不动，继续承担"防重复分析"的缓存职责

### 4.2 新增模块

#### `icas_warehouse.py` — 数据仓库层（约 250 行）

职责：
1. **Schema 管理**：`init_schema()` — 创建新表，对已有数据库用 ALTER TABLE 加字段
2. **数据写入**：`save_lesson(school, teacher, date, subject, grade, core_data, ext_data)` — 从分析结果提取指标写入 lessons 表
3. **数据查询**：
   - `get_lessons(school_id=None, teacher_id=None)` — 按维度筛选课次列表
   - `get_growth_data(teacher_id)` — 某教师的时间序列数据（radar/bloom/rt/ch 趋势）
   - `get_school_overview(school_id)` — 学校级汇总（教师数、课次数、各维度均值）
   - `get_teacher_comparison(school_id, subject=None)` — 同校教师横向对比
4. **维度管理**：`ensure_school(name)` / `ensure_teacher(name, school, subject, grade)` — 自动创建或查询维度记录

#### `icas_report_growth.py` — 纵向报告生成（约 400 行）

职责：
1. `generate_growth_html(teacher_id)` — 教师成长报告
2. `generate_school_overview_html(school_id)` — 学校概览报告
3. `generate_comparison_html(teacher_ids)` — 教师对比报告

报告复用现有 ECharts + HTML 模板框架，新增图表类型：
- 折线图（五维雷达趋势）
- 堆叠柱状图（Bloom 分布变化）
- 双轴折线图（Rt/Ch 趋势）
- 雷达图对比（多教师横向对比）

#### 改动 `auto_analyze_simple.py`（约 20 行变更）

在 `analyze_folder()` 末尾增加：
```python
# 新增：分析完成后写入数据仓库
from icas_warehouse import save_lesson_result
save_lesson_result(
    school=args.school or "默认学校",
    teacher=args.teacher or folder_name,
    lesson_date=args.date,
    subject=args.subject,
    grade=args.grade,
    core_data=report_data,
    ext_data=ext_data,
    folder_name=folder_name
)
```

新增 CLI 参数：`--school`, `--teacher`, `--date`, `--subject`, `--grade`

新增命令：`--growth <teacher_id>` 触发生长报告生成

#### 新增 `backfill_lessons.py` — 一次性数据回填脚本（约 80 行）

遍历 11 个课次文件夹，从 `icas_cache.db` 中读取已有分析结果，按用户输入的元数据（学校/教师/日期/学科/年级）写入 lessons 表。对于缓存中没有的课次，提示用户先跑一次分析。

### 4.3 数据流

```
                   ┌──────────────────────────────────┐
                   │         现有流程（不动）            │
                   │                                    │
  录音文件 ──→ ASR转录 ──→ icas_core分析 ──→ core_cache  │
                   │      ──→ icas_extended  ──→ ext_cache │
                   │      ──→ icas_report ──→ 单次HTML     │
                   └──────────┬───────────────────────────┘
                              │
                   ┌──────────▼───────────────────────────┐
                   │         新增流程                       │
                   │                                        │
                   │  save_lesson_result()                  │
                   │    ├─ ensure_school/teacher            │
                   │    ├─ 提取 radar/bloom/rt/ch 等指标    │
                   │    └─ 写入 lessons 表                  │
                   │                                        │
                   │  查询时：                               │
                   │    get_growth_data(teacher_id)         │
                   │    → 从 lessons 表按时间序列查询         │
                   │    → 需要完整数据时回查 core_cache       │
                   │                                        │
                   │  报告生成：                             │
                   │    generate_growth_html()              │
                   │    → ECharts 折线图/堆叠柱状图 HTML     │
                   └────────────────────────────────────────┘
```

### 4.4 Demo 展示场景

**场景一：教师成长曲线**
- 输入：某个教师的 ID
- 输出：五维雷达趋势折线图 + Bloom 分布堆叠柱状图 + Rt/Ch 行为趋势
- 数据：从 lessons 表查询该教师所有课次的 radar_logic 等字段

**场景二：学校教学全景**
- 输入：学校 ID
- 输出：全校教师列表 + 各教师五维雷达均值 + 各学科对比
- 数据：从 lessons 表聚合查询

**场景三：AI 改进闭环（增量）**
- 输入：教师 ID
- 输出：对比第 N 次课的建议与第 N+1 次课的分析，AI 判断改进情况
- 数据：回查 core_cache 的 report.recommendations + 下一次课的 full_data，调用一次大模型

## 五、文件改动清单

| 文件 | 操作 | 行数估算 |
|------|------|---------|
| `icas_warehouse.py` | **新增** | ~250 行 |
| `icas_report_growth.py` | **新增** | ~400 行 |
| `backfill_lessons.py` | **新增** | ~80 行 |
| `auto_analyze_simple.py` | **修改** | ~20 行新增 |
| `icas_core.py` | **不动** | — |
| `icas_extended.py` | **不动** | — |
| `icas_cache.py` | **不动** | — |
| `icas_report_extended.py` | **不动** | — |

## 六、实施顺序

1. `icas_warehouse.py` — 数据层（schema + 写入 + 查询）
2. `backfill_lessons.py` — 回填已有数据（手动输入元数据）
3. `icas_report_growth.py` — 报告可视化
4. `auto_analyze_simple.py` — 接入数据仓库，新分析自动入库
5. 验证：对 11 次课已有数据生成成长报告，确认数据正确

## 七、风险与应对

| 风险 | 应对 |
|------|------|
| 11 次课并非同一教师，成长曲线可能缺乏连续性 | Demo 阶段按"同校不同教师"展示横向对比，不强行展示单人成长 |
| 现有缓存只存了 1 条记录（第十一次课），大部分课次未缓存 | backfill 脚本检测缓存缺失时提示用户先跑分析 |
| SQLite 并发写入 | demo 阶段单用户，无并发问题 |
