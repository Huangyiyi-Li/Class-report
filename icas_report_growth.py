# -*- coding: utf-8 -*-
"""
ICAS 纵向追踪报告生成模块

生成教师成长曲线、学校教学概览、教师横向对比的 HTML 报告。
复用 icas_report_extended 的 Scholar's Atelier 暖色学术风 CSS。
"""

import json
import time
from pathlib import Path

RADAR_LABELS = ["教学逻辑", "互动技巧", "提问深度", "情感支持", "课堂管理"]
RADAR_KEYS = ["radar_logic", "radar_interaction", "radar_questioning", "radar_support", "radar_management"]

BLOOM_LABELS = ["记忆", "理解", "应用", "分析", "评价", "创造"]
BLOOM_KEYS = ["bloom_memory", "bloom_understand", "bloom_apply", "bloom_analyze", "bloom_evaluate", "bloom_create"]


def generate_growth_html(teacher_name: str, lessons: list, output_path: str = None) -> str:
    """
    生成教师成长追踪报告 HTML。

    Args:
        teacher_name: 教师姓名
        lessons: get_growth_data() 返回的课次列表
        output_path: 如果指定，写入文件
    Returns:
        HTML 字符串
    """
    if not lessons:
        return "<html><body><h2>暂无数据</h2><p>该教师尚无课次分析记录</p></body></html>"

    school_name = lessons[0].get("school_name", "")
    subject = lessons[0].get("subject", "")
    lesson_count = len(lessons)

    # 构建图表数据
    x_labels = []
    radar_series = {lbl: [] for lbl in RADAR_LABELS}
    bloom_series = {lbl: [] for lbl in BLOOM_LABELS}
    rt_values = []
    ch_values = []
    hattie_task = []
    hattie_process = []
    hattie_self = []

    for i, les in enumerate(lessons):
        label = les.get("lesson_date") or les.get("folder_name", f"第{i+1}次")
        x_labels.append(label)

        for lbl, key in zip(RADAR_LABELS, RADAR_KEYS):
            val = les.get(key)
            radar_series[lbl].append(val if val is not None else 0)

        for lbl, key in zip(BLOOM_LABELS, BLOOM_KEYS):
            val = les.get(key, 0) or 0
            bloom_series[lbl].append(val)

        rt_values.append(les.get("rt_value"))
        ch_values.append(les.get("ch_value"))
        hattie_task.append(les.get("hattie_task", 0) or 0)
        hattie_process.append(les.get("hattie_process", 0) or 0)
        hattie_self.append(les.get("hattie_self", 0) or 0)

    # 趋势分析
    radar_trend = _analyze_radar_trend(lessons)

    # 预序列化 JS 数据
    js_x = json.dumps(x_labels, ensure_ascii=False)
    js_radar_labels = json.dumps(RADAR_LABELS, ensure_ascii=False)
    js_radar_series = []
    for lbl in RADAR_LABELS:
        js_radar_series.append(json.dumps({
            "name": lbl, "type": "line", "data": radar_series[lbl], "smooth": True
        }, ensure_ascii=False))

    js_bloom_labels = json.dumps(BLOOM_LABELS, ensure_ascii=False)
    bloom_colors = ['#d4a574', '#c4713b', '#b8860b', '#4a7c59', '#2c3e50', '#8b2252']
    js_bloom_series = []
    for i, lbl in enumerate(BLOOM_LABELS):
        js_bloom_series.append(json.dumps({
            "name": lbl, "type": "bar", "stack": "bloom",
            "data": bloom_series[lbl], "itemStyle": {"color": bloom_colors[i]}
        }, ensure_ascii=False))

    js_rt = json.dumps(rt_values)
    js_ch = json.dumps(ch_values)
    js_hattie_task = json.dumps(hattie_task)
    js_hattie_process = json.dumps(hattie_process)
    js_hattie_self = json.dumps(hattie_self)

    html = _GROWTH_TEMPLATE.format(
        teacher_name=teacher_name,
        school_name=school_name,
        subject=subject or "综合",
        lesson_count=lesson_count,
        radar_trend=radar_trend,
        lesson_table=_build_lesson_table(lessons),
        js_x=js_x,
        js_radar_labels=js_radar_labels,
        js_radar_series=",".join(js_radar_series),
        js_bloom_labels=js_bloom_labels,
        js_bloom_series=",".join(js_bloom_series),
        js_rt=js_rt,
        js_ch=js_ch,
        js_hattie_task=js_hattie_task,
        js_hattie_process=js_hattie_process,
        js_hattie_self=js_hattie_self,
        css=_build_growth_css(),
    )

    if output_path:
        Path(output_path).write_text(html, encoding="utf-8")
    return html


def generate_school_overview_html(school_name: str, overview: dict, all_lessons: list,
                                   output_path: str = None) -> str:
    """生成学校教学概览报告 HTML。"""
    teachers = overview.get("teachers", [])
    overall = overview.get("overall", {})
    by_subject = overview.get("by_subject", [])
    lesson_count = sum(t.get("lesson_count", 0) for t in teachers)

    # 教师雷达对比
    teacher_names = [t["name"] for t in teachers if t.get("lesson_count", 0) > 0]
    teacher_radar = []
    for t in teachers:
        if t.get("lesson_count", 0) > 0:
            teacher_radar.append([
                t.get("avg_logic", 0) or 0,
                t.get("avg_interaction", 0) or 0,
                t.get("avg_questioning", 0) or 0,
                t.get("avg_support", 0) or 0,
                t.get("avg_management", 0) or 0,
            ])

    # 预序列化
    js_teacher_names = json.dumps(teacher_names, ensure_ascii=False)
    js_teacher_radar = json.dumps([{"name": n, "value": v} for n, v in zip(teacher_names, teacher_radar)], ensure_ascii=False)
    kpi_vals = {
        "logic": overall.get("avg_logic", "-") or "-",
        "interaction": overall.get("avg_interaction", "-") or "-",
        "questioning": overall.get("avg_questioning", "-") or "-",
        "support": overall.get("avg_support", "-") or "-",
        "management": overall.get("avg_management", "-") or "-",
    }

    # 学科对比图表
    subject_chart_js = ""
    if by_subject:
        subj_names = json.dumps([s.get("subject", "未知") for s in by_subject], ensure_ascii=False)
        subj_series = []
        subj_colors = ['#b8860b', '#4a7c59', '#c4713b', '#2c3e50', '#8b2252']
        dims = [("教学逻辑", "avg_logic"), ("互动技巧", "avg_interaction"),
                ("提问深度", "avg_questioning"), ("情感支持", "avg_support"),
                ("课堂管理", "avg_management")]
        for i, (dname, dkey) in enumerate(dims):
            subj_series.append(json.dumps({
                "name": dname, "type": "bar",
                "data": [s.get(dkey, 0) or 0 for s in by_subject],
                "itemStyle": {"color": subj_colors[i]}
            }, ensure_ascii=False))
        subject_chart_js = f"""
        var chartSub = echarts.init(document.getElementById('chart-subject-compare'));
        chartSub.setOption({{
            tooltip: {{trigger:'axis',axisPointer:{{type:'shadow'}}}},
            legend: {{data:['教学逻辑','互动技巧','提问深度','情感支持','课堂管理'],top:0}},
            grid: {{left:80,right:30,top:40,bottom:30}},
            xAxis: {{type:'category',data:{subj_names}}},
            yAxis: {{type:'value',min:0,max:100}},
            series:[{",".join(subj_series)}]
        }});
        window.addEventListener('resize',function(){{chartSub.resize();}});
        """

    html = _SCHOOL_TEMPLATE.format(
        school_name=school_name,
        teacher_count=len(teachers),
        lesson_count=lesson_count,
        subject_count=len(by_subject),
        teacher_table=_build_teacher_table(teachers),
        css=_build_growth_css(),
        js_teacher_names=js_teacher_names,
        js_teacher_radar=js_teacher_radar,
        subject_chart_section=f"""<div class="section-card"><div class="section-icon">📚</div><h2 class="section-title">学科维度对比</h2><div id="chart-subject-compare" style="width:100%;height:380px;"></div></div>""" if by_subject else "",
        subject_chart_js=subject_chart_js,
        **kpi_vals,
    )

    if output_path:
        Path(output_path).write_text(html, encoding="utf-8")
    return html


# ─── HTML 模板 ─────────────────────────────────────────


_GROWTH_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>教师成长追踪 - {teacher_name}</title>
<script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"></script>
{css}
</head>
<body>
<div class="main-content">
<div class="report-content-wrap">

<div class="report-header">
  <div class="header-badge">纵向追踪报告</div>
  <h1 class="header-title">{teacher_name} · 教学成长档案</h1>
  <div class="header-meta">
    <span>{school_name}</span>
    <span class="meta-divider">|</span>
    <span>{subject}</span>
    <span class="meta-divider">|</span>
    <span>共 {lesson_count} 节课</span>
  </div>
</div>

<div class="section-card">
  <div class="section-icon">📊</div>
  <h2 class="section-title">五维能力成长曲线</h2>
  <div id="chart-radar-trend" style="width:100%;height:420px;"></div>
  <div class="trend-summary">{radar_trend}</div>
</div>

<div class="section-card">
  <div class="section-icon">🧠</div>
  <h2 class="section-title">提问认知层次演进</h2>
  <div id="chart-bloom-trend" style="width:100%;height:380px;"></div>
  <div class="chart-note">高阶思维（分析/评价/创造）占比提升表明提问质量改善</div>
</div>

<div class="section-card">
  <div class="section-icon">🔄</div>
  <h2 class="section-title">教学行为变化趋势</h2>
  <div id="chart-st-trend" style="width:100%;height:350px;"></div>
  <div class="chart-note">Rt(教师行为率)下降 + Ch(师生转换频率)上升 = 走向以学生为中心</div>
</div>

<div class="section-card">
  <div class="section-icon">💬</div>
  <h2 class="section-title">反馈质量演进</h2>
  <div id="chart-hattie-trend" style="width:100%;height:320px;"></div>
  <div class="chart-note">从任务层级反馈向过程/自我层级反馈演进，反映反馈质量提升</div>
</div>

<div class="section-card">
  <div class="section-icon">📋</div>
  <h2 class="section-title">课次明细</h2>
  <div class="detail-table-wrap">{lesson_table}</div>
</div>

</div></div>

<script>
(function() {{
    var xData = {js_x};

    var chart1 = echarts.init(document.getElementById('chart-radar-trend'));
    chart1.setOption({{
        tooltip: {{trigger:'axis'}},
        legend: {{data:{js_radar_labels},top:0}},
        grid: {{left:50,right:30,top:40,bottom:30}},
        xAxis: {{type:'category',data:xData,axisLabel:{{rotate:30}}}},
        yAxis: {{type:'value',min:0,max:100,name:'分数'}},
        series:[{js_radar_series}]
    }});

    var chart2 = echarts.init(document.getElementById('chart-bloom-trend'));
    chart2.setOption({{
        tooltip: {{trigger:'axis',axisPointer:{{type:'shadow'}}}},
        legend: {{data:{js_bloom_labels},top:0}},
        grid: {{left:50,right:30,top:40,bottom:30}},
        xAxis: {{type:'category',data:xData,axisLabel:{{rotate:30}}}},
        yAxis: {{type:'value',name:'提问数量'}},
        series:[{js_bloom_series}]
    }});

    var chart3 = echarts.init(document.getElementById('chart-st-trend'));
    var rtData = {js_rt}.map(function(v){{return v!==null?v:'-';}});
    var chData = {js_ch}.map(function(v){{return v!==null?v:'-';}});
    chart3.setOption({{
        tooltip: {{trigger:'axis'}},
        legend: {{data:['Rt (教师行为率)','Ch (师生转换频率)'],top:0}},
        grid: {{left:60,right:60,top:40,bottom:30}},
        xAxis: {{type:'category',data:xData,axisLabel:{{rotate:30}}}},
        yAxis: [
            {{type:'value',name:'Rt',min:0,max:1,position:'left'}},
            {{type:'value',name:'Ch',min:0,max:1,position:'right'}}
        ],
        series: [
            {{name:'Rt (教师行为率)',type:'line',data:rtData,smooth:true,yAxisIndex:0,itemStyle:{{color:'#c4713b'}}}},
            {{name:'Ch (师生转换频率)',type:'line',data:chData,smooth:true,yAxisIndex:1,itemStyle:{{color:'#4a7c59'}}}}
        ]
    }});

    var chart4 = echarts.init(document.getElementById('chart-hattie-trend'));
    chart4.setOption({{
        tooltip: {{trigger:'axis'}},
        legend: {{data:['任务层级','过程层级','自我层级'],top:0}},
        grid: {{left:50,right:30,top:40,bottom:30}},
        xAxis: {{type:'category',data:xData,axisLabel:{{rotate:30}}}},
        yAxis: {{type:'value',name:'反馈次数'}},
        series: [
            {{name:'任务层级',type:'bar',stack:'hattie',data:{js_hattie_task},itemStyle:{{color:'#d4a574'}}}},
            {{name:'过程层级',type:'bar',stack:'hattie',data:{js_hattie_process},itemStyle:{{color:'#b8860b'}}}},
            {{name:'自我层级',type:'bar',stack:'hattie',data:{js_hattie_self},itemStyle:{{color:'#8b2252'}}}}
        ]
    }});

    window.addEventListener('resize',function(){{chart1.resize();chart2.resize();chart3.resize();chart4.resize();}});
}})();
</script>
</body></html>"""


_SCHOOL_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>学校教学概览 - {school_name}</title>
<script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"></script>
{css}
</head>
<body>
<div class="main-content">
<div class="report-content-wrap">

<div class="report-header">
  <div class="header-badge">学校教学概览</div>
  <h1 class="header-title">{school_name} · 教学全景</h1>
  <div class="header-meta">
    <span>教师 {teacher_count} 人</span>
    <span class="meta-divider">|</span>
    <span>课次 {lesson_count} 节</span>
    <span class="meta-divider">|</span>
    <span>学科 {subject_count} 个</span>
  </div>
</div>

<div class="kpi-row">
  <div class="kpi-card"><div class="kpi-value">{logic}</div><div class="kpi-label">教学逻辑</div></div>
  <div class="kpi-card"><div class="kpi-value">{interaction}</div><div class="kpi-label">互动技巧</div></div>
  <div class="kpi-card"><div class="kpi-value">{questioning}</div><div class="kpi-label">提问深度</div></div>
  <div class="kpi-card"><div class="kpi-value">{support}</div><div class="kpi-label">情感支持</div></div>
  <div class="kpi-card"><div class="kpi-value">{management}</div><div class="kpi-label">课堂管理</div></div>
</div>

<div class="section-card">
  <div class="section-icon">👥</div>
  <h2 class="section-title">教师能力横向对比</h2>
  <div id="chart-teacher-compare" style="width:100%;height:450px;"></div>
</div>

<div class="section-card">
  <div class="section-icon">📋</div>
  <h2 class="section-title">教师明细</h2>
  <div class="detail-table-wrap">{teacher_table}</div>
</div>

{subject_chart_section}

</div></div>

<script>
(function() {{
    var chart = echarts.init(document.getElementById('chart-teacher-compare'));
    chart.setOption({{
        tooltip: {{}},
        legend: {{data:{js_teacher_names},top:0}},
        radar: {{
            indicator: [
                {{name:'教学逻辑',max:100}},{{name:'互动技巧',max:100}},
                {{name:'提问深度',max:100}},{{name:'情感支持',max:100}},
                {{name:'课堂管理',max:100}}
            ],
            radius:'65%'
        }},
        series:[{{type:'radar',data:{js_teacher_radar}}}]
    }});
    window.addEventListener('resize',function(){{chart.resize();}});
    {subject_chart_js}
}})();
</script>
</body></html>"""


# ─── 辅助函数 ─────────────────────────────────────────


def _analyze_radar_trend(lessons: list) -> str:
    """分析五维雷达的趋势，返回文字总结"""
    if len(lessons) < 2:
        return "<p>仅有 1 节课数据，暂无趋势分析</p>"

    first, last = lessons[0], lessons[-1]
    improvements = []
    declines = []

    for lbl, key in zip(RADAR_LABELS, RADAR_KEYS):
        f_val = first.get(key)
        l_val = last.get(key)
        if f_val is not None and l_val is not None:
            diff = l_val - f_val
            if diff > 5:
                improvements.append(f"<strong>{lbl}</strong>（+{diff:.0f}分）")
            elif diff < -5:
                declines.append(f"<strong>{lbl}</strong>（{diff:.0f}分）")

    parts = []
    if improvements:
        parts.append(f"<span class='trend-up'>↑ 提升维度：{', '.join(improvements)}</span>")
    if declines:
        parts.append(f"<span class='trend-down'>↓ 下降维度：{', '.join(declines)}</span>")
    if not improvements and not declines:
        parts.append("<span class='trend-flat'>→ 各维度保持稳定</span>")

    return "<p>" + "</p><p>".join(parts) + "</p>"


def _build_lesson_table(lessons: list) -> str:
    """构建课次明细表格"""
    rows = ""
    for i, les in enumerate(lessons):
        date_str = les.get("lesson_date") or les.get("folder_name", "-")
        subject = les.get("subject", "-")
        rows += f"""<tr>
            <td>{i+1}</td><td>{date_str}</td><td>{subject}</td>
            <td>{les.get('radar_logic', '-') or '-'}</td>
            <td>{les.get('radar_interaction', '-') or '-'}</td>
            <td>{les.get('radar_questioning', '-') or '-'}</td>
            <td>{les.get('radar_support', '-') or '-'}</td>
            <td>{les.get('radar_management', '-') or '-'}</td>
            <td>{les.get('rt_value', '-') or '-'}</td>
        </tr>"""
    return f"""<table class="detail-table">
        <thead><tr><th>#</th><th>日期</th><th>学科</th>
        <th>教学逻辑</th><th>互动技巧</th><th>提问深度</th>
        <th>情感支持</th><th>课堂管理</th><th>Rt</th></tr></thead>
        <tbody>{rows}</tbody></table>"""


def _build_teacher_table(teachers: list) -> str:
    """构建教师明细表格"""
    rows = ""
    for t in teachers:
        rows += f"""<tr>
            <td>{t.get('name', '-')}</td>
            <td>{t.get('subject', '-') or '-'}</td>
            <td>{t.get('lesson_count', 0)}</td>
            <td>{t.get('avg_logic', '-') or '-'}</td>
            <td>{t.get('avg_interaction', '-') or '-'}</td>
            <td>{t.get('avg_questioning', '-') or '-'}</td>
            <td>{t.get('avg_support', '-') or '-'}</td>
            <td>{t.get('avg_management', '-') or '-'}</td>
        </tr>"""
    return f"""<table class="detail-table">
        <thead><tr><th>教师</th><th>学科</th><th>课次</th>
        <th>教学逻辑</th><th>互动技巧</th><th>提问深度</th>
        <th>情感支持</th><th>课堂管理</th></tr></thead>
        <tbody>{rows}</tbody></table>"""


def _build_growth_css() -> str:
    """报告 CSS — Scholar's Atelier 暖色学术风"""
    return """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Serif+SC:wght@400;600;700;900&display=swap');
    :root {
        --parchment: #faf6f0; --parchment-deep: #f0ebe0;
        --ink: #1c1917; --ink-soft: #3d3630; --ink-muted: #78716c;
        --gold: #b8860b; --gold-bright: #daa520; --gold-pale: #f5e6c8;
        --gold-wash: #faf3e0; --wine: #8b2252; --sage: #4a7c59;
        --navy: #2c3e50; --terra: #c4713b;
        --card-bg: #fffdf8; --border: #e7e0d4; --radius: 10px;
    }
    * { box-sizing: border-box; }
    html { scroll-behavior: smooth; }
    body {
        margin: 0; padding: 0; background: var(--parchment);
        font-family: "Noto Sans SC", "PingFang SC", "Microsoft YaHei", sans-serif;
        color: var(--ink); line-height: 1.75; font-size: 14px;
    }
    .main-content { min-height: 100vh; }
    .report-content-wrap { max-width: 960px; margin: 0 auto; padding: 28px 40px 48px; }
    .report-header {
        background: linear-gradient(135deg, #1c1917 0%, #292524 30%, #3d3630 70%, #57534e 100%);
        color: #faf6f0; padding: 36px 40px 28px;
        border-bottom: 3px solid var(--gold); margin: -28px -40px 28px;
    }
    .header-badge {
        display: inline-block; font-size: 11px; text-transform: uppercase;
        letter-spacing: 3px; color: var(--gold-bright);
        border: 1px solid rgba(218,165,32,0.4); padding: 3px 14px;
        border-radius: 20px; margin-bottom: 12px;
    }
    .header-title {
        font-family: "Noto Serif SC", serif; font-size: 28px; font-weight: 900;
        margin: 0 0 8px; letter-spacing: 1px;
    }
    .header-meta { font-size: 13px; color: #a8a29e; }
    .meta-divider { margin: 0 8px; color: #57534e; }
    .kpi-row { display: flex; gap: 16px; margin-bottom: 24px; flex-wrap: wrap; }
    .kpi-card {
        flex: 1; min-width: 120px; background: var(--card-bg);
        border: 1px solid var(--border); border-radius: var(--radius);
        padding: 20px 16px; text-align: center;
    }
    .kpi-value { font-family: "Noto Serif SC", serif; font-size: 28px; font-weight: 900; color: var(--gold); }
    .kpi-label { font-size: 12px; color: var(--ink-muted); margin-top: 4px; }
    .section-card {
        background: var(--card-bg); border: 1px solid var(--border);
        border-radius: var(--radius); padding: 24px 28px; margin-bottom: 24px;
    }
    .section-icon { font-size: 20px; margin-bottom: 4px; }
    .section-title {
        font-family: "Noto Serif SC", serif; font-size: 18px; font-weight: 700;
        margin: 0 0 16px; color: var(--ink);
        border-bottom: 2px solid var(--gold-pale); padding-bottom: 8px;
    }
    .chart-note { font-size: 12px; color: var(--ink-muted); text-align: center; margin-top: 8px; }
    .trend-summary { margin-top: 12px; padding: 12px 16px; background: var(--gold-wash); border-radius: 6px; }
    .trend-up { color: var(--sage); font-weight: 600; }
    .trend-down { color: var(--wine); font-weight: 600; }
    .trend-flat { color: var(--ink-muted); }
    .detail-table-wrap { overflow-x: auto; }
    .detail-table { width: 100%; border-collapse: collapse; font-size: 13px; }
    .detail-table th {
        background: var(--parchment-deep); padding: 8px 10px; text-align: center;
        font-weight: 600; border-bottom: 2px solid var(--gold-pale); white-space: nowrap;
    }
    .detail-table td { padding: 7px 10px; text-align: center; border-bottom: 1px solid var(--border); }
    .detail-table tr:hover td { background: var(--gold-wash); }
    @media print {
        .report-content-wrap { padding: 0; }
        .report-header { margin: 0 0 20px; }
        .section-card { break-inside: avoid; }
    }
    </style>
    """
