# -*- coding: utf-8 -*-
"""
ICAS v3.0 报告生成器
三视角报告：教师/教研员/校长
学科增强版 — 核心是特级教师诊断书

设计理念：
- 图表是论据，诊断是结论
- 学科特有维度独立展示
- 教师分层定位醒目
- Agent F 的学科诊断是报告的 C 位
"""

import json
import time
import markdown


def _safe_get(data, *keys, default=None):
    """安全取值"""
    current = data
    for key in keys:
        if isinstance(current, dict):
            current = current.get(key, default)
        else:
            return default
    return current


def generate_v3_report(core_data, ext_data, v3_data, tier_result,
                       subject_profile, lesson_type_config=None,
                       audience="teacher", teacher_name="",
                       school_name=""):
    """
    生成 v3 报告 HTML

    参数:
        core_data: v2 基础分析数据
        ext_data: v2 扩展分析数据
        v3_data: v3 学科增强数据
        tier_result: 教师分层结果
        subject_profile: 学科配置
        lesson_type_config: 课型配置
        audience: 报告受众 (teacher/researcher/principal)
        teacher_name: 教师姓名
        school_name: 学校名称
    """
    subject = subject_profile["subject"]
    subject_label = subject_profile["label"]

    # 提取数据
    radar_scores = _safe_get(core_data, "deep", "radar_scores", default=[0, 0, 0, 0, 0])
    radar_labels = ["教学逻辑", "互动技巧", "提问深度", "情感支持", "课堂管理"]
    persona = _safe_get(core_data, "deep", "persona", default={"tag": "未知", "keywords": []})
    bloom_data = _safe_get(core_data, "deep", "bloom_stats", default=[])
    hattie_data = _safe_get(core_data, "deep", "hattie_stats", default={})
    time_stats = _safe_get(core_data, "structure", "overall_stats", default={})

    # v3 数据
    subject_report = _safe_get(v3_data, "subject_report") or {}
    subject_dims = _safe_get(v3_data, "subject_dimensions", "subject_dimensions") or []

    # 分层数据
    tier_name = _safe_get(tier_result, "tier", default="未评估")
    tier_icon = _safe_get(tier_result, "tier_icon", default="📊")
    tier_label = _safe_get(tier_result, "tier_label", default="未评估")
    composite_score = _safe_get(tier_result, "composite_score", default=0)
    weak_items = _safe_get(tier_result, "weak_items", default=[])
    strong_items = _safe_get(tier_result, "strong_items", default=[])

    # ---- 根据受众选择内容模块 ----
    show_detail_charts = audience in ("teacher", "researcher")
    show_subject_diagnosis = audience in ("teacher", "researcher")
    show_tier_map = audience in ("principal", "researcher")
    show_comparison = audience in ("principal", "researcher")
    show_growth_trend = audience in ("teacher", "researcher")

    # ---- 构建 HTML ----

    # 头部信息
    header_html = f"""
    <div class="report-header">
        <div class="header-main">
            <h1 class="report-title">{subject_label}课堂深度诊断书</h1>
            <p class="report-subtitle">ICAS v3.0 — {subject_label}学科特级教师视角</p>
        </div>
        <div class="header-meta">
            <div>教师: {teacher_name}</div>
            <div>学校: {school_name or '未指定'}</div>
            <div>日期: {time.strftime('%Y-%m-%d')}</div>
            <div>风格: {persona.get('tag', '未知')}</div>
        </div>
    </div>
    """

    # 教师分层卡片
    tier_card_html = f"""
    <div class="tier-card" style="border-left: 4px solid {_safe_get(tier_result, 'tier_color', default='#666')}">
        <div class="tier-badge">
            <span class="tier-icon">{tier_icon}</span>
            <span class="tier-name">{tier_label}</span>
            <span class="tier-score">{composite_score}分</span>
        </div>
        <div class="tier-details">
            <div class="tier-section">
                <strong>策略：</strong>{_safe_get(tier_result, 'strategy', default='--')}
            </div>
            {''.join([f'<div class="weak-item">⚠️ {w["dimension"]}（{w["score"]}分）</div>' for w in weak_items[:3]])}
            {''.join([f'<div class="strong-item">✅ {s["dimension"]}（{s["score"]}分）</div>' for s in strong_items[:2]])}
        </div>
    </div>
    """

    # 学科特有维度卡片
    subject_dims_html = ""
    if subject_dims:
        dims_cards = []
        for dim in subject_dims:
            score = dim.get("score", 0)
            color = "#10b981" if score >= 80 else "#f59e0b" if score >= 60 else "#ef4444"
            dims_cards.append(f"""
            <div class="subject-dim-card">
                <div class="dim-header">
                    <span class="dim-name">{dim.get('name', '')}</span>
                    <span class="dim-score" style="color: {color}">{score}分</span>
                </div>
                <div class="dim-bar-bg">
                    <div class="dim-bar-fill" style="width: {score}%; background: {color}"></div>
                </div>
                <div class="dim-detail">
                    {'<span class="dim-good">✓ ' + dim.get('evidence_good', '') + '</span>' if dim.get('evidence_good') else ''}
                    {'<span class="dim-weak">△ ' + dim.get('evidence_weak', '') + '</span>' if dim.get('evidence_weak') else ''}
                </div>
            </div>
            """)
        subject_dims_html = f"""
        <div class="section">
            <h2 class="section-title">{subject_label}学科特有维度</h2>
            <div class="subject-dims-grid">
                {''.join(dims_cards)}
            </div>
        </div>
        """

    # 核心问题诊断（Agent F 的精华）
    core_problems_html = ""
    if subject_report.get("core_problems"):
        problems = subject_report["core_problems"]
        problem_cards = []
        for i, p in enumerate(problems[:2]):
            severity = p.get("severity", "中")
            sev_color = "#ef4444" if severity == "高" else "#f59e0b"
            problem_cards.append(f"""
            <div class="problem-card" style="border-left: 4px solid {sev_color}">
                <div class="problem-header">
                    <span class="problem-num">问题{i+1}</span>
                    <span class="problem-severity" style="color: {sev_color}">{severity}优先级</span>
                    <span class="problem-dim">[{p.get('dimension', '')}]</span>
                </div>
                <div class="problem-text">{p.get('problem', '')}</div>
                <div class="problem-evidence">
                    <strong>课堂证据：</strong><br>{p.get('evidence', '')}
                </div>
            </div>
            """)
        core_problems_html = f"""
        <div class="section section-highlight">
            <h2 class="section-title">核心问题定位</h2>
            {''.join(problem_cards)}
        </div>
        """

    # 根因分析与预判
    diagnosis_html = ""
    if subject_report:
        diagnosis_parts = []
        if subject_report.get("subject_diagnosis"):
            diagnosis_parts.append(f"""
            <div class="diag-block">
                <h3>学科宏观诊断</h3>
                <div class="diag-text">{markdown.markdown(str(subject_report['subject_diagnosis']), extensions=['nl2br'])}</div>
            </div>
            """)
        if subject_report.get("root_cause_analysis"):
            diagnosis_parts.append(f"""
            <div class="diag-block">
                <h3>根因归因</h3>
                <div class="diag-text">{markdown.markdown(str(subject_report['root_cause_analysis']), extensions=['nl2br'])}</div>
            </div>
            """)
        if subject_report.get("improvement_forecast"):
            diagnosis_parts.append(f"""
            <div class="diag-block">
                <h3>改进预判</h3>
                <div class="diag-text">{markdown.markdown(str(subject_report['improvement_forecast']), extensions=['nl2br'])}</div>
            </div>
            """)
        diagnosis_html = f"""
        <div class="section">
            <h2 class="section-title">问题诊断四步法</h2>
            {''.join(diagnosis_parts)}
        </div>
        """

    # 特级教师建议（Agent F 核心）
    expert_advice_html = ""
    if subject_report.get("expert_recommendations"):
        recs = subject_report["expert_recommendations"]
        rec_cards = []
        for i, rec in enumerate(recs):
            rec_cards.append(f"""
            <div class="rec-card">
                <div class="rec-header">
                    <span class="rec-num">{i+1}</span>
                    <span class="rec-title">{rec.get('title', '')}</span>
                </div>
                <div class="rec-body">
                    <div class="rec-principle"><strong>原理：</strong>{rec.get('principle', '')}</div>
                    <div class="rec-current"><strong>现状：</strong>{rec.get('current_situation', '')}</div>
                    <div class="rec-action"><strong>具体做法：</strong>{rec.get('specific_action', '')}</div>
                </div>
            </div>
            """)
        expert_advice_html = f"""
        <div class="section section-primary">
            <h2 class="section-title">{subject_profile.get('label', '学科')}特级教师的改进建议</h2>
            {''.join(rec_cards)}
        </div>
        """

    # 下次关注点
    next_focus_html = ""
    if subject_report.get("next_focus"):
        items = subject_report["next_focus"]
        next_focus_html = f"""
        <div class="section">
            <h2 class="section-title">下次课关注点（纵向追踪）</h2>
            <div class="next-focus-list">
                {''.join([f'<div class="next-focus-item">📌 {item}</div>' for item in items])}
            </div>
        </div>
        """

    # 图表区域（非校长视角才显示详细图表）
    charts_html = ""
    if show_detail_charts:
        charts_html = f"""
        <div class="section">
            <h2 class="section-title">数据支撑</h2>
            <div class="charts-grid">
                <div class="chart-card">
                    <h3>五维能力雷达</h3>
                    <div id="radar-chart" style="width:100%;height:280px;"></div>
                </div>
                <div class="chart-card">
                    <h3>认知层次分布 (Bloom)</h3>
                    <div id="bloom-chart" style="width:100%;height:280px;"></div>
                </div>
                <div class="chart-card">
                    <h3>时间分配</h3>
                    <div id="time-chart" style="width:100%;height:250px;"></div>
                </div>
                <div class="chart-card">
                    <h3>反馈质量 (Hattie)</h3>
                    <div id="hattie-chart" style="width:100%;height:250px;"></div>
                </div>
            </div>
        </div>
        """

    # 组装完整 HTML
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="utf-8">
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js"></script>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@400;500;700;900&display=swap');
        body {{
            font-family: "Noto Sans SC", "Microsoft YaHei", sans-serif;
            background: #f8fafc;
            color: #1e293b;
            margin: 0;
            padding: 20px;
        }}

        .report-container {{
            max-width: 900px;
            margin: 0 auto;
            background: white;
            border-radius: 16px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1), 0 1px 2px rgba(0,0,0,0.06);
            overflow: hidden;
        }}

        /* 头部 */
        .report-header {{
            background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%);
            color: white;
            padding: 32px 40px;
            display: flex;
            justify-content: space-between;
            align-items: flex-end;
        }}
        .report-title {{ font-size: 1.75rem; font-weight: 900; margin: 0; }}
        .report-subtitle {{ font-size: 0.9rem; opacity: 0.8; margin-top: 4px; }}
        .header-meta {{ text-align: right; font-size: 0.85rem; opacity: 0.9; line-height: 1.8; }}

        /* 内容区 */
        .report-body {{ padding: 32px 40px; }}

        /* Section */
        .section {{
            margin-bottom: 32px;
            page-break-inside: avoid;
        }}
        .section-title {{
            font-size: 1.15rem;
            font-weight: 700;
            color: #1e293b;
            border-left: 4px solid #4f46e5;
            padding-left: 12px;
            margin-bottom: 16px;
        }}
        .section-highlight {{
            background: #fef3c7;
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 32px;
        }}
        .section-primary {{
            background: #eef2ff;
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 32px;
        }}

        /* 分层卡片 */
        .tier-card {{
            background: #f8fafc;
            border-radius: 12px;
            padding: 16px 20px;
            margin-bottom: 24px;
            display: flex;
            gap: 20px;
            align-items: center;
        }}
        .tier-badge {{
            display: flex;
            align-items: center;
            gap: 8px;
            min-width: 200px;
        }}
        .tier-icon {{ font-size: 2rem; }}
        .tier-name {{ font-weight: 700; font-size: 1.1rem; }}
        .tier-score {{ font-size: 1.5rem; font-weight: 900; color: #4f46e5; }}
        .tier-details {{ flex: 1; }}
        .tier-section {{ font-size: 0.9rem; color: #475569; margin-bottom: 4px; }}
        .weak-item {{ color: #dc2626; font-size: 0.85rem; }}
        .strong-item {{ color: #059669; font-size: 0.85rem; }}

        /* 学科维度卡片 */
        .subject-dims-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
            gap: 12px;
        }}
        .subject-dim-card {{
            background: #f8fafc;
            border-radius: 8px;
            padding: 12px;
        }}
        .dim-header {{
            display: flex;
            justify-content: space-between;
            margin-bottom: 6px;
        }}
        .dim-name {{ font-weight: 600; font-size: 0.9rem; }}
        .dim-score {{ font-weight: 700; font-size: 1rem; }}
        .dim-bar-bg {{
            height: 6px;
            background: #e2e8f0;
            border-radius: 3px;
            overflow: hidden;
            margin-bottom: 6px;
        }}
        .dim-bar-fill {{ height: 100%; border-radius: 3px; transition: width 0.5s; }}
        .dim-detail {{ font-size: 0.75rem; }}
        .dim-good {{ display: block; color: #059669; }}
        .dim-weak {{ display: block; color: #d97706; }}

        /* 问题卡片 */
        .problem-card {{
            background: white;
            border-radius: 8px;
            padding: 16px;
            margin-bottom: 12px;
            box-shadow: 0 1px 2px rgba(0,0,0,0.05);
        }}
        .problem-header {{
            display: flex;
            gap: 8px;
            align-items: center;
            margin-bottom: 8px;
            font-size: 0.85rem;
        }}
        .problem-num {{ font-weight: 700; color: #1e293b; }}
        .problem-severity {{ font-weight: 600; }}
        .problem-dim {{ color: #6b7280; }}
        .problem-text {{ font-weight: 600; color: #1e293b; margin-bottom: 8px; }}
        .problem-evidence {{
            font-size: 0.85rem;
            color: #475569;
            background: #f1f5f9;
            padding: 8px 12px;
            border-radius: 6px;
        }}

        /* 诊断块 */
        .diag-block {{
            margin-bottom: 16px;
        }}
        .diag-block h3 {{
            font-size: 0.95rem;
            font-weight: 600;
            color: #4f46e5;
            margin-bottom: 6px;
        }}
        .diag-text {{
            font-size: 0.9rem;
            line-height: 1.7;
            color: #334155;
        }}

        /* 建议卡片 */
        .rec-card {{
            background: white;
            border-radius: 10px;
            padding: 16px;
            margin-bottom: 12px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.08);
        }}
        .rec-header {{
            display: flex;
            align-items: center;
            gap: 10px;
            margin-bottom: 10px;
        }}
        .rec-num {{
            width: 28px; height: 28px;
            background: #4f46e5;
            color: white;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 700;
            font-size: 0.85rem;
        }}
        .rec-title {{ font-weight: 700; color: #1e293b; }}
        .rec-body {{ font-size: 0.9rem; line-height: 1.7; }}
        .rec-principle, .rec-current {{ color: #64748b; margin-bottom: 4px; }}
        .rec-action {{
            color: #1e293b;
            background: #f0fdf4;
            padding: 8px 12px;
            border-radius: 6px;
            border-left: 3px solid #10b981;
        }}

        /* 下次关注点 */
        .next-focus-list {{
            display: grid;
            gap: 8px;
        }}
        .next-focus-item {{
            background: #f0f9ff;
            padding: 10px 14px;
            border-radius: 8px;
            font-size: 0.9rem;
        }}

        /* 图表 */
        .charts-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 16px;
        }}
        .chart-card {{
            background: #f8fafc;
            border-radius: 10px;
            padding: 16px;
        }}
        .chart-card h3 {{
            font-size: 0.9rem;
            font-weight: 600;
            color: #475569;
            margin-bottom: 8px;
            text-align: center;
        }}

        /* 打印 */
        @media print {{
            body {{ background: white !important; padding: 0 !important; print-color-adjust: exact !important; -webkit-print-color-adjust: exact !important; }}
            .report-container {{ box-shadow: none !important; border-radius: 0 !important; }}
            .section, .problem-card, .rec-card, .tier-card, .subject-dim-card {{ page-break-inside: avoid !important; }}
        }}
    </style>
</head>
<body>
    <div class="report-container">
        {header_html}
        <div class="report-body">
            {tier_card_html}
            {subject_dims_html}
            {core_problems_html}
            {diagnosis_html}
            {expert_advice_html}
            {next_focus_html}
            {charts_html}
            <div style="text-align:center;color:#94a3b8;font-size:0.75rem;margin-top:32px;padding-top:16px;border-top:1px solid #e2e8f0;">
                Generated by ICAS v3.0 — {subject_label}学科特级教师视角 | {time.strftime('%Y-%m-%d')}
            </div>
        </div>
    </div>

    <script>
        window.onload = function() {{
            // 雷达图
            var radarEl = document.getElementById('radar-chart');
            if (radarEl) {{
                echarts.init(radarEl).setOption({{
                    radar: {{
                        indicator: [
                            {{ name: '逻辑', max: 100 }}, {{ name: '互动', max: 100 }},
                            {{ name: '提问', max: 100 }}, {{ name: '支持', max: 100 }},
                            {{ name: '管理', max: 100 }}
                        ],
                        radius: '65%', splitNumber: 4
                    }},
                    series: [{{ type: 'radar', data: [{{ value: {json.dumps(radar_scores)}, areaStyle: {{ color: 'rgba(79,70,229,0.15)' }}, lineStyle: {{ color: '#4f46e5' }}, itemStyle: {{ color: '#4f46e5' }} }}] }}]
                }});
            }}

            // Bloom
            var bloomEl = document.getElementById('bloom-chart');
            if (bloomEl) {{
                echarts.init(bloomEl).setOption({{
                    grid: {{ top: 20, bottom: 30, left: 40, right: 10 }},
                    xAxis: {{ type: 'category', data: {json.dumps([b.get('level','') for b in bloom_data])}, axisLabel: {{ fontSize: 10 }} }},
                    yAxis: {{ type: 'value', splitLine: {{ show: false }} }},
                    series: [{{ type: 'bar', data: {json.dumps([b.get('count',0) for b in bloom_data])}, itemStyle: {{ color: '#6366f1', borderRadius: [3,3,0,0] }} }}]
                }});
            }}

            // 时间分配
            var timeEl = document.getElementById('time-chart');
            if (timeEl) {{
                var timeData = [
                    {{ value: {time_stats.get('total_lecture_minutes', 0)}, name: '教师讲授', itemStyle: {{ color: '#6366f1' }} }},
                    {{ value: {time_stats.get('total_interaction_minutes', 0)}, name: '师生互动', itemStyle: {{ color: '#ec4899' }} }},
                    {{ value: {time_stats.get('total_practice_minutes', 0)}, name: '学生练习', itemStyle: {{ color: '#10b981' }} }},
                    {{ value: {time_stats.get('total_other_minutes', 0)}, name: '其他', itemStyle: {{ color: '#9ca3af' }} }}
                ];
                echarts.init(timeEl).setOption({{
                    tooltip: {{ trigger: 'item' }},
                    legend: {{ bottom: 0, left: 'center', itemWidth: 10, itemHeight: 10, textStyle: {{ fontSize: 10 }} }},
                    series: [{{ type: 'pie', radius: '65%', center: ['50%','40%'], data: timeData }}]
                }});
            }}

            // Hattie
            var hattieEl = document.getElementById('hattie-chart');
            if (hattieEl) {{
                echarts.init(hattieEl).setOption({{
                    tooltip: {{ trigger: 'item' }},
                    legend: {{ bottom: 0, left: 'center', itemWidth: 10, itemHeight: 10, textStyle: {{ fontSize: 10 }} }},
                    series: [{{ type: 'pie', radius: ['35%','60%'], center: ['50%','38%'], data: [
                        {{ value: {hattie_data.get('task_level', 0)}, name: '任务层级', itemStyle: {{ color: '#6366f1' }} }},
                        {{ value: {hattie_data.get('process_level', 0)}, name: '过程层级', itemStyle: {{ color: '#8b5cf6' }} }},
                        {{ value: {hattie_data.get('self_level', 0)}, name: '自我层级', itemStyle: {{ color: '#a78bfa' }} }}
                    ], label: {{ show: false }}, labelLine: {{ show: false }} }}]
                }});
            }}
        }};
    </script>
</body>
</html>"""

    return html
