# -*- coding: utf-8 -*-
"""
ICAS v3.0 报告册生成器（完整版）
一个 HTML 文件 = 封面 + 总览 + 每节课完整报告 + 跨课对比
"""

import json
import time
import markdown
from pathlib import Path


def safe_get(data, *keys, default=None):
    current = data
    for key in keys:
        if isinstance(current, dict):
            current = current.get(key, default)
        else:
            return default
    return current


def generate_full_lesson_html(c, total_lessons):
    """生成单节课的完整报告 HTML"""

    # 学科维度卡片
    dim_cards = ""
    for d in c["subject_dims"]:
        score = d.get("score", 0)
        color = "#10b981" if score >= 80 else "#f59e0b" if score >= 60 else "#ef4444"
        dim_cards += f"""
        <div class="sdim-card">
            <div class="sdim-head">
                <span class="sdim-name">{d.get('name','')}</span>
                <span class="sdim-score" style="color:{color}">{score}分</span>
            </div>
            <div class="sdim-bar-bg"><div class="sdim-bar" style="width:{score}%;background:{color}"></div></div>
            <div class="sdim-evidence">
                {f'<div class="sdim-good">✓ {d.get("evidence_good","")}</div>' if d.get('evidence_good') else ''}
                {f'<div class="sdim-weak">△ {d.get("evidence_weak","")}</div>' if d.get('evidence_weak') else ''}
            </div>
            <div class="sdim-detail">{d.get('detail','')}</div>
        </div>"""

    # 核心问题
    problems_html = ""
    for p in c["core_problems"]:
        sev = p.get("severity", "中")
        sev_color = "#ef4444" if sev == "高" else "#f59e0b"
        problems_html += f"""
        <div class="fproblem" style="border-left:4px solid {sev_color}">
            <div class="fproblem-head">
                <span class="fproblem-sev" style="color:{sev_color}">{sev}优先级</span>
                <span class="fproblem-dim">[ {p.get('dimension','')} ]</span>
            </div>
            <div class="fproblem-text">{p.get('problem','')}</div>
            <div class="fproblem-evidence">课堂证据：{p.get('evidence','')}</div>
        </div>"""

    # 诊断（宏观 + 根因 + 预判）
    diag_html = ""
    if c.get("subject_diagnosis"):
        diag_html += f'<div class="fdiag-block"><h4>学科宏观诊断</h4><div class="fdiag-text">{markdown.markdown(str(c["subject_diagnosis"]), extensions=["nl2br"])}</div></div>'
    if c.get("root_cause"):
        diag_html += f'<div class="fdiag-block"><h4>根因归因</h4><div class="fdiag-text">{markdown.markdown(str(c["root_cause"]), extensions=["nl2br"])}</div></div>'

    # 建议
    recs_html = ""
    for j, r in enumerate(c["recommendations"]):
        recs_html += f"""
        <div class="frec">
            <div class="frec-num">{j+1}</div>
            <div class="frec-body">
                <div class="frec-title">{r.get('title','')}</div>
                <div class="frec-principle">原理：{r.get('principle','')}</div>
                <div class="frec-current">现状：{r.get('current_situation','')}</div>
                <div class="frec-action">具体做法：{r.get('specific_action','')}</div>
            </div>
        </div>"""

    # 下次关注
    focus_html = "".join(f'<div class="ffocus-item">📌 {f}</div>' for f in c.get("next_focus", []))

    # 导航
    prev_id = f"lesson-{c['index']-1}" if c["index"] > 1 else "overview"
    next_id = f"lesson-{c['index']+1}" if c["index"] < total_lessons else "summary"
    prev_label = f"← 第{c['index']-1}课" if c["index"] > 1 else "← 总览"
    next_label = f"第{c['index']+1}课 →" if c["index"] < total_lessons else "对比 →"

    return f"""
    <div class="page" id="lesson-{c['index']}">
        <!-- 课头 -->
        <div class="flesson-header" style="border-left:5px solid {c['tier_color']}">
            <div class="flh-left">
                <div class="flh-tag">第 {c['index']} / {total_lessons} 课</div>
                <div class="flh-title">{c['lesson_title']}</div>
                <div class="flh-meta">{c['subject']}学科 · {c['lesson_type']} · {c['persona_tag']}</div>
            </div>
            <div class="flh-right">
                <div class="flh-tier-icon">{c['tier_icon']}</div>
                <div class="flh-score">{c['composite_score']}<span class="flh-score-unit">分</span></div>
                <div class="flh-tier-name">{c['tier_label']}</div>
            </div>
        </div>

        <!-- 学科维度 -->
        <div class="fsection">
            <h3 class="fstitle">{c['subject']}学科特有维度</h3>
            <div class="fdims-grid">{dim_cards}</div>
        </div>

        <!-- 核心问题 -->
        {f'<div class="fsection fsection-warn"><h3 class="fstitle">核心问题定位</h3>{problems_html}</div>' if problems_html else ''}

        <!-- 诊断 -->
        {f'<div class="fsection"><h3 class="fstitle">问题诊断</h3>{diag_html}</div>' if diag_html else ''}

        <!-- 特级教师建议 -->
        {f'<div class="fsection fsection-primary"><h3 class="fstitle">{c["subject"]}学科特级教师的改进建议</h3>{recs_html}</div>' if recs_html else ''}

        <!-- 图表区 -->
        <div class="fsection">
            <h3 class="fstitle">数据支撑</h3>
            <div class="fcharts-grid">
                <div class="fchart-card">
                    <h4>五维能力雷达</h4>
                    <div id="f-radar-{c['index']}" style="width:100%;height:260px;"></div>
                </div>
                <div class="fchart-card">
                    <h4>认知层次 (Bloom)</h4>
                    <div id="f-bloom-{c['index']}" style="width:100%;height:260px;"></div>
                </div>
                <div class="fchart-card">
                    <h4>时间分配</h4>
                    <div id="f-time-{c['index']}" style="width:100%;height:240px;"></div>
                </div>
                <div class="fchart-card">
                    <h4>反馈质量 (Hattie)</h4>
                    <div id="f-hattie-{c['index']}" style="width:100%;height:240px;"></div>
                </div>
            </div>
        </div>

        <!-- 下次关注 -->
        {f'<div class="fsection"><h3 class="fstitle">下次课关注点（纵向追踪）</h3>{focus_html}</div>' if focus_html else ''}

        <!-- 翻页 -->
        <div class="fpage-nav">
            <button class="fpn-btn" onclick="showPage('{prev_id}')">{prev_label}</button>
            <span class="fpn-pos">{c['index']} / {total_lessons}</span>
            <button class="fpn-btn" onclick="showPage('{next_id}')">{next_label}</button>
        </div>
    </div>
    """


def generate_booklet(lessons_data, output_path, school_name="濮东小学"):
    """生成完整报告册"""

    def sort_key(d):
        name = d.get("folder_name", "")
        nums = "".join(c for c in name if c.isdigit())
        return int(nums) if nums else 0
    lessons_data.sort(key=sort_key)

    total = len(lessons_data)

    # ---- 提取每课次数据 ----
    cards = []
    for i, ld in enumerate(lessons_data):
        subject = ld.get("subject", "未知")
        lesson_type = ld.get("lesson_type", "未知")
        teacher = ld.get("teacher", "未知教师")
        folder = ld.get("folder_name", f"课次{i+1}")

        tier_result = ld.get("tier_result") or {}
        core = ld.get("core_data") or {}
        deep = core.get("deep") or {}
        persona = deep.get("persona") or {}
        radar = deep.get("radar_scores") or [0, 0, 0, 0, 0]
        structure = core.get("structure") or {}

        v3 = ld.get("v3_data") or {}
        subject_report = v3.get("subject_report") or {}
        subject_dims = (v3.get("subject_dimensions") or {}).get("subject_dimensions") or []

        # 推断课题名
        lesson_title = folder
        folder_path = Path("F:/1濮东-课堂录音") / folder
        if folder_path.exists():
            for f in folder_path.glob("*.docx"):
                if "教学设计" in f.name or "教案" in f.name:
                    lesson_title = f.stem
                    break

        cards.append({
            "index": i + 1, "folder": folder, "subject": subject,
            "lesson_type": lesson_type, "teacher": teacher, "lesson_title": lesson_title,
            "persona_tag": persona.get("tag", ""),
            "persona_keywords": persona.get("keywords", []),
            "radar": radar,
            "tier_name": tier_result.get("tier", ""),
            "tier_label": tier_result.get("tier_label", ""),
            "tier_icon": tier_result.get("tier_icon", "📊"),
            "tier_color": tier_result.get("tier_color", "#666"),
            "composite_score": tier_result.get("composite_score", 0),
            "weak_items": tier_result.get("weak_items") or [],
            "strong_items": tier_result.get("strong_items") or [],
            "subject_dims": subject_dims,
            "core_problems": subject_report.get("core_problems") or [],
            "subject_diagnosis": subject_report.get("subject_diagnosis") or "",
            "root_cause": subject_report.get("root_cause_analysis") or "",
            "recommendations": subject_report.get("expert_recommendations") or [],
            "next_focus": subject_report.get("next_focus") or [],
            "bloom": deep.get("bloom_stats") or [],
            "time_stats": structure.get("overall_stats") or {},
            "hattie": deep.get("hattie_stats") or {},
        })

    avg_score = sum(c["composite_score"] for c in cards) / total if total else 0
    tier_counts = {}
    for c in cards:
        tl = c["tier_label"]
        tier_counts[tl] = tier_counts.get(tl, 0) + 1

    # 兼容不同格式：'成长型教师'/'成长'/'卓越教师'/'卓越' 等
    def count_tier(keyword):
        return sum(v for k, v in tier_counts.items() if keyword in k)
    tier_summary = {
        "卓越": count_tier("卓越"),
        "成熟": count_tier("成熟"),
        "成长": count_tier("成长"),
        "待提升": count_tier("待提升"),
    }

    # ---- HTML 构建 ----

    # 封面
    cover = f"""
    <div class="page cover-page" id="cover">
        <div class="cover-inner">
            <div class="cover-badge">ICAS v3.0 智能课堂分析</div>
            <h1 class="cover-title">{school_name}</h1>
            <h2 class="cover-subtitle">AI 课堂诊断报告册</h2>
            <div class="cover-stats">
                <div class="cs"><span class="cs-num">{total}</span><span class="cs-label">节课</span></div>
                <div class="cs"><span class="cs-num">{avg_score:.0f}</span><span class="cs-label">均分</span></div>
                <div class="cs-divider"></div>
                {" ".join(f'<div class="cs"><span class="cs-num">{v}</span><span class="cs-label">{k}</span></div>' for k, v in tier_summary.items())}
            </div>
            <div class="cover-date">{time.strftime('%Y年%m月%d日')}</div>
            <div class="cover-tip">点击侧边栏导航 · 每节课完整报告可独立查看</div>
        </div>
    </div>
    """

    # 总览表
    rows = ""
    for c in cards:
        weak = "、".join(w["dimension"] for w in c["weak_items"][:2]) if c["weak_items"] else "--"
        rows += f"""<tr onclick="showPage('lesson-{c['index']}')" class="ov-row">
            <td>{c['index']}</td>
            <td class="tl">{c['lesson_title'][:18]}</td>
            <td>{c['subject']}</td>
            <td>{c['lesson_type']}</td>
            <td style="color:{c['tier_color']}">{c['tier_icon']} {c['tier_label']}</td>
            <td><b>{c['composite_score']}</b></td>
            <td class="tl tw">{weak}</td>
        </tr>"""

    overview = f"""
    <div class="page" id="overview">
        <h2 class="ptitle">教学总览</h2>
        <div class="ov-stats">
            <div class="ovc"><div class="ovc-v">{avg_score:.0f}</div><div class="ovc-l">综合均分</div></div>
            <div class="ovc"><div class="ovc-v">{tier_summary["卓越"]}</div><div class="ovc-l">卓越</div></div>
            <div class="ovc"><div class="ovc-v">{tier_summary["成熟"]}</div><div class="ovc-l">成熟</div></div>
            <div class="ovc"><div class="ovc-v">{tier_summary["成长"]}</div><div class="ovc-l">成长</div></div>
            <div class="ovc"><div class="ovc-v">{tier_summary["待提升"]}</div><div class="ovc-l">待提升</div></div>
        </div>
        <div class="ov-table-wrap">
            <table class="ov-table">
                <thead><tr><th>#</th><th class="tl">课题</th><th>学科</th><th>课型</th><th>分层</th><th>得分</th><th class="tl">薄弱项</th></tr></thead>
                <tbody>{rows}</tbody>
            </table>
        </div>
        <div class="ov-chart">
            <h3>综合得分分布</h3>
            <div id="ov-score-chart" style="width:100%;height:280px;"></div>
        </div>
    </div>
    """

    # 每节课完整报告
    lesson_pages = [generate_full_lesson_html(c, total) for c in cards]

    # 对比页
    labels = json.dumps([f"第{c['index']}课" for c in cards])
    scores = json.dumps([c["composite_score"] for c in cards])
    radar_map = {f"第{c['index']}课": c["radar"] for c in cards}

    dim_series = ""
    dim_colors = ["#6366f1", "#ec4899", "#10b981", "#f59e0b", "#8b5cf6"]
    for li, label in enumerate(["教学逻辑", "互动技巧", "提问深度", "情感支持", "课堂管理"]):
        data = [c["radar"][li] if li < len(c["radar"]) else 0 for c in cards]
        dim_series += f'{{name:"{label}",type:"line",data:{json.dumps(data)},smooth:true,lineStyle:{{width:2,color:"{dim_colors[li]}"}},itemStyle:{{color:"{dim_colors[li]}"}}}},'

    comparison = f"""
    <div class="page" id="summary">
        <h2 class="ptitle">跨课对比分析</h2>
        <div class="sm-chart"><h3>综合得分趋势</h3><div id="sm-score" style="width:100%;height:280px;"></div></div>
        <div class="sm-chart"><h3>五维能力叠加对比</h3><div id="sm-radar" style="width:100%;height:380px;"></div></div>
        <div class="sm-chart"><h3>各维度变化趋势</h3><div id="sm-dim" style="width:100%;height:320px;"></div></div>
    </div>
    """

    # 侧边栏导航
    nav = '<div class="sb-title">ICAS v3.0</div>'
    nav += '<a class="sb-a" onclick="showPage(\'cover\')">封面</a>'
    nav += '<a class="sb-a" onclick="showPage(\'overview\')">总览</a>'
    nav += '<div class="sb-div"></div>'
    for c in cards:
        nav += f'<a class="sb-a" onclick="showPage(\'lesson-{c["index"]}\')">{c["index"]}. {c["lesson_title"][:10]}</a>'
    nav += '<div class="sb-div"></div>'
    nav += '<a class="sb-a" onclick="showPage(\'summary\')">对比</a>'

    # 图表 JS
    chart_js = ""
    for c in cards:
        r = json.dumps(c["radar"])
        bl = c["bloom"]
        bl_levels = json.dumps([b.get("level", "") for b in bl])
        bl_counts = json.dumps([b.get("count", 0) for b in bl])
        ts = c["time_stats"]
        ht = c["hattie"]

        chart_js += f"""
        // 第{c['index']}课
        echarts.init(document.getElementById('f-radar-{c['index']}')).setOption({{
            radar:{{indicator:[{{name:'逻辑',max:100}},{{name:'互动',max:100}},{{name:'提问',max:100}},{{name:'支持',max:100}},{{name:'管理',max:100}}],radius:'65%',splitNumber:4}},
            series:[{{type:'radar',data:[{{value:{r},areaStyle:{{color:'rgba(79,70,229,0.15)'}},lineStyle:{{color:'#4f46e5'}},itemStyle:{{color:'#4f46e5'}}}}]}}]
        }});
        echarts.init(document.getElementById('f-bloom-{c['index']}')).setOption({{
            grid:{{top:20,bottom:30,left:40,right:10}},
            xAxis:{{type:'category',data:{bl_levels},axisLabel:{{fontSize:9}}}},
            yAxis:{{type:'value',splitLine:{{show:false}}}},
            series:[{{type:'bar',data:{bl_counts},itemStyle:{{color:'#6366f1',borderRadius:[3,3,0,0]}}}}]
        }});
        echarts.init(document.getElementById('f-time-{c['index']}')).setOption({{
            tooltip:{{trigger:'item'}},legend:{{bottom:0,textStyle:{{fontSize:9}}}},
            series:[{{type:'pie',radius:'65%',center:['50%','42%'],data:[
                {{value:{ts.get('total_lecture_minutes',0)},name:'教师讲授',itemStyle:{{color:'#6366f1'}}}},
                {{value:{ts.get('total_interaction_minutes',0)},name:'师生互动',itemStyle:{{color:'#ec4899'}}}},
                {{value:{ts.get('total_practice_minutes',0)},name:'学生练习',itemStyle:{{color:'#10b981'}}}},
                {{value:{ts.get('total_other_minutes',0)},name:'其他',itemStyle:{{color:'#9ca3af'}}}}
            ]}}]
        }});
        echarts.init(document.getElementById('f-hattie-{c['index']}')).setOption({{
            tooltip:{{trigger:'item'}},legend:{{bottom:0,textStyle:{{fontSize:9}}}},
            series:[{{type:'pie',radius:['35%','60%'],center:['50%','40%'],data:[
                {{value:{ht.get('task_level',0)},name:'任务层级',itemStyle:{{color:'#6366f1'}}}},
                {{value:{ht.get('process_level',0)},name:'过程层级',itemStyle:{{color:'#8b5cf6'}}}},
                {{value:{ht.get('self_level',0)},name:'自我层级',itemStyle:{{color:'#a78bfa'}}}}
            ],label:{{show:false}},labelLine:{{show:false}}}}]
        }});
        """

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{school_name} AI课堂诊断报告册</title>
<script src="https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js"></script>
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@300;400;500;700;900&display=swap');
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:"Noto Sans SC","Microsoft YaHei",sans-serif;background:#f1f5f9;color:#1e293b}}

/* 侧边栏 */
.sb{{position:fixed;left:0;top:0;width:170px;height:100vh;background:#1e293b;color:#cbd5e1;overflow-y:auto;z-index:100;padding:12px 0}}
.sb::-webkit-scrollbar{{width:3px}}
.sb::-webkit-scrollbar-thumb{{background:#475569;border-radius:2px}}
.sb-title{{padding:6px 16px 14px;font-size:0.7rem;color:#94a3b8;font-weight:600;letter-spacing:1px}}
.sb-a{{display:block;padding:7px 16px;font-size:0.78rem;cursor:pointer;transition:.15s;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.sb-a:hover{{background:#334155;color:#fff}}
.sb-div{{height:1px;background:#334155;margin:6px 12px}}

/* 主区 */
.main{{margin-left:170px;min-height:100vh}}
.page{{display:none;max-width:960px;margin:0 auto;padding:28px 36px}}
.page.active{{display:block}}

/* 封面 */
.cover-page.active{{display:flex!important;align-items:center;justify-content:center;min-height:100vh}}
.cover-inner{{text-align:center;padding:40px}}
.cover-badge{{display:inline-block;background:#4f46e5;color:#fff;padding:4px 18px;border-radius:999px;font-size:0.75rem;font-weight:600;margin-bottom:24px}}
.cover-title{{font-size:2.8rem;font-weight:900;color:#1e293b}}
.cover-subtitle{{font-size:1.4rem;font-weight:300;color:#64748b;margin:8px 0 36px}}
.cover-stats{{display:flex;gap:24px;justify-content:center;align-items:center;flex-wrap:wrap;margin-bottom:32px}}
.cs{{text-align:center;min-width:60px}}
.cs-num{{display:block;font-size:2rem;font-weight:900;color:#4f46e5}}
.cs-label{{font-size:0.75rem;color:#64748b}}
.cs-divider{{width:1px;height:40px;background:#e2e8f0}}
.cover-date{{font-size:0.85rem;color:#94a3b8;margin-bottom:8px}}
.cover-tip{{font-size:0.7rem;color:#cbd5e1}}

/* 通用 */
.ptitle{{font-size:1.3rem;font-weight:800;margin-bottom:20px}}

/* 总览 */
.ov-stats{{display:flex;gap:10px;margin-bottom:20px;flex-wrap:wrap}}
.ovc{{background:#fff;border-radius:10px;padding:14px 20px;text-align:center;box-shadow:0 1px 3px rgba(0,0,0,.05);min-width:80px}}
.ovc-v{{font-size:1.4rem;font-weight:800;color:#4f46e5}}
.ovc-l{{font-size:0.7rem;color:#64748b}}
.ov-table-wrap{{background:#fff;border-radius:10px;padding:12px;box-shadow:0 1px 3px rgba(0,0,0,.05);margin-bottom:20px;overflow-x:auto}}
.ov-table{{width:100%;border-collapse:collapse;font-size:0.82rem}}
.ov-table th{{background:#f8fafc;padding:10px 6px;text-align:center;font-weight:600;color:#475569;border-bottom:2px solid #e2e8f0}}
.ov-table td{{padding:10px 6px;text-align:center;border-bottom:1px solid #f1f5f9}}
.ov-row{{cursor:pointer;transition:.1s}}
.ov-row:hover{{background:#f0f9ff}}
.tl{{text-align:left!important}}
.tw{{color:#dc2626;font-size:0.72rem}}
.ov-chart{{background:#fff;border-radius:10px;padding:16px;box-shadow:0 1px 3px rgba(0,0,0,.05)}}
.ov-chart h3{{font-size:0.85rem;font-weight:600;color:#475569;margin-bottom:10px}}

/* 完整报告 */
.flesson-header{{display:flex;justify-content:space-between;align-items:center;background:#fff;border-radius:12px;padding:20px 24px;margin-bottom:20px;box-shadow:0 1px 4px rgba(0,0,0,.06)}}
.flh-left{{flex:1}}
.flh-tag{{font-size:0.75rem;color:#94a3b8;font-weight:500}}
.flh-title{{font-size:1.2rem;font-weight:700;margin:4px 0}}
.flh-meta{{font-size:0.78rem;color:#94a3b8}}
.flh-right{{text-align:center;min-width:90px}}
.flh-tier-icon{{font-size:2.2rem}}
.flh-score{{font-size:2rem;font-weight:900}}
.flh-score-unit{{font-size:0.85rem;font-weight:400;color:#94a3b8}}
.flh-tier-name{{font-size:0.72rem;color:#64748b}}

.fsection{{margin-bottom:24px;page-break-inside:avoid}}
.fsection-warn{{background:#fffbeb;border-radius:10px;padding:16px}}
.fsection-primary{{background:#eef2ff;border-radius:10px;padding:16px}}
.fstitle{{font-size:0.95rem;font-weight:700;color:#1e293b;margin-bottom:14px;padding-left:10px;border-left:3px solid #4f46e5}}

/* 学科维度 */
.fdims-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:10px}}
.sdim-card{{background:#f8fafc;border-radius:8px;padding:12px}}
.sdim-head{{display:flex;justify-content:space-between;margin-bottom:4px}}
.sdim-name{{font-weight:600;font-size:0.85rem}}
.sdim-score{{font-weight:700;font-size:0.95rem}}
.sdim-bar-bg{{height:5px;background:#e2e8f0;border-radius:3px;overflow:hidden;margin-bottom:6px}}
.sdim-bar{{height:100%;border-radius:3px}}
.sdim-evidence{{font-size:0.72rem;line-height:1.5}}
.sdim-good{{color:#059669}}
.sdim-weak{{color:#d97706}}
.sdim-detail{{font-size:0.72rem;color:#64748b;margin-top:4px;line-height:1.5}}

/* 问题 */
.fproblem{{background:#fff;border-radius:8px;padding:14px;margin-bottom:10px;box-shadow:0 1px 2px rgba(0,0,0,.04)}}
.fproblem-head{{font-size:0.78rem;display:flex;gap:8px;margin-bottom:6px}}
.fproblem-sev{{font-weight:600}}
.fproblem-dim{{color:#64748b}}
.fproblem-text{{font-weight:600;font-size:0.88rem;margin-bottom:6px}}
.fproblem-evidence{{font-size:0.78rem;color:#475569;background:#f8fafc;padding:8px 10px;border-radius:6px;line-height:1.5}}

/* 诊断 */
.fdiag-block{{margin-bottom:14px}}
.fdiag-block h4{{font-size:0.85rem;color:#4f46e5;font-weight:600;margin-bottom:6px}}
.fdiag-text{{font-size:0.82rem;line-height:1.7;color:#334155}}

/* 建议 */
.frec{{display:flex;gap:12px;margin-bottom:12px}}
.frec-num{{width:26px;height:26px;background:#4f46e5;color:#fff;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:0.75rem;font-weight:700;flex-shrink:0;margin-top:2px}}
.frec-body{{flex:1}}
.frec-title{{font-weight:700;font-size:0.88rem;margin-bottom:4px}}
.frec-principle,.frec-current{{font-size:0.78rem;color:#64748b;margin-bottom:2px}}
.frec-action{{font-size:0.82rem;color:#1e293b;background:#f0fdf4;padding:8px 12px;border-radius:6px;border-left:3px solid #10b981;line-height:1.6}}

/* 关注 */
.ffocus-item{{font-size:0.78rem;padding:6px 0;border-bottom:1px solid #e0f2fe}}
.ffocus-item:last-child{{border:none}}

/* 图表 */
.fcharts-grid{{display:grid;grid-template-columns:1fr 1fr;gap:12px}}
.fchart-card{{background:#f8fafc;border-radius:8px;padding:12px}}
.fchart-card h4{{font-size:0.8rem;font-weight:600;color:#475569;margin-bottom:6px;text-align:center}}

/* 翻页 */
.fpage-nav{{display:flex;justify-content:space-between;align-items:center;margin-top:28px;padding-top:16px;border-top:1px solid #e2e8f0}}
.fpn-btn{{background:#f1f5f9;border:none;padding:8px 24px;border-radius:8px;font-size:0.82rem;cursor:pointer;color:#475569;font-weight:500}}
.fpn-btn:hover{{background:#e2e8f0}}
.fpn-pos{{font-size:0.78rem;color:#94a3b8}}

/* 对比 */
.sm-chart{{background:#fff;border-radius:10px;padding:18px;margin-bottom:18px;box-shadow:0 1px 3px rgba(0,0,0,.05)}}
.sm-chart h3{{font-size:0.88rem;font-weight:600;color:#475569;margin-bottom:12px}}

@media print{{
    .sb{{display:none!important}}
    .main{{margin-left:0!important}}
    .page{{display:block!important;page-break-after:always;padding:16px!important}}
    .page:last-child{{page-break-after:auto}}
    .fpage-nav{{display:none!important}}
    body{{background:#fff!important;print-color-adjust:exact!important;-webkit-print-color-adjust:exact!important}}
}}
@media(max-width:768px){{
    .sb{{display:none}}
    .main{{margin-left:0}}
    .fdims-grid{{grid-template-columns:1fr}}
    .fcharts-grid{{grid-template-columns:1fr}}
}}
</style>
</head>
<body>
<div class="sb" id="sidebar">{nav}</div>
<div class="main">
    {cover}
    {overview}
    {" ".join(lesson_pages)}
    {comparison}
</div>
<script>
var _charts={{}};
var _chartsInit=false;
function _ensureCharts(){{
    if(_chartsInit)return;
    _chartsInit=true;
    {chart_js}

    // 总览得分图
    _charts['ov-score']=echarts.init(document.getElementById('ov-score-chart'));
    _charts['ov-score'].setOption({{
        grid:{{top:30,bottom:40,left:50,right:20}},
        xAxis:{{type:'category',data:{labels},axisLabel:{{fontSize:9,rotate:25}}}},
        yAxis:{{type:'value',min:40,max:100,splitLine:{{lineStyle:{{type:'dashed'}}}}}},
        series:[{{type:'bar',data:{scores},itemStyle:{{color:function(p){{return p.data>=75?'#6366f1':'#f59e0b'}},borderRadius:[4,4,0,0]}},label:{{show:true,position:'top',fontSize:10}}}}],
        tooltip:{{trigger:'axis'}}
    }});

    // 对比页
    var names={labels};
    var rMap={json.dumps(radar_map)};
    var colors=['#6366f1','#ec4899','#10b981','#f59e0b','#8b5cf6','#f43f5e','#06b6d4','#84cc16','#a855f7','#14b8a6','#eab308'];
    var rs=[];
    for(var i=0;i<names.length;i++){{rs.push({{value:rMap[names[i]],name:names[i],lineStyle:{{width:1.5,color:colors[i%colors.length]}},itemStyle:{{color:colors[i%colors.length]}},areaStyle:{{opacity:.04}}}})}}

    _charts['sm-score']=echarts.init(document.getElementById('sm-score'));
    _charts['sm-score'].setOption({{
        grid:{{top:30,bottom:40,left:50,right:20}},
        xAxis:{{type:'category',data:{labels},axisLabel:{{fontSize:9,rotate:25}}}},
        yAxis:{{type:'value',min:40,max:100,splitLine:{{lineStyle:{{type:'dashed'}}}}}},
        series:[{{type:'bar',data:{scores},itemStyle:{{color:'#6366f1',borderRadius:[4,4,0,0]}},label:{{show:true,position:'top',fontSize:10}}}}],
        tooltip:{{trigger:'axis'}}
    }});
    _charts['sm-radar']=echarts.init(document.getElementById('sm-radar'));
    _charts['sm-radar'].setOption({{
        legend:{{bottom:0,textStyle:{{fontSize:8}}}},
        radar:{{indicator:[{{name:'逻辑',max:100}},{{name:'互动',max:100}},{{name:'提问',max:100}},{{name:'支持',max:100}},{{name:'管理',max:100}}],radius:'65%',splitNumber:4}},
        series:[{{type:'radar',data:rs}}]
    }});
    _charts['sm-dim']=echarts.init(document.getElementById('sm-dim'));
    _charts['sm-dim'].setOption({{
        grid:{{top:30,bottom:40,left:50,right:20}},
        legend:{{bottom:0,textStyle:{{fontSize:9}}}},
        xAxis:{{type:'category',data:{labels},axisLabel:{{fontSize:9,rotate:25}}}},
        yAxis:{{type:'value',min:30,max:100,splitLine:{{lineStyle:{{type:'dashed'}}}}}},
        tooltip:{{trigger:'axis'}},
        series:[{dim_series}]
    }});
}}
function showPage(id){{
    document.querySelectorAll('.page').forEach(p=>p.classList.remove('active'));
    var el=document.getElementById(id);
    if(el)el.classList.add('active');
    window.scrollTo(0,0);
    setTimeout(function(){{
        _ensureCharts();
        Object.values(_charts).forEach(function(c){{c.resize()}});
    }},50);
}}
showPage('cover');

window.onload=function(){{
    _ensureCharts();
}};
</script>
</body>
</html>"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"报告册已生成: {output_path} ({len(html)//1024}KB)")


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--data-dir", default="F:/1濮东-课堂录音")
    p.add_argument("--output", default=None)
    p.add_argument("--school", default="濮东小学")
    args = p.parse_args()
    output = args.output or f"{args.data_dir}/{args.school}_AI课堂诊断报告册.html"

    all_data = []
    for d in sorted(Path(args.data_dir).glob("第*次课*")):
        if not d.is_dir(): continue
        jsons = sorted(d.glob("ICAS_v3_data_*.json"))
        if jsons:
            with open(jsons[-1], "r", encoding="utf-8") as f:
                all_data.append(json.load(f))
    print(f"加载 {len(all_data)} 次课数据")
    generate_booklet(all_data, output, args.school)
