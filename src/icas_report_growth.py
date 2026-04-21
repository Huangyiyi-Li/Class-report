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

# ─── 教育参考基准常量 ──────────────────────────────────
# 基于中国基础教育课堂观察研究和 Flanders 互动分析理论

BENCHMARKS = {
    "radar": {  # 五维雷达基准 (0-100)
        "优秀": 80, "良好": 65, "合格": 50,
    },
    "radar_dims": {
        "教学逻辑": {"优秀": 80, "良好": 65, "合格": 50},
        "互动技巧": {"优秀": 80, "良好": 65, "合格": 50},
        "提问深度": {"优秀": 75, "良好": 60, "合格": 45},  # 提问深度普遍偏低
        "情感支持": {"优秀": 80, "良好": 65, "合格": 50},
        "课堂管理": {"优秀": 80, "良好": 65, "合格": 50},
    },
    "rt": {  # Rt 教师行为率
        "学生主导": 0.30,  # <0.30 学生主导型
        "均衡": 0.50,      # 0.30-0.50 师生均衡
        "教师主导": 0.70,  # >0.50 教师主导
    },
    "ch": {  # Ch 师生转换频率
        "活跃": 0.25,  # >0.25 互动活跃
        "一般": 0.15,  # 0.15-0.25 一般
    },
    "bloom_high_ratio": 0.30,  # 高阶思维(分析+评价+创造)占比目标 ≥30%
    "hattie_deep_ratio": 0.40, # 过程+自我层级反馈占比目标 ≥40%
}

# 评级颜色
GRADE_COLORS = {
    "优秀": "#2c3e50", "良好": "#4a7c59",
    "合格": "#b8860b", "待改进": "#c4713b",
}


def _grade_score(score: float, thresholds: dict) -> str:
    """根据分数和阈值返回评级"""
    if score >= thresholds.get("优秀", 80): return "优秀"
    if score >= thresholds.get("良好", 65): return "良好"
    if score >= thresholds.get("合格", 50): return "合格"
    return "待改进"


def _run_diagnosis(lessons: list) -> dict:
    """
    规则驱动的诊断引擎。
    分析五维雷达趋势、Bloom 认知分布、S-T 行为比例、Hattie 反馈层级，
    返回结构化诊断结果。
    """
    if len(lessons) < 2:
        return {"summary": "数据不足（需≥2节课）", "items": [], "score": None}

    items = []
    first, last = lessons[0], lessons[-1]
    bm = BENCHMARKS

    # ── 1. 五维雷达诊断 ──
    for lbl, key in zip(RADAR_LABELS, RADAR_KEYS):
        f_val = first.get(key)
        l_val = last.get(key)
        if f_val is None or l_val is None:
            continue
        diff = l_val - f_val
        thresholds = bm["radar_dims"].get(lbl, bm["radar"])
        grade = _grade_score(l_val, thresholds)
        trend = "↑" if diff > 5 else ("↓" if diff < -5 else "→")
        severity = "warning" if grade == "待改进" else ("info" if diff < -5 else "ok")
        items.append({
            "category": "五维能力", "dimension": lbl,
            "first": f_val, "last": l_val, "diff": diff,
            "grade": grade, "trend": trend, "severity": severity,
            "msg": f"{lbl}：{f_val:.0f}→{l_val:.0f}（{trend}{abs(diff):.0f}分），评级【{grade}】"
        })

    # ── 2. Bloom 高阶思维占比诊断 ──
    high_keys = ["bloom_analyze", "bloom_evaluate", "bloom_create"]
    low_keys = ["bloom_memory", "bloom_understand", "bloom_apply"]
    for idx, les in enumerate([first, last]):
        total_q = sum(les.get(k, 0) or 0 for k in BLOOM_KEYS)
        if total_q == 0:
            continue
        high_count = sum(les.get(k, 0) or 0 for k in high_keys)
        ratio = high_count / total_q
        label = "首次" if idx == 0 else "最近"
        items.append({
            "category": "认知层次", "dimension": f"高阶思维占比({label})",
            "first": None, "last": None,
            "ratio": ratio, "target": bm["bloom_high_ratio"],
            "grade": "达标" if ratio >= bm["bloom_high_ratio"] else "待提升",
            "trend": "→",
            "severity": "ok" if ratio >= bm["bloom_high_ratio"] else "warning",
            "msg": f"高阶思维占比({label})：{ratio:.0%}（目标≥{bm['bloom_high_ratio']:.0%}）"
        })

    # ── 3. S-T 行为诊断 ──
    l_rt = last.get("rt_value")
    if l_rt is not None:
        if l_rt > bm["rt"]["教师主导"]:
            items.append({"category": "教学行为", "dimension": "Rt教师行为率",
                "first": None, "last": l_rt, "grade": "教师主导型",
                "trend": "→", "severity": "info",
                "msg": f"Rt={l_rt:.2f}（>0.50 教师主导），建议降低讲授比例"})
        elif l_rt < bm["rt"]["学生主导"]:
            items.append({"category": "教学行为", "dimension": "Rt教师行为率",
                "first": None, "last": l_rt, "grade": "学生主导型",
                "trend": "→", "severity": "ok",
                "msg": f"Rt={l_rt:.2f}（<0.30 学生主导），课堂以学生为中心"})
        else:
            items.append({"category": "教学行为", "dimension": "Rt教师行为率",
                "first": None, "last": l_rt, "grade": "师生均衡型",
                "trend": "→", "severity": "ok",
                "msg": f"Rt={l_rt:.2f}（0.30-0.50 师生均衡），教学节奏良好"})

    # ── 4. Hattie 反馈诊断 ──
    l_hattie_total = sum(last.get(k, 0) or 0 for k in ["hattie_task", "hattie_process", "hattie_self"])
    if l_hattie_total > 0:
        deep_ratio = (last.get("hattie_process", 0) or 0) + (last.get("hattie_self", 0) or 0)
        deep_ratio = deep_ratio / l_hattie_total
        grade = "达标" if deep_ratio >= bm["hattie_deep_ratio"] else "待提升"
        items.append({"category": "反馈质量", "dimension": "深层反馈占比",
            "first": None, "last": None,
            "ratio": deep_ratio, "target": bm["hattie_deep_ratio"],
            "grade": grade, "trend": "→",
            "severity": "ok" if grade == "达标" else "warning",
            "msg": f"过程+自我反馈占比：{deep_ratio:.0%}（目标≥{bm['hattie_deep_ratio']:.0%}）"})

    # ── 综合评分 ──
    radar_scores = [last.get(k) for k in RADAR_KEYS if last.get(k) is not None]
    avg_score = sum(radar_scores) / len(radar_scores) if radar_scores else None

    warnings = [i for i in items if i["severity"] == "warning"]
    summary_parts = []
    if warnings:
        dims = [i["dimension"] for i in warnings]
        summary_parts.append(f"⚠️ {len(warnings)}项待改进：{'、'.join(dims[:3])}")
    ok_items = [i for i in items if i["severity"] == "ok"]
    if ok_items:
        summary_parts.append(f"✅ {len(ok_items)}项达标/良好")
    if avg_score is not None:
        summary_parts.append(f"五维均分：{avg_score:.1f}")

    return {
        "summary": "；".join(summary_parts) if summary_parts else "诊断完成",
        "items": items,
        "avg_score": avg_score,
        "warning_count": len(warnings),
        "ok_count": len(ok_items),
    }


def _generate_prescriptions(diagnosis: dict, teacher_name: str) -> list:
    """
    基于诊断结果生成可执行处方建议。
    返回处方列表，每条包含 category / dimension / action / priority。
    """
    prescriptions = []
    items = diagnosis.get("items", [])

    # 按严重程度排序：warning > info > ok
    severity_order = {"warning": 0, "info": 1, "ok": 2}
    sorted_items = sorted(items, key=lambda x: severity_order.get(x.get("severity", "ok"), 2))

    for item in sorted_items:
        cat = item.get("category", "")
        dim = item.get("dimension", "")
        grade = item.get("grade", "")
        sev = item.get("severity", "ok")

        if sev == "warning":
            priority = "高"
            # 根据类别生成针对性建议
            if cat == "五维能力" and grade == "待改进":
                action = _get_radar_prescription(dim, item.get("last", 0))
            elif cat == "认知层次" and "待提升" in grade:
                action = "增加分析类和评价类提问。尝试\"为什么…？\"\"你怎么看…？\"\"比较一下…？\"等开放式问题，逐步减少\"是什么\"类记忆型问题。"
            elif cat == "反馈质量" and "待提升" in grade:
                action = "提升反馈深度：从\"对/错\"升级为\"你的思路很好，但这里可以…\"。多用过程性反馈（指明改进路径）和自我反思引导（\"你觉得哪里可以做得更好？\"）。"
            else:
                action = f"关注{dim}维度的持续提升，参考教研组优秀课例进行针对性训练。"
        elif sev == "info":
            priority = "中"
            if cat == "教学行为":
                action = "尝试增加小组讨论、学生展示等环节，将教师讲授时间压缩到课堂总时长的50%以下。每节课至少安排1次学生自主探究活动。"
            else:
                action = f"{dim}有下降趋势，建议复盘近期教学设计，与同组教师交流改进策略。"
        else:
            continue  # 达标的不出处方

        prescriptions.append({
            "category": cat, "dimension": dim,
            "action": action, "priority": priority,
            "grade": grade,
        })

    # 如果没有具体处方，给一个通用建议
    if not prescriptions:
        prescriptions.append({
            "category": "综合", "dimension": "持续发展",
            "action": f"{teacher_name}老师各项指标表现良好，建议继续保持当前教学风格，同时关注学科前沿教学方法，参与校际教研交流活动。",
            "priority": "低", "grade": "良好",
        })

    return prescriptions


def _get_radar_prescription(dimension: str, score: float) -> str:
    """根据五维雷达具体维度和分数生成针对性处方"""
    PRESCRIPTIONS = {
        "教学逻辑": "梳理教学目标→教学活动→评价任务的对齐关系。课前用\"三问\"检验：这节课学生要学到什么？通过什么活动学？怎么知道学会了？",
        "互动技巧": "增加师生互动形式：同桌讨论→小组合作→全班分享三段式。每5-8分钟设置一个互动节点，避免连续讲授超过10分钟。",
        "提问深度": "用\"等待时间\"策略：抛出问题后等待3-5秒再点名。将\"是什么\"类问题逐步替换为\"为什么\"\"如果…会怎样\"\"你有什么证据\"等高阶问题。",
        "情感支持": "关注课堂情感氛围：多用\"你的想法很有创意\"\"这个问题问得好\"等正向反馈。对回答错误的学生给予思路引导而非否定。",
        "课堂管理": "建立清晰的课堂常规和信号系统。使用\"注意力的候\"而非\"安静！\"。活动转换时给出明确的指令和时间预期。",
    }
    return PRESCRIPTIONS.get(dimension, f"建议在{dimension}方面进行专项训练，可参加校内教研活动或观摩优秀教师课堂。")


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

    # 诊断引擎 + 处方生成
    diagnosis = _run_diagnosis(lessons)
    prescriptions = _generate_prescriptions(diagnosis, teacher_name)
    diag_html = _build_diagnosis_html(diagnosis)
    presc_html = _build_prescription_html(prescriptions)

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
        diagnosis_html=diag_html,
        prescription_html=presc_html,
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

<div class="section-card diagnosis-card">
  <div class="section-icon">🔍</div>
  <h2 class="section-title">AI 诊断报告</h2>
  {diagnosis_html}
</div>

<div class="section-card prescription-card">
  <div class="section-icon">💊</div>
  <h2 class="section-title">处方建议</h2>
  {prescription_html}
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
        series:[{js_radar_series}],
        // 参考基准线
        visualMap: {{
            show: false, pieces: [
                {{gt: 80, color: '#2c3e50'}},
                {{gt: 65, lte: 80, color: '#4a7c59'}},
                {{gt: 50, lte: 65, color: '#b8860b'}},
                {{lte: 50, color: '#c4713b'}}
            ]
        }}
    }});
    // 添加基准参考线
    chart1.setOption({{
        yAxis: {{
            type:'value', min:0, max:100,
            axisLine: {{lineStyle:{{color:'#ccc'}}}}
        }},
        series: [{js_radar_series}].map(function(s, i) {{
            if (i === 0) {{
                s.markLine = {{
                    silent: true, symbol: 'none',
                    lineStyle: {{type:'dashed', width:1}},
                    data: [
                        {{yAxis:80, lineStyle:{{color:'#2c3e50'}}, label:{{formatter:'优秀(80)',position:'insideEndTop',fontSize:10,color:'#2c3e50'}}}},
                        {{yAxis:65, lineStyle:{{color:'#4a7c59'}}, label:{{formatter:'良好(65)',position:'insideEndTop',fontSize:10,color:'#4a7c59'}}}},
                        {{yAxis:50, lineStyle:{{color:'#c4713b'}}, label:{{formatter:'合格(50)',position:'insideEndTop',fontSize:10,color:'#c4713b'}}}}
                    ]
                }};
            }}
            return s;
        }})
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
            {{
                name:'Rt (教师行为率)',type:'line',data:rtData,smooth:true,yAxisIndex:0,
                itemStyle:{{color:'#c4713b'}},
                markLine:{{
                    silent:true, symbol:'none',
                    lineStyle:{{type:'dashed',width:1}},
                    data:[
                        {{yAxis:0.50,lineStyle:{{color:'#b8860b'}},label:{{formatter:'均衡线(0.50)',position:'insideEndTop',fontSize:10,color:'#b8860b'}}}},
                        {{yAxis:0.30,lineStyle:{{color:'#4a7c59'}},label:{{formatter:'学生主导(0.30)',position:'insideEndTop',fontSize:10,color:'#4a7c59'}}}}
                    ]
                }},
                markArea:{{
                    silent:true,
                    data:[[
                        {{yAxis:0.30,itemStyle:{{color:'rgba(74,124,89,0.08)'}}}},
                        {{yAxis:0.50}}
                    ]]
                }}
            }},
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


def _build_diagnosis_html(diagnosis: dict) -> str:
    """构建诊断报告 HTML"""
    items = diagnosis.get("items", [])
    if not items:
        return "<p class='diag-empty'>数据不足以生成诊断报告</p>"

    avg = diagnosis.get("avg_score")
    wc = diagnosis.get("warning_count", 0)
    oc = diagnosis.get("ok_count", 0)

    # 概要区
    header = f"""<div class="diag-summary">
      <div class="diag-score-card">
        <div class="diag-score-label">五维均分</div>
        <div class="diag-score-value">{avg:.1f}</div>
        <div class="diag-score-grade">{_grade_score(avg, BENCHMARKS['radar']) if avg else '-'}</div>
      </div>
      <div class="diag-stat-row">
        <span class="diag-stat stat-warn">⚠️ {wc} 项待改进</span>
        <span class="diag-stat stat-ok">✅ {oc} 项达标</span>
      </div>
      <div class="diag-summary-text">{diagnosis.get('summary', '')}</div>
    </div>"""

    # 明细区
    rows = ""
    for item in items:
        sev = item.get("severity", "ok")
        row_class = f"diag-row diag-{sev}"
        grade_badge = f"<span class='grade-badge grade-{item.get('grade','')}'>{item.get('grade','')}</span>"
        rows += f"""<div class="{row_class}">
          <span class="diag-cat">{item.get('category','')}</span>
          <span class="diag-dim">{item.get('dimension','')}</span>
          {grade_badge}
          <span class="diag-msg">{item.get('msg','')}</span>
        </div>"""

    return header + '<div class="diag-details">' + rows + '</div>'


def _build_prescription_html(prescriptions: list) -> str:
    """构建处方建议 HTML"""
    if not prescriptions:
        return "<p class='presc-empty'>暂无具体处方建议</p>"

    cards = ""
    for i, p in enumerate(prescriptions):
        pri = p.get("priority", "低")
        pri_class = f"presc-priority presc-{pri}"
        cards += f"""<div class="presc-card">
          <div class="presc-header">
            <span class="presc-num">处方 {i+1}</span>
            <span class="{pri_class}">优先级：{pri}</span>
            <span class="presc-dim">{p.get('category','')} · {p.get('dimension','')}</span>
          </div>
          <div class="presc-action">{p.get('action','')}</div>
        </div>"""

    return cards


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
    /* ── 诊断报告样式 ── */
    .diagnosis-card {{ border-left: 4px solid var(--wine); }}
    .diag-summary {{ display: flex; flex-wrap: wrap; gap: 16px; align-items: center; margin-bottom: 16px; }}
    .diag-score-card {{ background: var(--parchment-deep); border-radius: 8px; padding: 12px 20px; text-align: center; }}
    .diag-score-label {{ font-size: 11px; color: var(--ink-muted); }}
    .diag-score-value {{ font-family: "Noto Serif SC",serif; font-size: 32px; font-weight: 900; color: var(--gold); }}
    .diag-score-grade {{ font-size: 12px; color: var(--sage); font-weight: 600; }}
    .diag-stat-row {{ display: flex; gap: 12px; }}
    .diag-stat {{ font-size: 13px; font-weight: 600; }}
    .stat-warn {{ color: var(--terra); }} .stat-ok {{ color: var(--sage); }}
    .diag-summary-text {{ font-size: 13px; color: var(--ink-soft); flex-basis: 100%; margin-top: 4px; }}
    .diag-details {{ display: flex; flex-direction: column; gap: 6px; }}
    .diag-row {{
      display: flex; flex-wrap: wrap; gap: 8px; align-items: center;
      padding: 6px 10px; border-radius: 6px; font-size: 13px;
    }}
    .diag-ok {{ background: rgba(74,124,89,0.06); }}
    .diag-warning {{ background: rgba(196,113,59,0.08); }}
    .diag-info {{ background: rgba(184,134,11,0.06); }}
    .diag-cat {{ font-weight: 700; color: var(--ink-muted); min-width: 60px; }}
    .diag-dim {{ color: var(--ink-soft); min-width: 100px; }}
    .diag-msg {{ flex: 1; color: var(--ink); }}
    .grade-badge {{
      display: inline-block; padding: 1px 8px; border-radius: 10px;
      font-size: 11px; font-weight: 700;
    }}
    .grade-优秀 {{ background: #e8f0e8; color: #2c3e50; }}
    .grade-良好 {{ background: #e8f5e8; color: #4a7c59; }}
    .grade-合格 {{ background: #fff8e1; color: #b8860b; }}
    .grade-待改进 {{ background: #fbe9e7; color: #c4713b; }}
    .grade-达标 {{ background: #e8f5e8; color: #4a7c59; }}
    .grade-待提升 {{ background: #fff8e1; color: #b8860b; }}
    .grade-教师主导型 {{ background: #fff8e1; color: #b8860b; }}
    .grade-学生主导型 {{ background: #e8f5e8; color: #4a7c59; }}
    .grade-师生均衡型 {{ background: #e8f0e8; color: #2c3e50; }}
    /* ── 处方建议样式 ── */
    .prescription-card {{ border-left: 4px solid var(--gold); }}
    .presc-card {{
      background: var(--parchment-deep); border-radius: 8px;
      padding: 14px 18px; margin-bottom: 10px;
      border-left: 3px solid var(--gold);
    }}
    .presc-header {{
      display: flex; gap: 10px; align-items: center;
      margin-bottom: 6px; font-size: 12px;
    }}
    .presc-num {{
      font-weight: 800; color: var(--gold);
      font-family: "Noto Serif SC",serif;
    }}
    .presc-priority {{ font-weight: 700; }}
    .presc-高 {{ color: var(--terra); }}
    .presc-中 {{ color: var(--gold); }}
    .presc-低 {{ color: var(--ink-muted); }}
    .presc-dim {{ color: var(--ink-muted); }}
    .presc-action {{ font-size: 13px; color: var(--ink-soft); line-height: 1.7; }}
    @media print {
        .report-content-wrap { padding: 0; }
        .report-header { margin: 0 0 20px; }
        .section-card { break-inside: avoid; }
    }
    </style>
    """
