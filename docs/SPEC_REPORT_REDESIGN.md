# ICAS 课堂分析报告重新设计 - 实现规格书

## 零、实现进度追踪

### 已完成的组件（可直接复用）

| 组件 | 位置 | 说明 |
|------|------|------|
| `_s()` 安全取值函数 | `icas_report_extended.py:12-21` | 已有，可直接用 |
| `_build_css()` | `icas_report_extended.py:24-411` | Agent 1 完成，CSS完整 |
| `_build_sidebar()` | `icas_report_extended.py:414-629` | Agent 1 完成，含JS交互 |
| `_build_header_html()` | `report_sections.py:55-147` | Agent 2 完成，需适配CSS类名 |
| `_build_group_a_html()` | `report_sections.py:154-219` | Agent 2 完成，需适配CSS类名 |
| `_build_group_b_html()` | `report_sections.py:226-479` | Agent 2 完成，需适配CSS类名 |

### 待实现的组件

| 组件 | 说明 | 参考数据来源 |
|------|------|------|
| `_build_group_c_html()` | 6个section: radar/bloom/hattie/chains/fourmat/interaction | 见下方规格 |
| `_build_group_d_html()` | 4个section: thinking/response/feedback-detail/cognition | 见下方规格 |
| `_build_charts_js()` | 12个ECharts图表初始化JS | 复用旧代码 `icas_report_extended.py:867-954` |
| `generate_combined_html()` | 组装函数，拼合所有组件返回完整HTML | — |
| `auto_analyze_simple.py` 更新 | 改3行import和调用 | — |

### 实现方式

在 `icas_report_extended.py` 中：
1. 保留已有的 `_s()`, `_build_css()`, `_build_sidebar()` 不动
2. 删除旧的 `inject_extended_into_html()` 和 `generate_extended_sections()` 
3. 从 `report_sections.py` 复制 `_build_header_html`, `_build_group_a_html`, `_build_group_b_html` 并适配
4. 新增 `_build_group_c_html()`, `_build_group_d_html()`, `_build_charts_js()`
5. 新增 `generate_combined_html()` 组装函数

---

## 一、目标概述

将目前两段拼接式报告（原始4 Agent + 扩展9维分析）重写为**一份视觉统一的完整报告**。

### 核心需求
1. 左侧固定导航栏 + 右侧滚动内容区
2. 用户可勾选模块，点击按钮导出自定义PDF（A4）
3. 移动端响应式适配
4. 不修改 `icas_core.py`

---

## 二、文件改动清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `icas_report_extended.py` | **完全重写** | 新函数 `generate_combined_html()` 替代旧的两个函数 |
| `auto_analyze_simple.py` | **修改调用** | 改为调用新的 `generate_combined_html()` |
| `icas_core.py` | **不动** | 保留原样 |
| `icas_extended.py` | **不动** | 保留原样 |

---

## 三、数据结构参考

### 3.1 `full_data` — 由 `icas_core.py` 的 `analyze_classroom()` 返回

```python
full_data = {
    'structure': {
        'segments': [
            {'phase': '阶段名', 'type': 'Lecture|Interaction|Practice|Other',
             'summary': '摘要', 'percentage': 15, 'duration_minutes': 5}
        ],
        'overall_stats': {
            'total_lecture_minutes': 20,
            'total_interaction_minutes': 10,
            'total_practice_minutes': 10,
            'total_other_minutes': 5
        }
    },
    'deep': {
        'bloom_stats': [{'level': '记忆', 'count': 5}, ...],  # 6个级别
        'hattie_stats': {'task_level': 5, 'process_level': 3, 'self_level': 2},
        'radar_scores': [85, 70, 60, 90, 80],  # 5个分数 (逻辑/互动/提问/支持/管理)
        'persona': {'tag': '循循善诱型导师', 'keywords': ['思考', '逻辑', ...]}
    },
    'content': {
        'knowledge_graph': {'root': '主题', 'nodes': ['A', 'B'], 'logic': '关系描述'},
        'checklist': {
            'review': True/False,
            'homework': True/False,
            'summary': True/False,
            'homework_detail': '作业详情文字'
        },
        'micro_moments': [
            {'title': '片段标题', 'dialogue': '师:...\n生:...', 'analysis': '点评文字'}
        ]
    },
    'report': {
        'macro_review': '宏观综述长文本(Markdown)',
        'logic_analysis': '逻辑分析长文本(Markdown)',
        'student_cognition': '认知诊断长文本(Markdown)',
        'recommendations': [
            {'title': '建议标题', 'content': '建议内容(Markdown)'}
        ]
    }
}
```

### 3.2 `extended_data` — 由 `icas_extended.py` 的 `analyze_extended()` 返回

```python
extended_data = {
    'word_freq': [{'name': '词语', 'value': 15}, ...],  # top 30

    'st_analysis': {  # 可能为 None
        'teacher_minutes': 21.6,
        'student_minutes': 4.8,
        'total_minutes': 26.4,
        'rt': 0.82,
        'ch': 0.33,
        'classroom_type': '讲授型',
        'type_description': '说明文字',
        'suggestions': '改进建议',
        'per_phase': [
            {'phase': '环节名', 'teacher_pct': 85, 'student_pct': 15}
        ],
        'speech_rate': {
            'total_words': 3600,
            'speaking_minutes': 25.0,
            'words_per_minute': 144,
            'assessment': '语速评估'
        }
    },

    'qa_analysis': {  # 可能为 None
        'total_questions': 28,
        'question_chains': [
            {
                'id': 1,
                'topic': '主题',
                'thinking_type': '逻辑思维|形象思维|元认知思维|系统思维|辩证思维',
                'question_type': '平行型|收敛型|提高型|拓展型',
                'complexity': '简单情境|复杂情境|无情境',
                'questions': ['问题1', '问题2']
            }
        ],
        'fourmat': {'what': 24, 'how': 3, 'what_if': 0, 'why': 1},
        'openness': {'open': 8, 'closed': 20},
        'chain_analysis': '分析文字',
        'chain_suggestions': '建议文字'
    },

    'student_analysis': {  # 可能为 None
        'student_thinking': [
            {
                'type': '形象思维|逻辑思维|元认知思维|系统思维|辩证思维',
                'level': '全面体现|初步体现|尚未体现',
                'analysis': '分析文字',
                'suggestion': '建议文字'
            }
        ],
        'student_response': {
            'total': 15,
            'active_pct': 40,
            'passive_pct': 60,
            'length': {'short': 8, 'medium': 5, 'long': 2},
            'analysis': '分析文字',
            'suggestions': '建议文字'
        },
        'teacher_feedback': {
            'total': 20,
            'evaluative': 8,
            'directive': 5,
            'encouraging': 7,
            'analysis': '分析文字',
            'suggestions': '建议文字'
        },
        'common_phrases': [
            {'phrase': '反馈语原文', 'type': '评价性', 'context': '情境'}
        ]
    }
}
```

**重要**: `extended_data` 中所有嵌套key都可能不存在（AI返回失败时为None），必须用 `.get()` 安全访问。

---

## 四、新函数签名

### icas_report_extended.py

```python
def generate_combined_html(full_data, extended_data=None, teaching_design=None, folder_name=""):
    """
    生成完整的统一报告HTML（替代旧的 generate_ultimate_html + inject_extended_into_html）

    参数:
        full_data: analyze_classroom() 返回的分析数据 (dict)
        extended_data: analyze_extended() 返回的扩展数据 (dict or None)
        teaching_design: 教案文本 (str or None)
        folder_name: 课程文件夹名 (str)

    返回:
        str: 完整的HTML字符串
    """
```

旧的 `inject_extended_into_html` 和 `generate_extended_sections` 函数可以删除。

### auto_analyze_simple.py 调用变更

**旧代码** (删除):
```python
from icas_core import ..., generate_ultimate_html, ...
from icas_report_extended import inject_extended_into_html

# ...
html_content = generate_ultimate_html(full_data=report_data, teaching_design=teaching_design_text)
# ...
html_content = inject_extended_into_html(html_content, ext_data, folder_name=folder_name)
```

**新代码** (替换):
```python
from icas_core import analyze_classroom, read_excel_transcription, read_word_document
from icas_extended import analyze_extended
from icas_report_extended import generate_combined_html

# ...
html_content = generate_combined_html(
    full_data=report_data,
    extended_data=ext_data,
    teaching_design=teaching_design_text,
    folder_name=folder_name
)
```

注意: `generate_ultimate_html` 从 import 中移除，`inject_extended_into_html` 也从 import 中移除。

---

## 五、页面布局规格

### 5.1 整体结构

```
<body>
  <!-- 移动端汉堡按钮 -->
  <button id="sidebar-toggle" class="no-print md:hidden fixed top-4 left-4 z-50">

  <!-- 左侧固定导航栏 -->
  <aside id="sidebar" class="no-print">
    标题区
    分组checkbox区 (4组)
    全选/取消按钮
    导出PDF按钮
  </aside>

  <!-- 右侧主内容 -->
  <main id="main-content">
    报告头部
    Group A sections
    Group B sections
    Group C sections
    Group D sections
    页脚
  </main>

  <!-- 所有ECharts初始化JS -->
  <script>...</script>
</body>
```

### 5.2 侧边栏 (aside#sidebar)

- **位置**: fixed, left:0, top:0, bottom:0, width:240px
- **背景**: #1e293b (深蓝灰)
- **内容**:
  - 顶部: 图标 + "课堂分析报告" 标题 (白色文字)
  - 4个分组，每组一个折叠区:
    - **教学概况** (2项): 宏观综述, 导师建议
    - **结构与节奏** (7项): 时间分配, 知识图谱, 教学常规, 知识脚手架, S-T分析, 语速分析, 高频词汇
    - **教学策略** (6项): 五维能力, Bloom认知, Hattie反馈, 问题链, 4MAT分类, 互动切片
    - **学生与诊断** (4项): 学生思维, 学生应答, 教师反馈, 认知诊断
  - 每个 checkbox 的 value 对应 section id (如 `sec-overview`)
  - 全选/取消两个小按钮
  - 绿色醒目的"导出PDF"按钮

### 5.3 Section 卡片通用结构

```html
<section id="sec-xxx" class="section-card printable" style="--accent: #颜色值">
    <h2 class="section-title">标题文字</h2>
    <!-- 内容 -->
</section>
```

CSS:
```css
.section-card {
    background: #fff;
    border-radius: 12px;
    padding: 20px;
    margin-bottom: 20px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.08);
    border-left: 4px solid var(--accent, #6366f1);
}
.section-title {
    font-size: 1.1rem;
    font-weight: 800;
    color: #111827;
    margin-bottom: 1rem;
    padding-left: 0.75rem;
    border-left: 5px solid var(--accent, #4f46e5);
}
```

### 5.4 报告头部

- 标题: "课堂教学深度诊断书"
- 副标题: "ICAS ULTIMATE EDITION III"
- 右上角: 日期 + 教学风格tag
- 关键词pills (tag-pill 样式)
- 4个核心指标速览卡片 (grid 4列):
  - 总提问数 (`extended_data['qa_analysis']['total_questions']`)
  - 教师语速 (`extended_data['st_analysis']['speech_rate']['words_per_minute']`)
  - Rt 师生比 (`extended_data['st_analysis']['rt']`)
  - 课堂类型 (`extended_data['st_analysis']['classroom_type']`)
  - 以上extended指标可能为None，显示时默认为"--"

---

## 六、各Section详细规格

### Group A: 教学概况

| Section ID | 标题 | 边框色 | 数据来源 | 渲染方式 |
|---|---|---|---|---|
| sec-overview | 宏观教学综述 | #4f46e5 | `full_data['report']['macro_review']` | markdown.markdown(text, extensions=['nl2br']) |
| sec-recommend | 导师改进建议 | #4f46e5 | `full_data['report']['recommendations']` 列表 | 每条一个卡片: 编号圆圈+标题+markdown内容 |

如果有 teaching_design，在 sec-overview 顶部显示一个教学设计概览卡片（截取前200字）。

### Group B: 结构与节奏

| Section ID | 标题 | 边框色 | 图表 | 数据 |
|---|---|---|---|---|
| sec-time | 时间分配与教学节奏 | #6366f1 | 饼图 `time-chart` 200px | `overall_stats` 4项 |
| sec-knowledge | 知识图谱与逻辑链 | #3b82f6 | 力导向图 `kg-chart` 220px | `knowledge_graph` root+nodes |
| sec-checklist | 教学常规核查 | #6366f1 | 无 | `checklist` 3项boolean |
| sec-scaffold | 知识脚手架分析 | #818cf8 | 无 | `report['logic_analysis']` markdown |
| sec-st | S-T师生行为分析 | #10b981 | 环形图 `ext-st-pie-chart` 200px + 堆叠柱状图 `ext-st-bar-chart` 200px | `st_analysis` |
| sec-speech | 教师语速分析 | #6366f1 | 无 | `st_analysis['speech_rate']` 3个指标卡 |
| sec-wordcloud | 高频词汇分析 | #ec4899 | 词云 `ext-wordcloud-chart` 260px | `word_freq` |

**sec-time 布局**: grid 2列, 左图表右数字
**sec-knowledge 布局**: 图表 + 底部logic文字
**sec-checklist 布局**: grid 2列, 每项checkbox样式, homework占满行
**sec-st 布局**: grid 2列(饼图+柱状图) + 底部说明文字
**sec-speech 布局**: grid 3列(字/分钟, 总字数, 说话时长) + 底部评估文字

### Group C: 教学策略

| Section ID | 标题 | 边框色 | 图表 | 数据 |
|---|---|---|---|---|
| sec-radar | 五维能力雷达 | #6366f1 | 雷达图 `radar-chart` 250px | `radar_scores` |
| sec-bloom | 认知激发深度(Bloom) | #8b5cf6 | 柱状图 `bloom-chart` 250px | `bloom_stats` |
| sec-hattie | 反馈质量分布(Hattie) | #ec4899 | 环形图 `hattie-chart` 250px | `hattie_stats` |
| sec-chains | 问题链分析 | #8b5cf6 | 无 | `question_chains` |
| sec-fourmat | 问题分类统计 | #6366f1 | 环形图 `ext-fourmat-chart` + `ext-openness-chart` 各200px | `fourmat` + `openness` |
| sec-interaction | 关键互动切片 | #4f46e5 | 无 | `micro_moments` |

**sec-chains 布局**:
- 每个chain一个卡片(grid 2列)
- 顶部: 思维类型彩色标签 + 主题
- 中部: 问题类型badge + 复杂度badge
- 底部: 问题列表(ul)
- 思维类型颜色: 逻辑思维=#6366f1, 形象思维=#ec4899, 元认知思维=#10b981, 系统思维=#f59e0b, 辩证思维=#8b5cf6
- 最底部: chain_analysis + chain_suggestions 文字

**sec-interaction 布局**:
- 每个切片一个白底卡片
- 标题(indigo粗体) + 对话区(灰色背景等宽字体, whitespace-pre-wrap) + 导师点评

### Group D: 学生与诊断

| Section ID | 标题 | 边框色 | 图表 | 数据 |
|---|---|---|---|---|
| sec-thinking | 学生思维五维分析 | #10b981 | 无 | `student_thinking` 列表 |
| sec-response | 学生应答分析 | #f59e0b | 柱状图 `ext-response-chart` 200px | `student_response` |
| sec-feedback-detail | 教师反馈分析 | #ec4899 | 环形图 `ext-feedback-chart` 200px | `teacher_feedback` + `common_phrases` |
| sec-cognition | 学生认知诊断 | #10b981 | 无 | `report['student_cognition']` markdown |

**sec-thinking 布局**:
- 每个维度一个卡片, 背景色随级别变化
- 级别颜色: 全面体现=#10b981(绿), 初步体现=#f59e0b(黄), 尚未体现=#ef4444(红)
- 背景色(浅): #ecfdf5, #fffbeb, #fef2f2
- 标签(右上角) + 类型名 + 分析文字 + 建议文字(蓝色)

**sec-response 布局**: grid 2列, 左图表右数字(总数, 主动%, 被动%, 分析, 建议)
**sec-feedback-detail 布局**: grid 2列(图表+数字) + 底部常用反馈语列表(左边框引用样式)

---

## 七、ECharts图表规格

所有图表在一个 `<script>` 标签中，用 IIFE `(function(){ ... })();` 包裹。

辅助函数:
```javascript
function ic(id, opt) {
    var d = document.getElementById(id);
    if (!d) return;
    var c = echarts.init(d);
    c.setOption(opt);
}
```

在 `window.onload` 或 DOMContentLoaded 中调用所有初始化。

### 图表列表 (共12个)

1. **time-chart** - 饼图
   - 数据: 讲授(#6366f1) / 互动(#ec4899) / 练习(#10b981) / 其他(#9ca3af)
   - radius: '70%', center: ['50%','40%']

2. **kg-chart** - 力导向图
   - root节点 symbolSize:60, color:#4f46e5
   - 子节点 symbolSize:40, color:#3b82f6
   - force: repulsion:100, edgeLength:50

3. **radar-chart** - 雷达图
   - 5个indicator: 逻辑/互动/提问/支持/管理, max:100
   - radius:'65%', splitNumber:3

4. **bloom-chart** - 柱状图
   - color:#6366f1, borderRadius:[3,3,0,0]

5. **hattie-chart** - 环形图
   - radius:['40%','65%'], center:['50%','40%']
   - label: show:false

6. **ext-wordcloud-chart** - 词云 (需 echarts-wordcloud CDN)
   - sizeRange:[14,50], rotationRange:[-30,30]
   - 随机颜色: #4f46e5/#6366f1/#818cf8/#ec4899/#f43f5e/#10b981/#f59e0b/#8b5cf6

7. **ext-st-pie-chart** - 环形图
   - 教师(#6366f1) / 学生(#ec4899)
   - radius:['35%','60%']

8. **ext-st-bar-chart** - 堆叠柱状图
   - stack:'total'
   - X轴: 各环节名, Y轴: 百分比

9. **ext-fourmat-chart** - 环形图
   - 是何(#6366f1) / 如何(#10b981) / 若何(#f59e0b) / 为何(#ec4899)

10. **ext-openness-chart** - 环形图
    - 开放性(#10b981) / 封闭性(#9ca3af)

11. **ext-response-chart** - 柱状图
    - X轴: ['短(1-5字)','中(6-15字)','长(16+字)']
    - color: #f59e0b

12. **ext-feedback-chart** - 环形图
    - 评价性(#6366f1) / 指导性(#10b981) / 鼓励性(#f59e0b)

### CDN引入 (在<head>中)

```html
<script src="https://cdn.tailwindcss.com"></script>
<script src="https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/echarts-wordcloud@2.1.0/dist/echarts-wordcloud.min.js"></script>
```

---

## 八、CSS规格

### 关键样式

```css
/* 基础 */
body { font-family: "Microsoft YaHei", sans-serif; background: #f3f4f6; }

/* 侧边栏 */
#sidebar {
    position: fixed; left: 0; top: 0; bottom: 0;
    width: 240px; background: #1e293b;
    overflow-y: auto; z-index: 40;
    transition: transform 0.3s ease;
}

/* 主内容 */
#main-content { margin-left: 240px; padding: 24px; max-width: 900px; margin-right: auto; }

/* 移动端 */
@media (max-width: 768px) {
    #sidebar { transform: translateX(-100%); }
    #sidebar.open { transform: translateX(0); }
    #main-content { margin-left: 0; padding: 16px; }
    #sidebar-toggle { display: block !important; }
}

/* 打印 */
@media print {
    .no-print { display: none !important; }
    #main-content { margin-left: 0 !important; max-width: none !important; }
    body { background: white !important; }
    .printable { page-break-inside: auto; }
    .no-print-section { display: none !important; }
    [id$="-chart"] { page-break-inside: avoid !important; }
    p, li, td { orphans: 3; widows: 3; }
}
```

### 打印控制JS逻辑

```javascript
function exportPDF() {
    // 1. 获取所有checkbox
    var checkboxes = document.querySelectorAll('.section-check');
    // 2. 未勾选的section添加 no-print-section class
    checkboxes.forEach(function(cb) {
        var sec = document.getElementById(cb.value);
        if (sec) {
            if (cb.checked) {
                sec.classList.remove('no-print-section');
            } else {
                sec.classList.add('no-print-section');
            }
        }
    });
    // 3. 触发打印
    window.print();
}

function toggleAll(checked) {
    document.querySelectorAll('.section-check').forEach(function(cb) {
        cb.checked = checked;
    });
}
```

---

## 九、侧边栏Checkbox数据

每个checkbox的 `value` 对应 section 的 `id`：

```
教学概况:
  ☑ sec-overview  宏观综述
  ☑ sec-recommend 导师建议

结构与节奏:
  ☑ sec-time      时间分配
  ☑ sec-knowledge 知识图谱
  ☑ sec-checklist 教学常规
  ☑ sec-scaffold  知识脚手架
  ☑ sec-st        S-T分析
  ☑ sec-speech    语速分析
  ☑ sec-wordcloud 高频词汇

教学策略:
  ☑ sec-radar      五维能力
  ☑ sec-bloom      Bloom认知
  ☑ sec-hattie     Hattie反馈
  ☑ sec-chains     问题链
  ☑ sec-fourmat    4MAT分类
  ☑ sec-interaction 互动切片

学生与诊断:
  ☑ sec-thinking      学生思维
  ☑ sec-response      学生应答
  ☑ sec-feedback-detail 教师反馈
  ☑ sec-cognition     认知诊断
```

所有checkbox默认勾选，class 为 `section-check`。

---

## 十、Python f-string 转义注意事项

在Python f-string中嵌入JS代码时:
- JS的 `{ }` 必须写成 `{{ }}`
- JS的模板字符串反引号不影响Python
- `json.dumps(data, ensure_ascii=False)` 用于序列化数据到JS

示例:
```python
js_code = f"""
<script>
(function(){{
    var data = {json.dumps(some_data, ensure_ascii=False)};
    console.log(data.length);
}})();
</script>
"""
```

---

## 十一、验收标准

### 功能验收
1. `generate_combined_html()` 返回完整HTML字符串，可在浏览器正常打开
2. 侧边栏显示所有19个checkbox，点击可勾选/取消
3. 点击"导出PDF"按钮触发 window.print()，未勾选的section不显示
4. 12个ECharts图表全部正常渲染（需联网加载CDN）
5. 移动端(<768px): 侧边栏默认隐藏，hamburger按钮可切换显示

### 数据验收
1. 当 `extended_data=None` 时，扩展section显示"暂无数据"而不报错
2. 当 `extended_data` 中某个子key为None时（如 `st_analysis=None`），对应section优雅降级
3. 所有 `.get()` 链安全访问，不抛 KeyError

### 兼容性验收
1. `auto_analyze_simple.py` 修改后能正常运行完整分析流程
2. 生成的HTML + PDF效果一致
3. `icas_core.py` 完全未被修改

### 测试命令
```bash
cd f:/1濮东-课堂录音/ICAS_AI
python auto_analyze_simple.py "../第十一次课0323"
```
验证: 生成1份HTML，浏览器打开后侧边栏可见、图表正常、勾选导出正常。

---

## 十二、参考：现有代码中可复用的部分

1. **ECharts配置**: `icas_core.py:520-590` 和 `icas_report_extended.py:259-346` 中的图表配置可直接复用
2. **HTML模板结构**: `icas_core.py:347-594` 中的HTML结构和样式可参考
3. **数据提取**: `icas_report_extended.py:13-21` 中的 `_s()` 安全取值函数可复用
4. **markdown渲染**: `import markdown` + `markdown.markdown(text, extensions=['nl2br'])`

---

## 十三、实现步骤（按顺序执行）

### 步骤1: 准备 `icas_report_extended.py`

当前文件 `icas_report_extended.py` 中已有以下可用组件：
- `_s()` 函数 (行12-21) — **保留**
- `_build_css()` 函数 (行24-411) — **保留**
- `_build_sidebar()` 函数 (行414-629) — **保留**
- `inject_extended_into_html()` 函数 (行632-666) — **删除**
- `generate_extended_sections()` 函数 (行669-956) — **删除，但其ECharts配置和HTML模板可复用到新函数中**

### 步骤2: 从 `report_sections.py` 复制函数

文件位置: `f:/「2026」03/新建文件夹/report_sections.py`

需要复制到 `icas_report_extended.py` 的函数:
- `_safe_get()` — 与 `_s()` 功能类似，保留其中一个即可（推荐 `_safe_get` 更灵活）
- `_md()` — markdown渲染
- `_fmt_minutes()` — 分钟格式化
- `_build_header_html()` — 报告头部
- `_build_group_a_html()` — 教学概况
- `_build_group_b_html()` — 结构与节奏

**注意**: 复制后需适配：
- `_build_header_html` 中使用了 FontAwesome 图标 (`<i class="fa-xxx">`)，需在HTML `<head>` 中加入 FontAwesome CDN
- `_build_group_b_html` 中的 `sec-checklist` 读取路径是 `structure.checklist` 而非 `content.checklist`，需修正为 `content.checklist`（与 `icas_core.py` 的数据结构一致）
- 侧边栏checkbox的 `data-section` 属性需匹配section id

### 步骤3: 新增 `_build_group_c_html(full_data, extended_data)`

需要生成的6个section：

**sec-radar**: 五维能力雷达图
```python
# 数据: full_data['deep']['radar_scores'] — [85,70,60,90,80]
# 图表容器: <div id="radar-chart" style="width:100%;height:250px;"></div>
# 参考现有代码: icas_core.py:534-547
```

**sec-bloom**: Bloom认知层次柱状图
```python
# 数据: full_data['deep']['bloom_stats'] — [{'level':'记忆','count':5}, ...]
# 图表容器: <div id="bloom-chart" style="width:100%;height:250px;"></div>
# 参考现有代码: icas_core.py:549-555
```

**sec-hattie**: Hattie反馈质量环形图
```python
# 数据: full_data['deep']['hattie_stats'] — {task_level:5, process_level:3, self_level:2}
# 图表容器: <div id="hattie-chart" style="width:100%;height:250px;"></div>
# 参考现有代码: icas_core.py:557-570
```

**sec-chains**: 问题链分析（扩展数据）
```python
# 数据: extended_data['qa_analysis']['question_chains'] — [{id,topic,thinking_type,question_type,complexity,questions}]
# 无图表，纯HTML卡片
# 参考现有代码: icas_report_extended.py:708-724 (chain_cards生成逻辑)
# 思维类型颜色映射:
thinking_colors = {"逻辑思维":"#6366f1","形象思维":"#ec4899","元认知思维":"#10b981","系统思维":"#f59e0b","辩证思维":"#8b5cf6"}
# 每个chain: 彩色标签 + 主题 + 类型/复杂度badge + 问题列表
# 底部: chain_analysis + chain_suggestions
```

**sec-fourmat**: 4MAT+开放性双环形图（扩展数据）
```python
# 两个图表容器:
# <div id="ext-fourmat-chart" style="width:100%;height:200px;"></div>
# <div id="ext-openness-chart" style="width:100%;height:200px;"></div>
# 数据: extended_data['qa_analysis']['fourmat'] + ['openness']
# 参考现有代码: icas_report_extended.py:909-931
```

**sec-interaction**: 关键互动切片
```python
# 数据: full_data['content']['micro_moments'] — [{title, dialogue, analysis}]
# 无图表，纯HTML
# 参考现有代码: icas_core.py:311-321 (micro_html生成逻辑)
# 每个切片: 标题(indigo粗体) + 对话区(灰色背景等宽字体) + 导师点评
```

### 步骤4: 新增 `_build_group_d_html(full_data, extended_data)`

需要生成的4个section：

**sec-thinking**: 学生思维五维（扩展数据）
```python
# 数据: extended_data['student_analysis']['student_thinking'] — [{type,level,analysis,suggestion}]
# 无图表，纯HTML彩色卡片
# 参考现有代码: icas_report_extended.py:727-740 (thinking_cards)
# 级别颜色:
level_colors = {"全面体现":"#10b981","初步体现":"#f59e0b","尚未体现":"#ef4444"}
level_bg = {"全面体现":"#ecfdf5","初步体现":"#fffbeb","尚未体现":"#fef2f2"}
```

**sec-response**: 学生应答柱状图（扩展数据）
```python
# 数据: extended_data['student_analysis']['student_response']
# 图表容器: <div id="ext-response-chart" style="width:100%;height:200px;"></div>
# 参考现有代码: icas_report_extended.py:934-940
# 布局: grid 2列，左图表右数字
```

**sec-feedback-detail**: 教师反馈环形图（扩展数据）
```python
# 数据: extended_data['student_analysis']['teacher_feedback'] + ['common_phrases']
# 图表容器: <div id="ext-feedback-chart" style="width:100%;height:200px;"></div>
# 参考现有代码: icas_report_extended.py:942-953 (图表) + 744-749 (反馈语)
# 布局: grid 2列(图表+数字) + 底部常用反馈语列表
```

**sec-cognition**: 学生认知诊断
```python
# 数据: full_data['report']['student_cognition'] — Markdown字符串
# 用 markdown.markdown() 渲染
```

### 步骤5: 新增 `_build_charts_js(full_data, extended_data)`

返回 `<script>` 标签字符串，包含12个ECharts图表初始化。

辅助函数:
```javascript
function ic(id, opt) {
    var d = document.getElementById(id);
    if (!d) return;
    var c = echarts.init(d);
    c.setOption(opt);
}
```

**图表完整配置** — 直接复用现有代码中的ECharts配置，替换数据源:

1. **time-chart** — 来自 `icas_core.py:573-589`
2. **kg-chart** — 来自 `icas_core.py:523-530`
3. **radar-chart** — 来自 `icas_core.py:534-547`
4. **bloom-chart** — 来自 `icas_core.py:549-555`
5. **hattie-chart** — 来自 `icas_core.py:557-570`
6. **ext-wordcloud-chart** — 来自 `icas_report_extended.py:877-883`
7. **ext-st-pie-chart** — 来自 `icas_report_extended.py:887-895`
8. **ext-st-bar-chart** — 来自 `icas_report_extended.py:898-907`
9. **ext-fourmat-chart** — 来自 `icas_report_extended.py:909-920`
10. **ext-openness-chart** — 来自 `icas_report_extended.py:922-931`
11. **ext-response-chart** — 来自 `icas_report_extended.py:934-940`
12. **ext-feedback-chart** — 来自 `icas_report_extended.py:942-953`

所有图表在 `window.onload` 中初始化，用 IIFE 包裹。

### 步骤6: 新增 `generate_combined_html()` 组装函数

```python
def generate_combined_html(full_data, extended_data=None, teaching_design=None, folder_name=""):
    """生成完整的统一报告HTML"""
    css = _build_css()
    sidebar = _build_sidebar()
    header = _build_header_html(full_data, folder_name, extended_data)
    group_a = _build_group_a_html(full_data, teaching_design)
    group_b = _build_group_b_html(full_data, extended_data)
    group_c = _build_group_c_html(full_data, extended_data)
    group_d = _build_group_d_html(full_data, extended_data)
    charts_js = _build_charts_js(full_data, extended_data)

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>课堂分析报告 - {folder_name}</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/echarts-wordcloud@2.1.0/dist/echarts-wordcloud.min.js"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css">
    {css}
</head>
<body>
    {sidebar}
    <main class="main-content" id="main-content">
        {header}
        {group_a}
        {group_b}
        {group_c}
        {group_d}
        <footer class="text-center text-xs text-gray-400 mt-8 py-4 no-print">
            Generated by ICAS Ultimate System III (Powered by AI)
        </footer>
    </main>
    {charts_js}
</body>
</html>"""
```

### 步骤7: 更新 `auto_analyze_simple.py`

修改 imports:
```python
# 删除:
from icas_core import ..., generate_ultimate_html, ...
from icas_report_extended import inject_extended_into_html

# 替换为:
from icas_core import analyze_classroom, read_excel_transcription, read_word_document
from icas_extended import analyze_extended
from icas_report_extended import generate_combined_html
```

修改 `analyze_folder()` 函数中报告生成部分（约行168-198），替换为:
```python
# 生成统一报告
html_content = generate_combined_html(
    full_data=report_data,
    extended_data=ext_data,
    teaching_design=teaching_design_text,
    folder_name=folder_name
)
with open(html_path, 'w', encoding='utf-8') as f:
    f.write(html_content)
```

---

## 十四、关键注意事项

1. **Python f-string中JS花括号转义**: `{{` 和 `}}`
2. **数据安全访问**: 所有 `extended_data` 的嵌套访问必须用 `.get()` 或 `_safe_get()` / `_s()`
3. **FontAwesome CDN**: header和section标题中使用了FontAwesome图标，需在head中引入
4. **sidebar checkbox的 `data-section` 属性**必须与section的 `id` 完全一致
5. **ECharts容器**: 只放 `<div id="xxx" style="width:100%;height:Npx;"></div>`，不直接写JS
6. **所有JS在一个 `<script>` 标签中**，在 `window.onload` 中初始化全部图表
