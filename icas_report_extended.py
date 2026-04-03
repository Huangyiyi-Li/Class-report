# -*- coding: utf-8 -*-
"""
ICAS 扩展分析 - HTML片段生成模块
"""

import json
import time
import markdown

def _safe_get(data, *keys, default=None):
    current = data
    for k in keys:
        if not isinstance(current, dict):
            return default
        current = current.get(k, None)
        if current is None:
            return default
    return current if current is not None else default
def _s(data, path, default=""):
    keys = path.split('.')
    obj = data
    for k in keys:
        if isinstance(obj, dict) and k in obj:
            obj = obj[k]
        else:
            return default
    return obj
def _md(text):
    if not text:
        return ""
    return markdown.markdown(str(text), extensions=["nl2br"])
def _fmt_minutes(m):
    if m is None:
        return "-"
    try:
        m = float(m)
    except (TypeError, ValueError):
        return "-"
    if m >= 60:
        h = int(m // 60)
        mins = int(m % 60)
        return f"{h}小时{mins}分" if mins else f"{h}小时"
    mins = int(m)
    secs = int((m - mins) * 60)
    return f"{mins}分{secs}秒" if secs else f"{mins}分钟"
def _build_css():
    """返回报告页面所需的完整CSS样式 — Scholar's Atelier 暖色学术风"""
    return """
    <style>
    /* ============================================
       ICAS Report v3 — Scholar's Atelier
       Warm Academic Luxury · Editorial Journal Style
       ============================================ */
    @import url('https://fonts.googleapis.com/css2?family=Noto+Serif+SC:wght@400;600;700;900&family=Playfair+Display:wght@700;900&display=swap');

    /* ---------- Design Tokens ---------- */
    :root {
        --sidebar-w: 260px;

        /* Warm Academic Palette */
        --parchment: #faf6f0;
        --parchment-deep: #f0ebe0;
        --ink: #1c1917;
        --ink-soft: #3d3630;
        --ink-muted: #78716c;
        --gold: #b8860b;
        --gold-bright: #daa520;
        --gold-pale: #f5e6c8;
        --gold-wash: #faf3e0;
        --wine: #8b2252;
        --wine-soft: #c9a0b8;
        --sage: #4a7c59;
        --sage-wash: #e8f0ea;
        --navy: #2c3e50;
        --navy-soft: #5a7d95;
        --terra: #c4713b;
        --terra-wash: #fdf0e8;

        /* Functional */
        --sidebar-bg: #1c1917;
        --sidebar-text: #a8a29e;
        --sidebar-heading: #e7e5e4;
        --page-bg: var(--parchment);
        --card-bg: #fffdf8;
        --card-bg-hover: #fffcf3;
        --border: #e7e0d4;
        --border-light: #f0ebe0;
        --shadow-sm: 0 1px 4px rgba(28,25,23,0.06), 0 1px 2px rgba(28,25,23,0.04);
        --shadow-md: 0 4px 12px rgba(28,25,23,0.07);
        --shadow-lg: 0 8px 24px rgba(28,25,23,0.09);
        --radius-sm: 5px;
        --radius: 10px;
        --radius-lg: 14px;
    }

    /* ---------- Reset ---------- */
    *, *::before, *::after { box-sizing: border-box; }
    html { scroll-behavior: smooth; }

    body {
        margin: 0; padding: 0;
        background: var(--parchment);
        background-image:
            radial-gradient(ellipse at 20% 50%, rgba(184,134,11,0.03) 0%, transparent 50%),
            radial-gradient(ellipse at 80% 20%, rgba(139,34,82,0.02) 0%, transparent 50%);
        font-family: "Noto Sans SC", "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif;
        color: var(--ink);
        line-height: 1.75;
        font-size: 14px;
        -webkit-font-smoothing: antialiased;
    }

    /* ---------- Main Content ---------- */
    .main-content {
        margin-left: var(--sidebar-w);
        min-height: 100vh;
        transition: margin-left 0.35s cubic-bezier(0.4,0,0.2,1);
    }

    .report-content-wrap {
        max-width: 920px;
        margin: 0 auto;
        padding: 28px 40px 48px;
    }

    @media (max-width: 1200px) {
        .report-content-wrap { padding: 24px 24px 36px; }
    }

    /* ---------- Scrollbar ---------- */
    ::-webkit-scrollbar { width: 5px; height: 5px; }
    ::-webkit-scrollbar-track { background: var(--parchment-deep); }
    ::-webkit-scrollbar-thumb { background: var(--gold-pale); border-radius: 3px; }
    ::-webkit-scrollbar-thumb:hover { background: var(--gold); }

    /* ============================================
       HEADER — 深色墨韵
       ============================================ */
    .report-header {
        background: linear-gradient(135deg, #1c1917 0%, #292524 30%, #3d3630 70%, #57534e 100%);
        color: #faf6f0;
        padding: 40px 44px 32px;
        position: relative;
        overflow: hidden;
        border-bottom: 3px solid var(--gold);
    }

    .report-header::before {
        content: '';
        position: absolute;
        top: -40%; right: -5%;
        width: 500px; height: 500px;
        background: radial-gradient(circle, rgba(184,134,11,0.12) 0%, transparent 65%);
        border-radius: 50%;
        pointer-events: none;
    }

    .report-header::after {
        content: '';
        position: absolute;
        bottom: -40%; left: 15%;
        width: 400px; height: 400px;
        background: radial-gradient(circle, rgba(139,34,82,0.08) 0%, transparent 65%);
        border-radius: 50%;
        pointer-events: none;
    }

    .header-top {
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        position: relative;
        z-index: 1;
    }

    .header-brand { flex: 1; }

    .report-header .report-title {
        font-family: "Noto Serif SC", "Playfair Display", serif;
        font-size: 28px;
        font-weight: 900;
        margin: 0;
        letter-spacing: 2px;
        color: #faf6f0;
        text-shadow: 0 1px 3px rgba(0,0,0,0.3);
    }

    .header-subtitle {
        display: inline-block;
        margin-top: 8px;
        padding: 4px 14px;
        font-size: 10px;
        font-weight: 700;
        letter-spacing: 2.5px;
        color: var(--gold-bright);
        background: rgba(184,134,11,0.15);
        border: 1px solid rgba(184,134,11,0.3);
        border-radius: 2px;
    }

    .header-meta {
        display: flex;
        gap: 16px;
        font-size: 12px;
        color: rgba(250,246,240,0.5);
        position: relative;
        z-index: 1;
        letter-spacing: 0.3px;
    }

    .header-meta i { margin-right: 5px; color: var(--gold); }

    .header-tags {
        display: flex;
        align-items: center;
        gap: 10px;
        margin-top: 20px;
        flex-wrap: wrap;
        position: relative;
        z-index: 1;
    }

    .style-tag {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 5px 16px;
        font-size: 13px;
        font-weight: 600;
        color: #faf6f0;
        background: rgba(184,134,11,0.2);
        border: 1px solid rgba(184,134,11,0.35);
        border-radius: 2px;
    }

    .style-tag i { color: var(--gold-bright); }

    .keyword-pills { display: flex; flex-wrap: wrap; gap: 6px; }

    .keyword-pill {
        padding: 3px 12px;
        font-size: 11px;
        letter-spacing: 0.3px;
        color: rgba(250,246,240,0.65);
        background: rgba(250,246,240,0.06);
        border-radius: 2px;
        border: 1px solid rgba(250,246,240,0.08);
    }

    /* KPI Row */
    .kpi-row {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 14px;
        margin-top: 24px;
        position: relative;
        z-index: 1;
    }

    .kpi-card {
        background: rgba(250,246,240,0.08);
        border: 1px solid rgba(250,246,240,0.1);
        border-radius: var(--radius);
        padding: 16px 18px;
        display: flex;
        align-items: center;
        gap: 14px;
        transition: background 0.2s, border-color 0.2s;
    }

    .kpi-card:hover {
        background: rgba(250,246,240,0.14);
        border-color: rgba(184,134,11,0.3);
    }

    .kpi-icon {
        width: 40px; height: 40px;
        border-radius: 8px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 16px;
        flex-shrink: 0;
    }

    .kpi-blue .kpi-icon { background: rgba(44,62,80,0.5); color: var(--navy-soft); }
    .kpi-green .kpi-icon { background: rgba(74,124,89,0.4); color: #a3d4b5; }
    .kpi-purple .kpi-icon { background: rgba(107,91,138,0.4); color: #c4b5d8; }
    .kpi-orange .kpi-icon { background: rgba(196,113,59,0.4); color: #e8b88a; }

    .kpi-body { display: flex; flex-direction: column; }
    .kpi-value { font-family: "Noto Serif SC", serif; font-size: 22px; font-weight: 900; line-height: 1.2; color: #faf6f0; }
    .kpi-label { font-size: 10px; letter-spacing: 0.5px; color: rgba(250,246,240,0.45); margin-top: 3px; text-transform: uppercase; }

    .kpi-row--compact {
        grid-template-columns: repeat(3, 1fr);
        margin-top: 0;
    }

    .kpi-row--compact .kpi-card {
        background: var(--card-bg);
        border: 1px solid var(--border);
        color: var(--ink);
    }

    .kpi-row--compact .kpi-value { color: var(--ink); font-size: 20px; }
    .kpi-row--compact .kpi-label { color: var(--ink-muted); }

    /* ============================================
       GROUP LABELS — 金色装饰线
       ============================================ */
    .group-label {
        display: flex;
        align-items: center;
        gap: 12px;
        margin: 32px 0 16px;
        padding: 0 4px;
        font-family: "Noto Serif SC", serif;
        font-size: 13px;
        font-weight: 700;
        letter-spacing: 1px;
        color: var(--ink-muted);
        text-transform: uppercase;
    }

    .group-label::after {
        content: '';
        flex: 1;
        height: 1px;
        background: linear-gradient(90deg, var(--gold-pale) 0%, transparent 100%);
    }

    .group-label--a { color: var(--gold); }
    .group-label--b { color: var(--navy); }
    .group-label--c { color: var(--wine); }
    .group-label--d { color: var(--sage); }

    /* ============================================
       SECTION CARDS — 纸质卡片
       ============================================ */
    .section-card {
        background: var(--card-bg);
        border-radius: var(--radius-lg);
        padding: 0;
        margin-bottom: 18px;
        box-shadow: var(--shadow-sm);
        border: 1px solid var(--border);
        overflow: hidden;
        transition: box-shadow 0.25s, border-color 0.25s;
        position: relative;
    }

    .section-card::before {
        content: '';
        position: absolute;
        top: 0; left: 0; right: 0; bottom: 0;
        background: linear-gradient(135deg, rgba(250,246,240,0.5) 0%, transparent 50%);
        pointer-events: none;
        z-index: 0;
    }

    .section-card:hover {
        box-shadow: var(--shadow-md);
        border-color: var(--gold-pale);
    }

    .section-title {
        display: flex;
        align-items: center;
        gap: 12px;
        margin: 0;
        padding: 18px 24px 14px;
        font-family: "Noto Serif SC", serif;
        font-size: 16px;
        font-weight: 700;
        color: var(--ink);
        border-bottom: 1px solid var(--border-light);
        position: relative;
        z-index: 1;
    }

    .section-title i {
        font-size: 14px;
        width: 30px;
        height: 30px;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        border-radius: var(--radius-sm);
        color: #fff;
    }

    .section-body {
        padding: 18px 24px 22px;
        position: relative;
        z-index: 1;
    }

    /* ============================================
       PROSE CONTENT — 排版优化
       ============================================ */
    .prose-content {
        font-size: 14px;
        line-height: 1.85;
        color: var(--ink-soft);
    }
    .prose-content p { margin: 0 0 12px; }
    .prose-content strong { color: var(--ink); font-weight: 700; }
    .prose-content ul, .prose-content ol { margin: 8px 0; padding-left: 22px; }
    .prose-content li { margin-bottom: 5px; }
    .prose-content h1, .prose-content h2, .prose-content h3 {
        font-family: "Noto Serif SC", serif;
        color: var(--ink);
        margin: 18px 0 10px;
    }

    .text-muted { color: var(--ink-muted); font-style: italic; }

    /* ============================================
       CHART LAYOUTS
       ============================================ */
    .chart-container {
        background: var(--parchment);
        border: 1px solid var(--border-light);
        border-radius: var(--radius);
        padding: 14px;
        page-break-inside: avoid;
        break-inside: avoid;
    }

    .chart-with-side {
        display: grid;
        grid-template-columns: 1fr 180px;
        gap: 20px;
        align-items: center;
    }

    .chart-side.time-stats {
        display: flex;
        flex-direction: column;
        gap: 10px;
    }

    .time-stat-item {
        display: flex;
        align-items: center;
        gap: 8px;
        font-size: 13px;
        color: var(--ink-soft);
    }

    .time-stat-item .dot {
        width: 8px; height: 8px;
        border-radius: 50%;
        flex-shrink: 0;
    }

    .time-stat-item .label { flex: 1; }

    .time-stat-item .value {
        font-family: "Noto Serif SC", serif;
        font-weight: 700;
        color: var(--ink);
        font-variant-numeric: tabular-nums;
    }

    .chart-row {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 16px;
    }

    .chart-half { min-width: 0; }

    /* ============================================
       CHECKLIST — 温暖色调
       ============================================ */
    .checklist-grid {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 12px;
    }

    .checklist-item {
        background: var(--parchment);
        border: 1px solid var(--border);
        border-radius: var(--radius);
        padding: 14px 16px;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }

    .check-label { font-family: "Noto Serif SC", serif; font-weight: 600; font-size: 14px; color: var(--ink); }

    .check-status { font-size: 13px; display: flex; align-items: center; gap: 6px; }

    .check-done { color: var(--sage); font-weight: 600; }
    .check-not { color: var(--ink-muted); }

    .homework-detail {
        margin-top: 12px;
        padding: 14px 18px;
        background: var(--gold-wash);
        border: 1px solid var(--gold-pale);
        border-left: 3px solid var(--gold);
        border-radius: var(--radius);
        font-size: 13px;
        color: #6b5a2e;
    }

    /* ============================================
       RECOMMEND CARDS — 学术建议卡片
       ============================================ */
    .recommend-card {
        background: var(--parchment);
        border-radius: var(--radius);
        padding: 18px 22px;
        margin-bottom: 14px;
        border-left: 4px solid var(--gold);
        transition: background 0.2s, border-color 0.2s;
    }

    .recommend-card:hover {
        background: var(--parchment-deep);
        border-left-color: var(--gold-bright);
    }

    .recommend-header {
        display: flex;
        align-items: center;
        gap: 12px;
        margin-bottom: 12px;
    }

    .recommend-num {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 28px; height: 28px;
        border-radius: 50%;
        background: var(--ink);
        color: var(--gold-bright);
        font-family: "Noto Serif SC", serif;
        font-size: 13px;
        font-weight: 900;
        flex-shrink: 0;
    }

    .recommend-title { font-family: "Noto Serif SC", serif; font-weight: 700; font-size: 15px; color: var(--ink); }

    .recommend-body { padding-left: 40px; }

    /* ============================================
       ST ANALYSIS — 数据徽章
       ============================================ */
    .st-summary {
        display: flex;
        gap: 12px;
        flex-wrap: wrap;
        margin-bottom: 16px;
    }

    .st-badge {
        background: var(--parchment);
        border: 1px solid var(--border);
        border-radius: var(--radius);
        padding: 12px 20px;
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 3px;
    }

    .st-label { font-size: 10px; color: var(--ink-muted); text-transform: uppercase; letter-spacing: 1px; }

    .st-value { font-family: "Noto Serif SC", serif; font-size: 20px; font-weight: 900; color: var(--ink); }

    .st-badge--type .st-value { color: var(--gold); }

    .st-type-desc {
        margin: 12px 0;
        padding: 12px 18px;
        background: var(--gold-wash);
        border-radius: var(--radius);
        font-size: 13px;
        color: #6b5a2e;
        border-left: 3px solid var(--gold);
    }

    .st-suggestions {
        margin: 14px 0 0;
        padding-left: 22px;
        font-size: 13px;
        color: var(--ink-soft);
    }

    .st-suggestions li { margin-bottom: 5px; }

    /* ============================================
       SPEECH EVAL
       ============================================ */
    .speech-eval {
        margin-top: 16px;
        padding: 16px 20px;
        background: var(--parchment);
        border-radius: var(--radius);
        border: 1px solid var(--border);
    }

    /* ============================================
       DESIGN EXCERPT — 教案引用
       ============================================ */
    .design-excerpt {
        margin-top: 18px;
        padding: 18px 22px;
        background: var(--gold-wash);
        border: 1px solid var(--gold-pale);
        border-radius: var(--radius);
        border-left: 3px solid var(--gold);
    }

    .design-excerpt h4 {
        margin: 0 0 10px;
        font-family: "Noto Serif SC", serif;
        font-size: 14px;
        font-weight: 700;
        color: #6b5a2e;
    }

    .design-excerpt h4 i { margin-right: 6px; color: var(--gold); }

    .design-text {
        font-size: 13px;
        color: #5a4a28;
        line-height: 1.65;
    }

    /* ============================================
       KNOWLEDGE GRAPH LOGIC
       ============================================ */
    .kg-logic {
        margin-top: 16px;
        padding: 16px 20px;
        background: var(--parchment);
        border-radius: var(--radius);
        border: 1px solid var(--border);
    }

    /* ============================================
       CHAIN CARDS (Group C) — 葡萄酒色系
       ============================================ */
    .chain-card {
        background: var(--parchment);
        border: 1px solid var(--border);
        border-radius: var(--radius);
        padding: 16px 20px;
        margin-bottom: 12px;
        transition: box-shadow 0.2s, border-color 0.2s;
    }

    .chain-card:hover {
        box-shadow: var(--shadow-sm);
        border-color: var(--wine-soft);
    }

    .chain-header {
        display: flex;
        align-items: center;
        gap: 10px;
        margin-bottom: 10px;
    }

    .chain-tag {
        display: inline-block;
        padding: 3px 12px;
        border-radius: 2px;
        color: #faf6f0;
        font-size: 11px;
        font-weight: 700;
        flex-shrink: 0;
    }

    .chain-topic { font-family: "Noto Serif SC", serif; font-size: 14px; font-weight: 700; color: var(--ink); }

    .chain-meta { display: flex; gap: 6px; margin-bottom: 10px; }

    .chain-badge {
        font-size: 11px;
        padding: 3px 12px;
        background: var(--wine-soft);
        color: var(--wine);
        border-radius: 2px;
        border: 1px solid rgba(139,34,82,0.2);
    }

    .chain-badge--gray {
        background: var(--parchment);
        color: var(--ink-soft);
        border-color: var(--border);
    }

    .chain-questions {
        margin: 0;
        padding-left: 20px;
        font-size: 13px;
        color: var(--ink-soft);
        line-height: 1.7;
    }

    .chain-questions li { margin-bottom: 4px; }

    /* Insight Boxes */
    .insight-box {
        padding: 14px 18px;
        border-radius: var(--radius);
        font-size: 13px;
        line-height: 1.7;
        margin-top: 12px;
    }

    .insight-analysis {
        background: var(--parchment);
        border: 1px solid var(--border);
        color: var(--ink-soft);
    }

    .insight-suggestion {
        background: var(--sage-wash);
        border: 1px solid rgba(74,124,89,0.2);
        color: var(--sage);
    }

    .insight-label {
        font-family: "Noto Serif SC", serif;
        font-weight: 700;
        margin-right: 6px;
        color: var(--ink);
    }

    /* ============================================
       MICRO MOMENTS — 互动切片
       ============================================ */
    .no-break { page-break-inside: avoid; break-inside: avoid; }

    .micro-card {
        background: var(--parchment);
        border: 1px solid var(--border);
        border-radius: var(--radius-lg);
        padding: 22px;
        margin-bottom: 16px;
        transition: box-shadow 0.2s;
    }

    .micro-card:hover { box-shadow: var(--shadow-md); }

    .micro-title {
        font-family: "Noto Serif SC", serif;
        font-size: 15px;
        font-weight: 700;
        color: var(--ink);
        margin: 0 0 14px;
        padding-bottom: 12px;
        border-bottom: 2px solid var(--gold-pale);
    }

    .micro-dialogue {
        background: var(--parchment-deep);
        padding: 14px 18px;
        border-radius: var(--radius);
        border-left: 3px solid var(--gold);
        font-size: 13px;
        font-family: "Menlo", "Consolas", "Noto Sans SC", monospace;
        color: var(--ink-soft);
        white-space: pre-wrap;
        line-height: 1.8;
        margin-bottom: 16px;
    }

    .micro-analysis {
        display: flex;
        gap: 12px;
        align-items: flex-start;
    }

    .micro-analysis-label {
        display: inline-block;
        padding: 4px 12px;
        background: var(--ink);
        color: var(--gold-bright);
        border-radius: 2px;
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 0.5px;
        flex-shrink: 0;
        margin-top: 2px;
    }

    .micro-analysis p {
        margin: 0;
        font-size: 13px;
        color: var(--ink-soft);
        line-height: 1.8;
        font-style: italic;
    }

    /* ============================================
       THINKING CARDS (Group D) — 鼠尾草绿
       ============================================ */
    .thinking-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
        gap: 14px;
    }

    .thinking-card {
        border-radius: var(--radius);
        border: 1px solid;
        padding: 16px 20px;
        transition: transform 0.2s, box-shadow 0.2s;
    }

    .thinking-card:hover {
        transform: translateY(-2px);
        box-shadow: var(--shadow-md);
    }

    .thinking-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 10px;
    }

    .thinking-type { font-family: "Noto Serif SC", serif; font-size: 14px; font-weight: 700; color: var(--ink); }

    .thinking-level {
        font-size: 11px;
        font-weight: 700;
        padding: 3px 12px;
        border-radius: 2px;
        color: #faf6f0;
    }

    .thinking-analysis {
        font-size: 13px;
        color: var(--ink-soft);
        line-height: 1.7;
        margin: 0 0 8px;
    }

    .thinking-suggestion {
        font-size: 12px;
        color: var(--sage);
        margin: 0;
    }

    /* ============================================
       RESPONSE STATS — 数据面板
       ============================================ */
    .response-stats {
        display: flex;
        flex-direction: column;
        gap: 10px;
        justify-content: center;
    }

    .resp-stat {
        display: flex;
        justify-content: space-between;
        align-items: baseline;
        padding: 10px 16px;
        background: var(--parchment);
        border-radius: var(--radius-sm);
        border: 1px solid var(--border);
    }

    .resp-stat-label { font-size: 13px; color: var(--ink-soft); }

    .resp-stat-value {
        font-family: "Noto Serif SC", serif;
        font-size: 18px;
        font-weight: 900;
        color: var(--ink);
        font-variant-numeric: tabular-nums;
    }

    .resp-stat-value small { font-size: 12px; font-weight: 400; color: var(--ink-muted); }

    /* ============================================
       PHRASE CARDS — 引用样式
       ============================================ */
    .phrase-section {
        margin-top: 20px;
        padding-top: 20px;
        border-top: 1px solid var(--border);
    }

    .phrase-heading {
        font-family: "Noto Serif SC", serif;
        font-size: 14px;
        font-weight: 700;
        color: var(--ink);
        margin: 0 0 14px;
    }

    .phrase-heading i { margin-right: 6px; color: var(--gold); }

    .phrase-card {
        background: var(--parchment);
        border-left: 3px solid var(--gold);
        padding: 12px 18px;
        border-radius: 0 var(--radius) var(--radius) 0;
        margin-bottom: 10px;
    }

    .phrase-text {
        font-family: "Noto Serif SC", serif;
        font-size: 14px;
        font-style: italic;
        font-weight: 600;
        color: var(--ink);
        margin: 0 0 4px;
    }

    .phrase-meta {
        font-size: 12px;
        color: var(--ink-muted);
    }

    /* ============================================
       SIDEBAR — 墨色学术风
       ============================================ */
    .sidebar {
        position: fixed;
        top: 0; left: 0;
        width: var(--sidebar-w);
        height: 100vh;
        background: var(--sidebar-bg);
        color: var(--sidebar-text);
        overflow-y: auto;
        z-index: 1000;
        transition: transform 0.35s cubic-bezier(0.4,0,0.2,1);
        display: flex;
        flex-direction: column;
        border-right: 1px solid rgba(184,134,11,0.15);
    }

    .sidebar-header {
        padding: 28px 22px 18px;
        border-bottom: 1px solid rgba(184,134,11,0.15);
        background: linear-gradient(180deg, rgba(184,134,11,0.08) 0%, transparent 100%);
    }

    .sidebar-header .report-title {
        font-family: "Noto Serif SC", serif;
        font-size: 14px;
        font-weight: 700;
        color: var(--sidebar-heading);
        display: flex;
        align-items: center;
        gap: 10px;
    }

    .sidebar-header .report-title .title-icon {
        width: 34px; height: 34px;
        background: linear-gradient(135deg, var(--gold) 0%, var(--gold-bright) 100%);
        border-radius: 4px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-family: "Playfair Display", serif;
        font-size: 11px;
        color: var(--ink);
        font-weight: 900;
        flex-shrink: 0;
        box-shadow: 0 2px 8px rgba(184,134,11,0.3);
    }

    .sidebar-header .report-subtitle {
        font-size: 9px;
        letter-spacing: 1.5px;
        color: var(--ink-muted);
        margin-top: 4px;
        padding-left: 44px;
    }

    .sidebar-body {
        flex: 1;
        overflow-y: auto;
        padding: 10px 0;
    }

    .sidebar-group { margin-bottom: 2px; }

    .sidebar-group-header {
        padding: 12px 22px;
        font-size: 10px;
        font-weight: 700;
        color: var(--ink-muted);
        text-transform: uppercase;
        letter-spacing: 1.5px;
        cursor: pointer;
        display: flex;
        align-items: center;
        justify-content: space-between;
        user-select: none;
        transition: color 0.2s;
    }

    .sidebar-group-header:hover { color: var(--gold); }

    .sidebar-group-header .toggle-arrow {
        font-size: 8px;
        transition: transform 0.2s;
        opacity: 0.4;
    }

    .sidebar-group.collapsed .toggle-arrow { transform: rotate(-90deg); }
    .sidebar-group.collapsed .sidebar-group-items { display: none; }

    .sidebar-item {
        padding: 7px 22px 7px 34px;
        display: flex;
        align-items: center;
        gap: 10px;
        cursor: pointer;
        font-size: 12px;
        color: var(--sidebar-text);
        transition: all 0.15s;
        border-left: 2px solid transparent;
    }

    .sidebar-item:hover {
        background: rgba(184,134,11,0.06);
        color: var(--sidebar-heading);
        border-left-color: rgba(184,134,11,0.3);
    }

    .sidebar-item input[type="checkbox"] {
        accent-color: var(--gold);
        width: 14px; height: 14px;
        cursor: pointer;
        flex-shrink: 0;
    }

    .sidebar-item .nav-label {
        cursor: pointer;
        flex: 1;
        font-size: 12px;
    }

    .sidebar-item .nav-arrow {
        font-size: 13px;
        color: rgba(184,134,11,0.25);
        cursor: pointer;
        padding: 2px 5px;
        border-radius: 3px;
        transition: all 0.15s;
        flex-shrink: 0;
    }

    .sidebar-item .nav-arrow:hover {
        color: var(--gold-bright);
        background: rgba(184,134,11,0.12);
    }

    .sidebar-item.active {
        background: rgba(184,134,11,0.1);
        border-left-color: var(--gold);
    }

    .sidebar-item.active .nav-label {
        color: var(--gold);
        font-weight: 600;
    }

    .section-highlight {
        animation: sectionPulse 1.5s ease-out;
    }

    @keyframes sectionPulse {
        0% { box-shadow: 0 0 0 0 rgba(184,134,11,0.4); }
        30% { box-shadow: 0 0 0 4px rgba(184,134,11,0.2); }
        100% { box-shadow: var(--shadow-sm); }
    }

    .sidebar-footer {
        padding: 16px 18px;
        border-top: 1px solid rgba(184,134,11,0.15);
    }

    .sidebar-footer .btn-row {
        display: flex;
        gap: 8px;
        margin-bottom: 10px;
    }

    .sidebar-footer .btn-row button {
        flex: 1;
        padding: 8px 0;
        font-size: 11px;
        font-weight: 600;
        letter-spacing: 0.5px;
        border: 1px solid rgba(250,246,240,0.1);
        border-radius: var(--radius-sm);
        background: transparent;
        color: var(--sidebar-text);
        cursor: pointer;
        transition: all 0.15s;
    }

    .sidebar-footer .btn-row button:hover {
        background: rgba(184,134,11,0.1);
        color: var(--gold);
        border-color: rgba(184,134,11,0.2);
    }

    .btn-export-pdf {
        display: block;
        width: 100%;
        padding: 12px 0;
        font-family: "Noto Serif SC", serif;
        font-size: 13px;
        font-weight: 700;
        letter-spacing: 1px;
        border: none;
        border-radius: var(--radius-sm);
        background: linear-gradient(135deg, var(--gold) 0%, var(--gold-bright) 100%);
        color: var(--ink);
        cursor: pointer;
        text-align: center;
        transition: all 0.25s;
        box-shadow: 0 2px 10px rgba(184,134,11,0.3);
    }

    .btn-export-pdf:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 16px rgba(184,134,11,0.4);
    }

    /* ---------- Hamburger ---------- */
    .hamburger-btn {
        display: none;
        position: fixed;
        top: 14px; left: 14px;
        z-index: 1100;
        width: 42px; height: 42px;
        border-radius: var(--radius-sm);
        background: var(--sidebar-bg);
        border: 1px solid rgba(184,134,11,0.3);
        color: var(--gold);
        font-size: 18px;
        cursor: pointer;
        box-shadow: var(--shadow-lg);
        align-items: center;
        justify-content: center;
        line-height: 1;
    }

    .sidebar-overlay {
        display: none;
        position: fixed;
        top: 0; left: 0;
        width: 100%; height: 100%;
        background: rgba(28,25,23,0.6);
        backdrop-filter: blur(3px);
        z-index: 999;
    }

    /* ============================================
       RESPONSIVE
       ============================================ */
    @media (max-width: 1024px) {
        .kpi-row { grid-template-columns: repeat(2, 1fr); }
        .kpi-row--compact { grid-template-columns: repeat(3, 1fr); }
        .chart-with-side { grid-template-columns: 1fr; }
        .chart-row { grid-template-columns: 1fr; }
        .checklist-grid { grid-template-columns: repeat(2, 1fr); }
    }

    @media (max-width: 767px) {
        .hamburger-btn { display: flex; }
        .sidebar { transform: translateX(-100%); }
        .sidebar.open { transform: translateX(0); }
        .sidebar-overlay.open { display: block; }

        .main-content {
            margin-left: 0;
            padding: 0;
        }

        .report-header { padding: 56px 18px 22px; }
        .header-top { flex-direction: column; gap: 8px; }
        .report-header .report-title { font-size: 22px; }

        .kpi-row { grid-template-columns: repeat(2, 1fr); gap: 10px; }
        .kpi-row--compact { grid-template-columns: 1fr 1fr 1fr; }
        .kpi-card { padding: 12px; }
        .kpi-value { font-size: 18px; }

        .section-title { padding: 16px 18px 12px; font-size: 15px; }
        .section-body { padding: 14px 18px 18px; }
        .section-card { margin-bottom: 14px; }

        .checklist-grid { grid-template-columns: 1fr; }

        .chart-container [id$="-chart"] { height: 220px !important; }

        .group-label { margin: 22px 18px 12px; }
    }

    /* ============================================
       PRINT — A4 纸质打印效果
       ============================================ */
    @media print {
        @page {
            size: A4;
            margin: 15mm 12mm;
        }

        .sidebar,
        .hamburger-btn,
        .sidebar-overlay,
        .no-print,
        .nav-arrow {
            display: none !important;
            position: static !important;
        }

        .main-content {
            margin-left: 0 !important;
            padding: 0 !important;
            max-width: 100% !important;
            background: #fff;
        }

        .report-content-wrap {
            max-width: 100% !important;
            padding: 0 !important;
        }

        .no-print-section { display: none !important; }

        body {
            background: #fff;
            -webkit-print-color-adjust: exact;
            print-color-adjust: exact;
        }

        .section-card {
            break-inside: avoid;
            page-break-inside: avoid;
            box-shadow: none;
            border: 1px solid #d4c5a9;
            border-radius: 3px;
            margin-bottom: 18px;
            background: #fffef9;
            position: relative;
        }

        .section-card::before {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0; bottom: 0;
            border: 1px solid rgba(184,134,11,0.06);
            border-radius: 3px;
            pointer-events: none;
        }

        .section-card:hover {
            transform: none;
            box-shadow: none;
        }

        .report-header {
            background: #1c1917 !important;
            color: #faf6f0 !important;
            -webkit-print-color-adjust: exact;
            print-color-adjust: exact;
            padding: 18px 24px 14px !important;
            border-bottom: 3px solid #b8860b !important;
            border-radius: 3px;
            margin-bottom: 14px;
            break-after: avoid;
            page-break-after: avoid;
        }

        .kpi-card {
            background: rgba(250,246,240,0.12) !important;
            -webkit-print-color-adjust: exact;
            print-color-adjust: exact;
            border: 1px solid rgba(250,246,240,0.15);
        }

        .section-title {
            page-break-after: avoid;
            break-after: avoid;
            border-bottom: 1px solid var(--border);
            padding-bottom: 10px !important;
        }

        .section-title i {
            -webkit-print-color-adjust: exact;
            print-color-adjust: exact;
        }

        .group-label {
            page-break-after: avoid;
            break-after: avoid;
            page-break-before: auto;
            margin-top: 22px;
            padding: 8px 14px;
            border-bottom: 2px solid var(--border);
        }

        .chart-container,
        .chart-row,
        .chart-half,
        .chart-with-side,
        .chart-main {
            page-break-inside: avoid;
            break-inside: avoid;
        }

        .recommend-card,
        .micro-card,
        .chain-card,
        .thinking-card,
        .phrase-card,
        .checklist-item,
        .st-summary,
        .st-badge {
            break-inside: avoid;
            page-break-inside: avoid;
        }

        p { orphans: 3; widows: 3; }
        h1, h2, h3 { page-break-after: avoid; break-after: avoid; }

        .section-highlight { animation: none !important; box-shadow: none !important; }

        .insight-box {
            break-inside: avoid;
            page-break-inside: avoid;
        }

        .print-hide { display: none !important; }

        /* === A4 适配：单列布局 === */
        .chart-row { grid-template-columns: 1fr !important; gap: 16px !important; }
        .chart-half { width: 100% !important; max-width: 100% !important; }
        .chart-with-side { grid-template-columns: 1fr !important; }
        .kpi-row { grid-template-columns: repeat(2, 1fr) !important; }
        .checklist-grid { grid-template-columns: repeat(2, 1fr) !important; }

        /* 图表容器撑满宽度 */
        div[_echarts_instance_] { width: 100% !important; }

        /* 长文本 section 允许跨页 */
        .section-card { break-inside: auto !important; page-break-inside: auto !important; }
    }
    </style>
    """

def _build_sidebar():



    """返回报告左侧导航栏的HTML字符串，支持快速导航+模块选择+PDF导出"""
    return """
    <!-- 移动端 Hamburger 按钮 -->
    <button class="hamburger-btn no-print" id="hamburgerBtn" aria-label="Open menu">&#9776;</button>

    <!-- 遮罩层 -->
    <div class="sidebar-overlay" id="sidebarOverlay"></div>

    <!-- 左侧 Sidebar -->
    <nav class="sidebar no-print" id="reportSidebar">
        <div class="sidebar-header">
            <div class="report-title">
                <span class="title-icon">IC</span>
                <span>ICAS 课堂分析报告</span>
            </div>
            <div class="report-subtitle">Interactive Classroom Analysis System</div>
        </div>

        <div class="sidebar-body">
            <!-- 分组1: 教学概况 -->
            <div class="sidebar-group" data-group="overview">
                <div class="sidebar-group-header">
                    <span>教学概况</span>
                    <span class="toggle-arrow">&#9660;</span>
                </div>
                <div class="sidebar-group-items">
                    <div class="sidebar-item" data-nav="sec-overview">
                        <input type="checkbox" id="chk-sec-overview" data-section="sec-overview" checked>
                        <span class="nav-label">课堂总览</span>
                        <span class="nav-arrow" title="跳转">&#8594;</span>
                    </div>
                    <div class="sidebar-item" data-nav="sec-recommend">
                        <input type="checkbox" id="chk-sec-recommend" data-section="sec-recommend" checked>
                        <span class="nav-label">教学建议</span>
                        <span class="nav-arrow" title="跳转">&#8594;</span>
                    </div>
                </div>
            </div>

            <!-- 分组2: 结构与节奏 -->
            <div class="sidebar-group" data-group="structure">
                <div class="sidebar-group-header">
                    <span>结构与节奏</span>
                    <span class="toggle-arrow">&#9660;</span>
                </div>
                <div class="sidebar-group-items">
                    <div class="sidebar-item" data-nav="sec-time">
                        <input type="checkbox" id="chk-sec-time" data-section="sec-time" checked>
                        <span class="nav-label">时间分配</span>
                        <span class="nav-arrow" title="跳转">&#8594;</span>
                    </div>
                    <div class="sidebar-item" data-nav="sec-knowledge">
                        <input type="checkbox" id="chk-sec-knowledge" data-section="sec-knowledge" checked>
                        <span class="nav-label">知识点覆盖</span>
                        <span class="nav-arrow" title="跳转">&#8594;</span>
                    </div>
                    <div class="sidebar-item" data-nav="sec-checklist">
                        <input type="checkbox" id="chk-sec-checklist" data-section="sec-checklist" checked>
                        <span class="nav-label">教学清单</span>
                        <span class="nav-arrow" title="跳转">&#8594;</span>
                    </div>
                    <div class="sidebar-item" data-nav="sec-scaffold">
                        <input type="checkbox" id="chk-sec-scaffold" data-section="sec-scaffold" checked>
                        <span class="nav-label">支架分析</span>
                        <span class="nav-arrow" title="跳转">&#8594;</span>
                    </div>
                    <div class="sidebar-item" data-nav="sec-st">
                        <input type="checkbox" id="chk-sec-st" data-section="sec-st" checked>
                        <span class="nav-label">S-T 师生行为</span>
                        <span class="nav-arrow" title="跳转">&#8594;</span>
                    </div>
                    <div class="sidebar-item" data-nav="sec-speech">
                        <input type="checkbox" id="chk-sec-speech" data-section="sec-speech" checked>
                        <span class="nav-label">语速分析</span>
                        <span class="nav-arrow" title="跳转">&#8594;</span>
                    </div>
                    <div class="sidebar-item" data-nav="sec-wordcloud">
                        <input type="checkbox" id="chk-sec-wordcloud" data-section="sec-wordcloud" checked>
                        <span class="nav-label">高频词汇</span>
                        <span class="nav-arrow" title="跳转">&#8594;</span>
                    </div>
                </div>
            </div>

            <!-- 分组3: 教学策略 -->
            <div class="sidebar-group" data-group="strategy">
                <div class="sidebar-group-header">
                    <span>教学策略</span>
                    <span class="toggle-arrow">&#9660;</span>
                </div>
                <div class="sidebar-group-items">
                    <div class="sidebar-item" data-nav="sec-radar">
                        <input type="checkbox" id="chk-sec-radar" data-section="sec-radar" checked>
                        <span class="nav-label">能力雷达图</span>
                        <span class="nav-arrow" title="跳转">&#8594;</span>
                    </div>
                    <div class="sidebar-item" data-nav="sec-bloom">
                        <input type="checkbox" id="chk-sec-bloom" data-section="sec-bloom" checked>
                        <span class="nav-label">布鲁姆分层</span>
                        <span class="nav-arrow" title="跳转">&#8594;</span>
                    </div>
                    <div class="sidebar-item" data-nav="sec-hattie">
                        <input type="checkbox" id="chk-sec-hattie" data-section="sec-hattie" checked>
                        <span class="nav-label">Hattie 可见学习</span>
                        <span class="nav-arrow" title="跳转">&#8594;</span>
                    </div>
                    <div class="sidebar-item" data-nav="sec-chains">
                        <input type="checkbox" id="chk-sec-chains" data-section="sec-chains" checked>
                        <span class="nav-label">问题链分析</span>
                        <span class="nav-arrow" title="跳转">&#8594;</span>
                    </div>
                    <div class="sidebar-item" data-nav="sec-fourmat">
                        <input type="checkbox" id="chk-sec-fourmat" data-section="sec-fourmat" checked>
                        <span class="nav-label">4MAT 分类</span>
                        <span class="nav-arrow" title="跳转">&#8594;</span>
                    </div>
                    <div class="sidebar-item" data-nav="sec-interaction">
                        <input type="checkbox" id="chk-sec-interaction" data-section="sec-interaction" checked>
                        <span class="nav-label">互动分析</span>
                        <span class="nav-arrow" title="跳转">&#8594;</span>
                    </div>
                </div>
            </div>

            <!-- 分组4: 学生与诊断 -->
            <div class="sidebar-group" data-group="student">
                <div class="sidebar-group-header">
                    <span>学生与诊断</span>
                    <span class="toggle-arrow">&#9660;</span>
                </div>
                <div class="sidebar-group-items">
                    <div class="sidebar-item" data-nav="sec-thinking">
                        <input type="checkbox" id="chk-sec-thinking" data-section="sec-thinking" checked>
                        <span class="nav-label">思维五维分析</span>
                        <span class="nav-arrow" title="跳转">&#8594;</span>
                    </div>
                    <div class="sidebar-item" data-nav="sec-response">
                        <input type="checkbox" id="chk-sec-response" data-section="sec-response" checked>
                        <span class="nav-label">学生应答</span>
                        <span class="nav-arrow" title="跳转">&#8594;</span>
                    </div>
                    <div class="sidebar-item" data-nav="sec-feedback-detail">
                        <input type="checkbox" id="chk-sec-feedback-detail" data-section="sec-feedback-detail" checked>
                        <span class="nav-label">教师反馈</span>
                        <span class="nav-arrow" title="跳转">&#8594;</span>
                    </div>
                    <div class="sidebar-item" data-nav="sec-cognition">
                        <input type="checkbox" id="chk-sec-cognition" data-section="sec-cognition" checked>
                        <span class="nav-label">认知诊断</span>
                        <span class="nav-arrow" title="跳转">&#8594;</span>
                    </div>
                </div>
            </div>
        </div>

        <!-- 底部操作区 -->
        <div class="sidebar-footer">
            <div class="btn-row">
                <button type="button" id="btnSelectAll">全选</button>
                <button type="button" id="btnDeselectAll">取消全选</button>
            </div>
            <button type="button" class="btn-export-pdf" id="btnExportPdf">导出 PDF</button>
        </div>
    </nav>

    <!-- Sidebar 交互脚本 -->
    <script>
    (function() {
        var sidebar = document.getElementById('reportSidebar');
        var hamburger = document.getElementById('hamburgerBtn');
        var overlay = document.getElementById('sidebarOverlay');

        // Hamburger 切换
        function toggleSidebar() {
            sidebar.classList.toggle('open');
            overlay.classList.toggle('open');
        }

        if (hamburger) {
            hamburger.addEventListener('click', toggleSidebar);
        }
        if (overlay) {
            overlay.addEventListener('click', toggleSidebar);
        }

        // 分组折叠/展开
        var groupHeaders = document.querySelectorAll('.sidebar-group-header');
        groupHeaders.forEach(function(header) {
            header.addEventListener('click', function() {
                this.closest('.sidebar-group').classList.toggle('collapsed');
            });
        });

        // ====== 核心: 点击整行导航到对应 section ======
        var sidebarItems = document.querySelectorAll('.sidebar-item');
        sidebarItems.forEach(function(item) {
            var sectionId = item.getAttribute('data-nav');
            if (!sectionId) return;

            var checkbox = item.querySelector('input[type="checkbox"]');
            var labelText = item.querySelector('.nav-label');

            // 点击 label 文字或箭头 -> 导航
            function doNavigate(e) {
                e.stopPropagation();
                e.preventDefault();
                var target = document.getElementById(sectionId);
                if (target) {
                    target.scrollIntoView({ behavior: 'smooth', block: 'start' });
                    target.classList.add('section-highlight');
                    setTimeout(function() { target.classList.remove('section-highlight'); }, 1500);
                }
                if (window.innerWidth < 768) {
                    sidebar.classList.remove('open');
                    overlay.classList.remove('open');
                }
            }

            // 点击箭头 -> 导航
            var arrow = item.querySelector('.nav-arrow');
            if (arrow) arrow.addEventListener('click', doNavigate);

            // 点击 label -> 导航(不切换checkbox)
            if (labelText) labelText.addEventListener('click', doNavigate);

            // 点击整行空白区域 -> 也导航
            item.addEventListener('click', function(e) {
                // 只有点击空白区域时才导航，点击checkbox/label/arrow走各自的handler
                if (e.target === item) {
                    doNavigate(e);
                }
            });

            // checkbox 点击仅切换勾选，不导航
            if (checkbox) {
                checkbox.addEventListener('click', function(e) {
                    e.stopPropagation();
                });
            }
        });

        // ====== 滚动高亮: 自动标记当前可见的 sidebar 项 ======
        var allSections = [];
        sidebarItems.forEach(function(item) {
            var sid = item.getAttribute('data-nav');
            var el = document.getElementById(sid);
            if (el) allSections.push({ id: sid, el: el, item: item });
        });

        function updateActiveNav() {
            var scrollY = window.scrollY || document.documentElement.scrollTop;
            var offset = 120;
            var active = null;
            for (var i = allSections.length - 1; i >= 0; i--) {
                if (allSections[i].el.offsetTop - offset <= scrollY) {
                    active = allSections[i];
                    break;
                }
            }
            sidebarItems.forEach(function(it) { it.classList.remove('active'); });
            if (active) active.item.classList.add('active');
        }

        var scrollTimer = null;
        window.addEventListener('scroll', function() {
            if (scrollTimer) clearTimeout(scrollTimer);
            scrollTimer = setTimeout(updateActiveNav, 80);
        });
        updateActiveNav();

        // 全选
        var btnSelectAll = document.getElementById('btnSelectAll');
        if (btnSelectAll) {
            btnSelectAll.addEventListener('click', function() {
                var checkboxes = document.querySelectorAll('.sidebar-item input[type="checkbox"]');
                checkboxes.forEach(function(cb) { cb.checked = true; });
            });
        }

        // 取消全选
        var btnDeselectAll = document.getElementById('btnDeselectAll');
        if (btnDeselectAll) {
            btnDeselectAll.addEventListener('click', function() {
                var checkboxes = document.querySelectorAll('.sidebar-item input[type="checkbox"]');
                checkboxes.forEach(function(cb) { cb.checked = false; });
            });
        }

        // 导出 PDF（高清模式：先触发 ECharts resize 再打印）
        var btnExportPdf = document.getElementById('btnExportPdf');
        if (btnExportPdf) {
            btnExportPdf.addEventListener('click', function() {
                var checkboxes = document.querySelectorAll('.sidebar-item input[type="checkbox"]');
                checkboxes.forEach(function(cb) {
                    var sectionId = cb.getAttribute('data-section');
                    var sectionEl = document.getElementById(sectionId);
                    if (sectionEl) {
                        if (cb.checked) {
                            sectionEl.classList.remove('no-print-section');
                        } else {
                            sectionEl.classList.add('no-print-section');
                        }
                    }
                });

                // 触发 ECharts resize 让图表适配打印布局
                window.dispatchEvent(new Event('resize'));

                // 等待 ECharts 重绘完成后再打印
                setTimeout(function() {
                    window.print();
                }, 1500);
            });
        }
    })();
    </script>
    """



def _build_header_html(full_data, folder_name, extended_data=None):

    """
    报告头部区域：
    - 标题 / 副标题 / 日期
    - 教学风格 tag
    - 关键词 pills
    - 4 个核心指标速览卡片
    """
    # --- 基础信息 ---
    today = time.strftime("%Y-%m-%d")
    persona = _safe_get(full_data, "deep", "persona") or {}
    tag = persona.get("tag", "未识别")
    keywords = persona.get("keywords", [])

    # --- 标题区 ---
    html = f"""
    <!-- ===== HEADER ===== -->
    <header class="report-header printable">
      <div class="header-top">
        <div class="header-brand">
          <h1 class="report-title">课堂教学深度诊断书</h1>
          <span class="header-subtitle">ICAS ULTIMATE EDITION III</span>
        </div>
        <div class="header-meta">
          <span class="header-date"><i class="fa-regular fa-calendar"></i> {today}</span>
          <span class="header-folder"><i class="fa-regular fa-folder"></i> {folder_name}</span>
        </div>
      </div>

      <div class="header-tags">
        <span class="style-tag">
          <i class="fa-solid fa-chalkboard-user"></i> {tag}
        </span>
        <div class="keyword-pills">
    """

    for kw in keywords:
        html += f'          <span class="keyword-pill">{kw}</span>\n'

    html += """        </div>
      </div>
    """

    # --- 核心指标速览卡片 ---
    if extended_data:
        total_q = _safe_get(extended_data, "qa_analysis", "total_questions", default="-")
        wpm = _safe_get(extended_data, "st_analysis", "speech_rate", "words_per_minute", default="-")
        rt = _safe_get(extended_data, "st_analysis", "rt", default="-")
        classroom_type = _safe_get(extended_data, "st_analysis", "classroom_type", default="-")

        # 格式化显示
        total_q_str = str(total_q) if total_q != "-" else "-"
        wpm_str = f"{wpm:.0f}" if isinstance(wpm, (int, float)) else "-"
        rt_str = f"{rt:.1%}" if isinstance(rt, (int, float)) else str(rt) if rt != "-" else "-"
        classroom_type_str = str(classroom_type) if classroom_type != "-" else "-"

        html += f"""
      <div class="kpi-row">
        <div class="kpi-card kpi-blue">
          <div class="kpi-icon"><i class="fa-solid fa-comments"></i></div>
          <div class="kpi-body">
            <span class="kpi-value">{total_q_str}</span>
            <span class="kpi-label">总提问数</span>
          </div>
        </div>
        <div class="kpi-card kpi-green">
          <div class="kpi-icon"><i class="fa-solid fa-gauge-high"></i></div>
          <div class="kpi-body">
            <span class="kpi-value">{wpm_str}</span>
            <span class="kpi-label">教师语速(字/分)</span>
          </div>
        </div>
        <div class="kpi-card kpi-purple">
          <div class="kpi-icon"><i class="fa-solid fa-users"></i></div>
          <div class="kpi-body">
            <span class="kpi-value">{rt_str}</span>
            <span class="kpi-label">Rt 师生比</span>
          </div>
        </div>
        <div class="kpi-card kpi-orange">
          <div class="kpi-icon"><i class="fa-solid fa-shapes"></i></div>
          <div class="kpi-body">
            <span class="kpi-value">{classroom_type_str}</span>
            <span class="kpi-label">课堂类型</span>
          </div>
        </div>
      </div>
    """

    html += """    </header>
    """

    return html


# ──────────────────────────────────────────────
# Group A：教学概况
# ──────────────────────────────────────────────


def _build_group_a_html(full_data, teaching_design):

    """
    Group A — 教学概况（2 个 section）
      - sec-overview:  宏观教学综述
      - sec-recommend: 导师改进建议
    """

    html = """
    <!-- ===== GROUP A: 教学概况 ===== -->
    <div class="group-label group-label--a">A &middot; 教学概况</div>
    """

    # ── sec-overview ────────────────────────────
    macro_review = _safe_get(full_data, "report", "macro_review", default="")
    macro_html = _md(macro_review)

    # 教学设计概览
    design_html = ""
    if teaching_design:
        td_text = str(teaching_design)
        excerpt = td_text[:200] + ("..." if len(td_text) > 200 else "")
        design_html = f"""
        <div class="design-excerpt">
          <h4><i class="fa-solid fa-file-lines"></i> 教学设计概览</h4>
          <div class="design-text">{excerpt}</div>
        </div>
        """

    html += f"""
    <section id="sec-overview" class="section-card printable" style="border-left: 4px solid #6366f1;">
      <h3 class="section-title"><i class="fa-solid fa-binoculars" style="background:#6366f1;"></i> 宏观教学综述</h3>
      <div class="section-body prose-content">
        {macro_html}
      </div>
      {design_html}
    </section>
    """

    # ── sec-recommend ──────────────────────────
    recommendations = _safe_get(full_data, "report", "recommendations", default=[])
    recs_html = ""
    if recommendations and isinstance(recommendations, list):
        for idx, rec in enumerate(recommendations, 1):
            title = rec.get("title", f"建议 {idx}") if isinstance(rec, dict) else str(rec)
            content = rec.get("content", "") if isinstance(rec, dict) else str(rec)
            content_html = _md(content)
            recs_html += f"""
        <div class="recommend-card" style="border-left: 4px solid #6366f1;">
          <div class="recommend-header">
            <span class="recommend-num">{idx}</span>
            <span class="recommend-title">{title}</span>
          </div>
          <div class="recommend-body prose-content">{content_html}</div>
        </div>
        """

    html += f"""
    <section id="sec-recommend" class="section-card printable" style="border-left: 4px solid #6366f1;">
      <h3 class="section-title"><i class="fa-solid fa-lightbulb" style="background:#f59e0b;"></i> 导师改进建议</h3>
      <div class="section-body">
        {recs_html if recs_html else '<p class="text-muted">暂无改进建议</p>'}
      </div>
    </section>
    """

    return html


# ──────────────────────────────────────────────
# Group B：结构与节奏
# ──────────────────────────────────────────────


def _build_group_b_html(full_data, extended_data):

    """
    Group B — 结构与节奏（7 个 section）
      - sec-time      : 时间分配（饼图）
      - sec-knowledge  : 知识图谱（力导向图）
      - sec-checklist  : 教学常规核查
      - sec-scaffold   : 知识脚手架分析
      - sec-st         : S-T 师生行为分析（扩展数据）
      - sec-speech     : 语速分析（扩展数据）
      - sec-wordcloud  : 高频词汇（扩展数据）
    """

    # Group B 统一边框色
    BORDER_B = "#0ea5e9"  # sky-500

    html = """
    <!-- ===== GROUP B: 结构与节奏 ===== -->
    <div class="group-label group-label--b">B &middot; 结构与节奏</div>
    """

    # ── sec-time ────────────────────────────────
    stats = _safe_get(full_data, "structure", "overall_stats") or {}
    lecture_min = stats.get("total_lecture_minutes", 0) or 0
    interact_min = stats.get("total_interaction_minutes", 0) or 0
    practice_min = stats.get("total_practice_minutes", 0) or 0
    other_min = stats.get("total_other_minutes", 0) or 0

    html += f"""
    <section id="sec-time" class="section-card printable" style="border-left: 4px solid {BORDER_B};">
      <h3 class="section-title"><i class="fa-solid fa-clock" style="background:#0284c7;"></i> 时间分配</h3>
      <div class="section-body">
        <div class="chart-with-side">
          <div class="chart-main">
            <div id="time-chart" style="width:100%; height:200px;"></div>
          </div>
          <div class="chart-side time-stats">
            <div class="time-stat-item">
              <span class="dot" style="background:#5b8ff9;"></span>
              <span class="label">讲授</span>
              <span class="value">{_fmt_minutes(lecture_min)}</span>
            </div>
            <div class="time-stat-item">
              <span class="dot" style="background:#5ad8a6;"></span>
              <span class="label">互动</span>
              <span class="value">{_fmt_minutes(interact_min)}</span>
            </div>
            <div class="time-stat-item">
              <span class="dot" style="background:#f6bd16;"></span>
              <span class="label">练习</span>
              <span class="value">{_fmt_minutes(practice_min)}</span>
            </div>
            <div class="time-stat-item">
              <span class="dot" style="background:#e86452;"></span>
              <span class="label">其他</span>
              <span class="value">{_fmt_minutes(other_min)}</span>
            </div>
          </div>
        </div>
      </div>
    </section>
    """

    # ── sec-knowledge ──────────────────────────
    kg = _safe_get(full_data, "content", "knowledge_graph") or {}
    kg_root = kg.get("root", "")
    kg_nodes = kg.get("nodes", [])
    kg_logic = kg.get("logic", "")

    # 力导向图只放容器，JS另行注入
    html += f"""
    <section id="sec-knowledge" class="section-card printable" style="border-left: 4px solid {BORDER_B};">
      <h3 class="section-title"><i class="fa-solid fa-diagram-project" style="background:#0284c7;"></i> 知识图谱</h3>
      <div class="section-body">
        <div class="chart-container">
          <div id="kg-chart" style="width:100%; height:220px;"></div>
        </div>
        {"<div class='kg-logic prose-content'>" + _md(kg_logic) + '</div>' if kg_logic else ''}
      </div>
    </section>
    """

    # ── sec-checklist ──────────────────────────
    checklist = _safe_get(full_data, "content", "checklist") or {}
    review_done = bool(checklist.get("review", False))
    summary_done = bool(checklist.get("summary", False))
    homework_done = bool(checklist.get("homework", False))
    homework_detail = checklist.get("homework_detail", "")

    def _check_icon(done):
        if done:
            return '<i class="fa-solid fa-circle-check" style="color:#10b981;"></i> <span class="check-done">已完成</span>'
        return '<i class="fa-regular fa-circle" style="color:#9ca3af;"></i> <span class="check-not">未涉及</span>'

    html += f"""
    <section id="sec-checklist" class="section-card printable" style="border-left: 4px solid {BORDER_B};">
      <h3 class="section-title"><i class="fa-solid fa-list-check" style="background:#0284c7;"></i> 教学常规核查</h3>
      <div class="section-body">
        <div class="checklist-grid">
          <div class="checklist-item">
            <span class="check-label">复习环节</span>
            <span class="check-status">{_check_icon(review_done)}</span>
          </div>
          <div class="checklist-item">
            <span class="check-label">总结环节</span>
            <span class="check-status">{_check_icon(summary_done)}</span>
          </div>
          <div class="checklist-item">
            <span class="check-label">作业布置</span>
            <span class="check-status">{_check_icon(homework_done)}</span>
          </div>
        </div>
        {"<div class='homework-detail prose-content'>" + _md(homework_detail) + '</div>' if homework_detail else ''}
      </div>
    </section>
    """

    # ── sec-scaffold ───────────────────────────
    logic_analysis = _safe_get(full_data, "report", "logic_analysis", default="")
    logic_html = _md(logic_analysis)

    html += f"""
    <section id="sec-scaffold" class="section-card printable" style="border-left: 4px solid {BORDER_B};">
      <h3 class="section-title"><i class="fa-solid fa-layer-group" style="background:#0284c7;"></i> 知识脚手架分析</h3>
      <div class="section-body prose-content">
        {logic_html if logic_html else '<p class="text-muted">暂无分析数据</p>'}
      </div>
    </section>
    """

    # ── sec-st ─────────────────────────────────
    st_data = _safe_get(extended_data, "st_analysis") if extended_data else None

    if st_data:
        rt_val = st_data.get("rt", "-")
        ch_val = st_data.get("ch", "-")
        ctype = st_data.get("classroom_type", "-")
        ctype_desc = st_data.get("type_description", "")
        st_suggestions = st_data.get("suggestions", [])
        teacher_min = st_data.get("teacher_minutes", 0)
        student_min = st_data.get("student_minutes", 0)
        per_phase = st_data.get("per_phase", [])

        rt_str = f"{rt_val:.1%}" if isinstance(rt_val, (int, float)) else str(rt_val)
        ch_str = f"{ch_val:.1%}" if isinstance(ch_val, (int, float)) else str(ch_val)

        # 建议列表
        sg_html = ""
        if st_suggestions and isinstance(st_suggestions, list):
            for s in st_suggestions:
                sg_html += f"<li>{s}</li>"
            sg_html = f'<ul class="st-suggestions">{sg_html}</ul>'

        html += f"""
        <section id="sec-st" class="section-card printable" style="border-left: 4px solid {BORDER_B};">
          <h3 class="section-title"><i class="fa-solid fa-chart-pie" style="background:#0284c7;"></i> S-T 师生行为分析</h3>
          <div class="section-body">
            <div class="st-summary">
              <div class="st-badge"><span class="st-label">Rt</span><span class="st-value">{rt_str}</span></div>
              <div class="st-badge"><span class="st-label">Ch</span><span class="st-value">{ch_str}</span></div>
              <div class="st-badge st-badge--type"><span class="st-label">课堂类型</span><span class="st-value">{ctype}</span></div>
            </div>
            {"<p class='st-type-desc'>" + ctype_desc + '</p>' if ctype_desc else ''}
            <div class="chart-row">
              <div class="chart-half">
                <div id="ext-st-pie-chart" style="width:100%; height:220px;"></div>
              </div>
              <div class="chart-half">
                <div id="ext-st-bar-chart" style="width:100%; height:220px;"></div>
              </div>
            </div>
            {sg_html}
          </div>
        </section>
        """
    else:
        html += f"""
        <section id="sec-st" class="section-card printable" style="border-left: 4px solid {BORDER_B};">
          <h3 class="section-title"><i class="fa-solid fa-chart-pie" style="background:#0284c7;"></i> S-T 师生行为分析</h3>
          <div class="section-body">
            <p class="text-muted">暂无 S-T 分析数据</p>
          </div>
        </section>
        """

    # ── sec-speech ─────────────────────────────
    speech_data = _safe_get(extended_data, "st_analysis", "speech_rate") if extended_data else None

    if speech_data:
        wpm = speech_data.get("words_per_minute", "-")
        total_words = speech_data.get("total_words", "-")
        duration_min = speech_data.get("duration_minutes", "-")
        evaluation = speech_data.get("evaluation", "")

        wpm_str = f"{wpm:.0f}" if isinstance(wpm, (int, float)) else str(wpm)
        total_words_str = f"{total_words:,}" if isinstance(total_words, (int, float)) else str(total_words)
        dur_str = _fmt_minutes(duration_min) if isinstance(duration_min, (int, float)) else str(duration_min)

        html += f"""
        <section id="sec-speech" class="section-card printable" style="border-left: 4px solid {BORDER_B};">
          <h3 class="section-title"><i class="fa-solid fa-microphone" style="background:#0284c7;"></i> 语速分析</h3>
          <div class="section-body">
            <div class="kpi-row kpi-row--compact">
              <div class="kpi-card kpi-blue">
                <span class="kpi-value">{wpm_str}</span>
                <span class="kpi-label">字/分钟</span>
              </div>
              <div class="kpi-card kpi-green">
                <span class="kpi-value">{total_words_str}</span>
                <span class="kpi-label">总字数</span>
              </div>
              <div class="kpi-card kpi-purple">
                <span class="kpi-value">{dur_str}</span>
                <span class="kpi-label">说话时长</span>
              </div>
            </div>
            {"<div class='speech-eval prose-content'>" + _md(evaluation) + '</div>' if evaluation else ''}
          </div>
        </section>
        """
    else:
        html += f"""
        <section id="sec-speech" class="section-card printable" style="border-left: 4px solid {BORDER_B};">
          <h3 class="section-title"><i class="fa-solid fa-microphone" style="background:#0284c7;"></i> 语速分析</h3>
          <div class="section-body">
            <p class="text-muted">暂无语速分析数据</p>
          </div>
        </section>
        """

    # ── sec-wordcloud ──────────────────────────
    word_freq = _safe_get(extended_data, "word_freq") if extended_data else None

    if word_freq and isinstance(word_freq, list) and len(word_freq) > 0:
        html += f"""
        <section id="sec-wordcloud" class="section-card printable" style="border-left: 4px solid {BORDER_B};">
          <h3 class="section-title"><i class="fa-solid fa-cloud" style="background:#0284c7;" style="background:#0284c7;"></i> 高频词汇</h3>
          <div class="section-body">
            <div class="chart-container">
              <div id="ext-wordcloud-chart" style="width:100%; height:260px;"></div>
            </div>
          </div>
        </section>
        """
    else:
        html += f"""
        <section id="sec-wordcloud" class="section-card printable" style="border-left: 4px solid {BORDER_B};">
          <h3 class="section-title"><i class="fa-solid fa-cloud" style="background:#0284c7;" style="background:#0284c7;"></i> 高频词汇</h3>
          <div class="section-body">
            <p class="text-muted">暂无高频词汇数据</p>
          </div>
        </section>
        """

    return html


# ──────────────────────────────────────────────
# Group C：教学策略
# ──────────────────────────────────────────────
def _build_group_c_html(full_data, extended_data):
    html = '''
    <!-- ===== GROUP C: 教学策略 ===== -->
    <div class="group-label group-label--c">C &middot; 教学策略</div>
    '''
    BORDER_C = "#8b5cf6"
    
    # sec-radar
    html += f'''
    <section id="sec-radar" class="section-card printable" style="border-left: 4px solid #6366f1;">
      <h3 class="section-title"><i class="fa-solid fa-satellite-dish" style="background:#7c3aed;"></i> 五维能力雷达</h3>
      <div class="section-body">
        <div class="chart-container">
          <div id="radar-chart" style="width:100%; height:250px;"></div>
        </div>
      </div>
    </section>
    '''
    
    # sec-bloom
    html += f'''
    <section id="sec-bloom" class="section-card printable" style="border-left: 4px solid #8b5cf6;">
      <h3 class="section-title"><i class="fa-solid fa-layer-group" style="background:#8b5cf6;"></i> 认知激发深度 (Bloom)</h3>
      <div class="section-body">
        <div class="chart-container">
          <div id="bloom-chart" style="width:100%; height:250px;"></div>
        </div>
      </div>
    </section>
    '''
    
    # sec-hattie
    html += f'''
    <section id="sec-hattie" class="section-card printable" style="border-left: 4px solid #ec4899;">
      <h3 class="section-title"><i class="fa-solid fa-chart-pie" style="background:#e11d48;"></i> 反馈质量分布 (Hattie)</h3>
      <div class="section-body">
        <div class="chart-container">
          <div id="hattie-chart" style="width:100%; height:250px;"></div>
        </div>
      </div>
    </section>
    '''
    
    # sec-chains
    chains = _safe_get(extended_data, "qa_analysis", "question_chains", default=[]) if extended_data else []
    tc = {"逻辑思维": "#6366f1", "形象思维": "#ec4899", "元认知思维": "#10b981", "系统思维": "#f59e0b", "辩证思维": "#8b5cf6"}
    chain_cards = ""
    for c in chains:
        color = tc.get(c.get('thinking_type', ''), '#6366f1')
        q_li = "".join([f'<li>{q}</li>' for q in c.get('questions', [])])
        chain_cards += f'''
            <div class="chain-card">
                <div class="chain-header">
                    <span class="chain-tag" style="background:{color}">{c.get('thinking_type','')}</span>
                    <span class="chain-topic">{c.get('topic','')}</span>
                </div>
                <div class="chain-meta">
                    <span class="chain-badge">{c.get('question_type','')}</span>
                    <span class="chain-badge chain-badge--gray">{c.get('complexity','')}</span>
                </div>
                <ul class="chain-questions">{q_li}</ul>
            </div>'''
            
    chain_analysis = _safe_get(extended_data, "qa_analysis", "chain_analysis", default="") if extended_data else ""
    chain_suggestions = _safe_get(extended_data, "qa_analysis", "chain_suggestions", default="") if extended_data else ""
    
    html += f'''
    <section id="sec-chains" class="section-card printable" style="border-left: 4px solid #8b5cf6;">
      <h3 class="section-title"><i class="fa-solid fa-link" style="background:#8b5cf6;"></i> 问题链分析</h3>
      <div class="section-body">
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
            {chain_cards if chain_cards else '<p class="text-muted">暂无问题链数据</p>'}
        </div>
        {"<div class='insight-box insight-analysis'><span class='insight-label'>分析</span>" + chain_analysis + "</div>" if chain_analysis else ""}
        {"<div class='insight-box insight-suggestion'><span class='insight-label'>建议</span>" + chain_suggestions + "</div>" if chain_suggestions else ""}
      </div>
    </section>
    '''
    
    # sec-fourmat
    html += f'''
    <section id="sec-fourmat" class="section-card printable" style="border-left: 4px solid #6366f1;">
      <h3 class="section-title"><i class="fa-solid fa-shapes" style="background:#6366f1;"></i> 问题分类统计</h3>
      <div class="section-body">
        <div class="chart-row">
            <div class="chart-container">
                <div id="ext-fourmat-chart" style="width:100%; height:220px;"></div>
            </div>
            <div class="chart-container">
                <div id="ext-openness-chart" style="width:100%; height:220px;"></div>
            </div>
        </div>
      </div>
    </section>
    '''
    
    # sec-interaction
    micro = _safe_get(full_data, "content", "micro_moments", default=[])
    micro_html = ""
    for m in micro:
        micro_html += f'''
        <div class="micro-card no-break">
            <h4 class="micro-title">{m.get('title','')}</h4>
            <div class="micro-dialogue">{m.get('dialogue','')}</div>
            <div class="micro-analysis">
                <span class="micro-analysis-label">导师点评</span>
                <p>{m.get('analysis','')}</p>
            </div>
        </div>
        '''
        
    html += f'''
    <section id="sec-interaction" class="section-card printable" style="border-left: 4px solid #4f46e5;">
      <h3 class="section-title"><i class="fa-solid fa-comments" style="background:#4f46e5;"></i> 关键互动切片 (Micro-Teaching)</h3>
      <div class="section-body">
        {micro_html if micro_html else '<p class="text-muted">暂无互动分析数据</p>'}
      </div>
    </section>
    '''
    
    return html

# ──────────────────────────────────────────────
# Group D：学生与诊断
# ──────────────────────────────────────────────
def _build_group_d_html(full_data, extended_data):
    html = '''
    <!-- ===== GROUP D: 学生与诊断 ===== -->
    <div class="group-label group-label--d">D &middot; 学生与诊断</div>
    '''
    
    # sec-thinking
    thinking = _safe_get(extended_data, "student_analysis", "student_thinking", default=[]) if extended_data else []
    lc = {"全面体现": "#059669", "初步体现": "#d97706", "尚未体现": "#dc2626"}
    lb = {"全面体现": "#ecfdf5", "初步体现": "#fffbeb", "尚未体现": "#fef2f2"}
    thinking_cards = ""
    for t in thinking:
        level = t.get('level', '尚未体现')
        thinking_cards += f'''
            <div class="thinking-card" style="background:{lb.get(level,'#f9fafb')}; border-color:{lc.get(level,'#9ca3af')}">
                <div class="thinking-header">
                    <span class="thinking-type">{t.get('type','')}</span>
                    <span class="thinking-level" style="background:{lc.get(level,'#9ca3af')}">{level}</span>
                </div>
                <p class="thinking-analysis">{t.get('analysis','')}</p>
                <p class="thinking-suggestion">{t.get('suggestion','')}</p>
            </div>'''
            
    html += f'''
    <section id="sec-thinking" class="section-card printable" style="border-left: 4px solid #10b981;">
      <h3 class="section-title"><i class="fa-solid fa-brain" style="background:#10b981;"></i> 学生思维五维分析</h3>
      <div class="section-body">
        <div class="thinking-grid">
            {thinking_cards if thinking_cards else '<p class="text-muted">暂无学生思维数据</p>'}
        </div>
      </div>
    </section>
    '''
    
    # sec-response
    resp = _safe_get(extended_data, "student_analysis", "student_response", default={}) if extended_data else {}
    resp_total = resp.get('total', 0)
    resp_active = resp.get('active_pct', 0)
    resp_passive = resp.get('passive_pct', 0)
    resp_analysis = resp.get('analysis', '')
    resp_suggestions = resp.get('suggestions', '')
    
    html += f'''
    <section id="sec-response" class="section-card printable" style="border-left: 4px solid #f59e0b;">
      <h3 class="section-title"><i class="fa-solid fa-hand-sparkles" style="background:#f59e0b;"></i> 学生应答分析</h3>
      <div class="section-body">
        <div class="chart-row">
            <div class="chart-container">
                <div id="ext-response-chart" style="width:100%; height:220px;"></div>
            </div>
            <div class="response-stats">
                <div class="resp-stat"><span class="resp-stat-label">总体应答</span><span class="resp-stat-value">{resp_total} <small>次</small></span></div>
                <div class="resp-stat"><span class="resp-stat-label">主动应答</span><span class="resp-stat-value">{resp_active}%</span></div>
                <div class="resp-stat"><span class="resp-stat-label">被动应答</span><span class="resp-stat-value">{resp_passive}%</span></div>
                {"<div class='insight-box insight-analysis'><span class='insight-label'>分析</span>" + resp_analysis + "</div>" if resp_analysis else ""}
                {"<div class='insight-box insight-suggestion'><span class='insight-label'>建议</span>" + resp_suggestions + "</div>" if resp_suggestions else ""}
            </div>
        </div>
      </div>
    </section>
    '''
    
    # sec-feedback-detail
    phrases = _safe_get(extended_data, "student_analysis", "common_phrases", default=[]) if extended_data else []
    phrase_html = ""
    for p_item in phrases:
        phrase_html += f'''
            <div class="phrase-card">
                <p class="phrase-text">"{p_item.get('phrase','')}"</p>
                <span class="phrase-meta">[{p_item.get('type','')}] {p_item.get('context','')}</span>
            </div>'''

    fb = _safe_get(extended_data, "student_analysis", "teacher_feedback", default={}) if extended_data else {}
    fb_analysis = fb.get('analysis', '')
    fb_suggestions = fb.get('suggestions', '')

    html += f'''
    <section id="sec-feedback-detail" class="section-card printable" style="border-left: 4px solid #ec4899;">
      <h3 class="section-title"><i class="fa-solid fa-comment-dots" style="background:#ec4899;"></i> 教师反馈分析</h3>
      <div class="section-body">
        <div class="chart-row">
            <div class="chart-container">
                <div id="ext-feedback-chart" style="width:100%; height:220px;"></div>
            </div>
            <div class="response-stats">
                {"<div class='insight-box insight-analysis'><span class='insight-label'>分析</span>" + fb_analysis + "</div>" if fb_analysis else ""}
                {"<div class='insight-box insight-suggestion'><span class='insight-label'>建议</span>" + fb_suggestions + "</div>" if fb_suggestions else ""}
            </div>
        </div>
        <div class="phrase-section">
            <h4 class="phrase-heading"><i class="fa-solid fa-quote-left"></i> 常用反馈语分析</h4>
            {phrase_html if phrase_html else '<p class="text-muted">暂无常用反馈语</p>'}
        </div>
      </div>
    </section>
    '''
    
    # sec-cognition
    cognition = _safe_get(full_data, "report", "student_cognition", default="")
    html += f'''
    <section id="sec-cognition" class="section-card printable" style="border-left: 4px solid #10b981;">
      <h3 class="section-title"><i class="fa-solid fa-magnifying-glass-chart" style="background:#10b981;"></i> 学生认知诊断</h3>
      <div class="section-body text-sm leading-relaxed text-gray-700 prose-content">
        {_md(cognition) if cognition else '<p class="text-muted">暂无认知诊断数据</p>'}
      </div>
    </section>
    '''
    
    return html

def _build_charts_js(full_data, extended_data):
    # Prepare Data
    structure = _safe_get(full_data, "structure") or {}
    deep = _safe_get(full_data, "deep") or {}
    content = _safe_get(full_data, "content") or {}
    
    ext_st = _safe_get(extended_data, "st_analysis") or {}
    ext_qa = _safe_get(extended_data, "qa_analysis") or {}
    ext_student = _safe_get(extended_data, "student_analysis") or {}
    ext_word = _safe_get(extended_data, "word_freq") or []
    
    # 1. time-chart
    time_stats = structure.get('overall_stats', {})
    time_chart_data = [
        {'value': time_stats.get('total_lecture_minutes', 0), 'name': '教师讲授', 'itemStyle': {'color': '#6366f1'}},
        {'value': time_stats.get('total_interaction_minutes', 0), 'name': '师生互动', 'itemStyle': {'color': '#ec4899'}},
        {'value': time_stats.get('total_practice_minutes', 0), 'name': '学生练习', 'itemStyle': {'color': '#10b981'}},
        {'value': time_stats.get('total_other_minutes', 0), 'name': '其他环节', 'itemStyle': {'color': '#9ca3af'}}
    ]
    
    # 2. kg-chart
    kg = content.get('knowledge_graph', {})
    kg_root = kg.get('root', '')
    kg_nodes = kg.get('nodes', [])
    kg_data = []
    kg_links = []
    if kg_root:
        kg_data.append({'name': kg_root, 'symbolSize': 60, 'itemStyle': {'color': '#4f46e5'}})
        for node in kg_nodes:
            kg_data.append({'name': node, 'symbolSize': 40, 'itemStyle': {'color': '#3b82f6'}})
            kg_links.append({'source': kg_root, 'target': node})
            
    # 3. radar-chart
    radar_scores = deep.get('radar_scores', [])
    
    # 4. bloom-chart
    bloom_stats = deep.get('bloom_stats', [])
    bloom_levels = [i.get('level', '') for i in bloom_stats]
    bloom_counts = [i.get('count', 0) for i in bloom_stats]
    
    # 5. hattie-chart
    hattie = deep.get('hattie_stats', {})
    hattie_chart_data = [
        {'value': hattie.get('task_level', 0), 'name': '任务层级'},
        {'value': hattie.get('process_level', 0), 'name': '过程层级'},
        {'value': hattie.get('self_level', 0), 'name': '自我层级'}
    ]
    
    # 6. ext-wordcloud-chart
    word_freq_data = []
    for item in ext_word:
        word_freq_data.append({'name': item.get('name',''), 'value': item.get('value',0)})
        
    # 7. ext-st-pie-chart
    teacher_min = ext_st.get('teacher_minutes', 0)
    student_min = ext_st.get('student_minutes', 0)
    st_pie_data = [
        {'value': teacher_min, 'name': '教师行为', 'itemStyle': {'color': '#6366f1'}},
        {'value': student_min, 'name': '学生行为', 'itemStyle': {'color': '#ec4899'}}
    ]
    
    # 8. ext-st-bar-chart
    st_phases = ext_st.get('per_phase', [])
    phase_names = [p.get('phase', '') for p in st_phases]
    t_pct = [p.get('teacher_pct', 0) for p in st_phases]
    s_pct = [p.get('student_pct', 0) for p in st_phases]
    
    # 9. ext-fourmat-chart
    fourmat = ext_qa.get('fourmat', {})
    fourmat_data = [
        {'value': fourmat.get('what', 0), 'name': '是何(What)', 'itemStyle': {'color': '#6366f1'}},
        {'value': fourmat.get('how', 0), 'name': '如何(How)', 'itemStyle': {'color': '#10b981'}},
        {'value': fourmat.get('what_if', 0), 'name': '若何(What-if)', 'itemStyle': {'color': '#f59e0b'}},
        {'value': fourmat.get('why', 0), 'name': '为何(Why)', 'itemStyle': {'color': '#ec4899'}}
    ]
    
    # 10. ext-openness-chart
    openness = ext_qa.get('openness', {})
    openness_data = [
        {'value': openness.get('open', 0), 'name': '开放性', 'itemStyle': {'color': '#10b981'}},
        {'value': openness.get('closed', 0), 'name': '封闭性', 'itemStyle': {'color': '#9ca3af'}}
    ]
    
    # 11. ext-response-chart
    resp_length = ext_student.get('student_response', {}).get('length', {})
    resp_data = [resp_length.get('short', 0), resp_length.get('medium', 0), resp_length.get('long', 0)]
    
    # 12. ext-feedback-chart
    fb = ext_student.get('teacher_feedback', {})
    fb_data = [
        {'value': fb.get('evaluative', 0), 'name': '评价性', 'itemStyle': {'color': '#6366f1'}},
        {'value': fb.get('directive', 0), 'name': '指导性', 'itemStyle': {'color': '#10b981'}},
        {'value': fb.get('encouraging', 0), 'name': '鼓励性', 'itemStyle': {'color': '#f59e0b'}}
    ]
    
    has_words = "true" if len(word_freq_data) > 0 else "false"
    
    return f'''
    <script>
    (function(){{
        var data = {{
            time_chart: {json.dumps(time_chart_data, ensure_ascii=False)},
            kg_data: {json.dumps(kg_data, ensure_ascii=False)},
            kg_links: {json.dumps(kg_links, ensure_ascii=False)},
            radar_scores: {json.dumps(radar_scores)},
            bloom_levels: {json.dumps(bloom_levels, ensure_ascii=False)},
            bloom_counts: {json.dumps(bloom_counts)},
            hattie_chart: {json.dumps(hattie_chart_data, ensure_ascii=False)},
            word_freq: {json.dumps(word_freq_data, ensure_ascii=False)},
            st_pie: {json.dumps(st_pie_data, ensure_ascii=False)},
            phase_names: {json.dumps(phase_names, ensure_ascii=False)},
            t_pct: {json.dumps(t_pct)},
            s_pct: {json.dumps(s_pct)},
            fourmat: {json.dumps(fourmat_data, ensure_ascii=False)},
            openness: {json.dumps(openness_data, ensure_ascii=False)},
            resp_data: {json.dumps(resp_data)},
            fb_data: {json.dumps(fb_data, ensure_ascii=False)}
        }};
        
        function ic(id, opt) {{
            var d = document.getElementById(id);
            if (!d) return;
            var c = echarts.init(d);
            c.setOption(opt);
        }}
        
        window.addEventListener('DOMContentLoaded', function() {{
            ic('time-chart', {{
                tooltip: {{ trigger: 'item' }},
                legend: {{ bottom: '0%', left: 'center', itemWidth: 10, itemHeight: 10, textStyle: {{ fontSize: 10 }} }},
                series: [{{
                    type: 'pie', radius: '70%', center: ['50%', '40%'],
                    data: data.time_chart,
                    emphasis: {{ itemStyle: {{ shadowBlur: 10, shadowOffsetX: 0, shadowColor: 'rgba(0,0,0,0.5)' }} }}
                }}]
            }});
            
            ic('kg-chart', {{
                series: [{{
                    type: 'graph', layout: 'force', symbolSize: 30,
                    label: {{ show: true, fontSize: 10 }},
                    data: data.kg_data,
                    links: data.kg_links,
                    force: {{ repulsion: 100, edgeLength: 50 }}
                }}]
            }});
            
            ic('radar-chart', {{
                radar: {{
                    indicator: [
                        {{ name: '逻辑', max: 100 }}, {{ name: '互动', max: 100 }},
                        {{ name: '提问', max: 100 }}, {{ name: '支持', max: 100 }},
                        {{ name: '管理', max: 100 }}
                    ],
                    radius: '65%', splitNumber: 3, axisName: {{ fontSize: 10 }}
                }},
                series: [{{
                    type: 'radar',
                    data: [{{ value: data.radar_scores, areaStyle: {{ color: 'rgba(79, 70, 229, 0.2)' }} }}]
                }}]
            }});
            
            ic('bloom-chart', {{
                tooltip: {{ trigger: 'axis' }},
                grid: {{ top: 20, bottom: 20, left: 30, right: 10 }},
                xAxis: {{ type: 'category', data: data.bloom_levels, axisLabel: {{ fontSize: 10 }} }},
                yAxis: {{ type: 'value', splitLine: {{ show: false }} }},
                series: [{{ type: 'bar', data: data.bloom_counts, itemStyle: {{ color: '#6366f1', borderRadius: [3,3,0,0] }} }}]
            }});
            
            ic('hattie-chart', {{
                tooltip: {{ trigger: 'item' }},
                legend: {{ bottom: '0%', left: 'center', itemWidth: 10, itemHeight: 10, textStyle: {{ fontSize: 10 }} }},
                series: [{{
                    type: 'pie', radius: ['40%', '65%'], center: ['50%', '40%'],
                    avoidLabelOverlap: true, label: {{ show: false }}, labelLine: {{ show: false }},
                    data: data.hattie_chart
                }}]
            }});
            
            if (typeof echarts.wordCloud !== 'undefined' || {has_words}) {{
                ic('ext-wordcloud-chart', {{
                    tooltip: {{ show: true }},
                    series: [{{
                        type: 'wordCloud', shape: 'circle',
                        sizeRange: [14, 50], rotationRange: [-30, 30],
                        gridSize: 8, drawOutOfBound: false,
                        textStyle: {{
                            color: function() {{
                                var colors = ['#4f46e5', '#6366f1', '#818cf8', '#ec4899', '#f43f5e', '#10b981', '#f59e0b', '#8b5cf6'];
                                return colors[Math.floor(Math.random() * colors.length)];
                            }}
                        }},
                        data: data.word_freq
                    }}]
                }});
            }}
            
            ic('ext-st-pie-chart', {{
                tooltip: {{ trigger: 'item' }},
                legend: {{ bottom: '0%', left: 'center', itemWidth: 10, itemHeight: 10, textStyle: {{ fontSize: 10 }} }},
                series: [{{
                    type: 'pie', radius: ['35%', '60%'], center: ['50%', '40%'],
                    label: {{ show: false }},
                    data: data.st_pie
                }}]
            }});
            
            ic('ext-st-bar-chart', {{
                tooltip: {{ trigger: 'axis', axisPointer: {{ type: 'shadow' }} }},
                legend: {{ bottom: '0%', left: 'center', itemWidth: 10, itemHeight: 10, textStyle: {{ fontSize: 10 }} }},
                grid: {{ top: 20, bottom: 40, left: 30, right: 10 }},
                xAxis: {{ type: 'category', data: data.phase_names, axisLabel: {{ fontSize: 9 }} }},
                yAxis: {{ type: 'value', max: 100, splitLine: {{ show: false }} }},
                series: [
                    {{ name: '教师', type: 'bar', stack: 'total', itemStyle: {{ color: '#6366f1' }}, data: data.t_pct }},
                    {{ name: '学生', type: 'bar', stack: 'total', itemStyle: {{ color: '#ec4899' }}, data: data.s_pct }}
                ]
            }});
            
            ic('ext-fourmat-chart', {{
                title: {{ text: '4MAT', left: 'center', top:'center', textStyle: {{ fontSize: 12, color: '#6b7280' }} }},
                tooltip: {{ trigger: 'item' }},
                series: [{{
                    type: 'pie', radius: ['45%', '70%'],
                    label: {{ show: false }},
                    data: data.fourmat
                }}]
            }});
            
            ic('ext-openness-chart', {{
                title: {{ text: '开放性', left: 'center', top:'center', textStyle: {{ fontSize: 12, color: '#6b7280' }} }},
                tooltip: {{ trigger: 'item' }},
                series: [{{
                    type: 'pie', radius: ['45%', '70%'],
                    label: {{ show: false }},
                    data: data.openness
                }}]
            }});
            
            ic('ext-response-chart', {{
                tooltip: {{ trigger: 'axis' }},
                grid: {{ top: 30, bottom: 20, left: 30, right: 10 }},
                xAxis: {{ type: 'category', data: ['短(1-5字)','中(6-15字)','长(16+字)'], axisLabel: {{ fontSize: 9 }} }},
                yAxis: {{ type: 'value', splitLine: {{ show: false }} }},
                series: [{{ type: 'bar', data: data.resp_data, itemStyle: {{ color: '#f59e0b', borderRadius: [3,3,0,0] }} }}]
            }});
            
            ic('ext-feedback-chart', {{
                tooltip: {{ trigger: 'item' }},
                legend: {{ bottom: '0%', left: 'center', itemWidth: 10, itemHeight: 10, textStyle: {{ fontSize: 9 }} }},
                series: [{{
                    type: 'pie', radius: ['40%', '65%'], center: ['50%', '40%'],
                    label: {{ show: false }},
                    data: data.fb_data
                }}]
            }});
        }});
    }})();
    </script>
    '''

def generate_combined_html(full_data, extended_data=None, teaching_design=None, folder_name=""):
    css = _build_css()
    sidebar = _build_sidebar()
    header = _build_header_html(full_data, folder_name, extended_data)
    group_a = _build_group_a_html(full_data, teaching_design)
    group_b = _build_group_b_html(full_data, extended_data)
    group_c = _build_group_c_html(full_data, extended_data)
    group_d = _build_group_d_html(full_data, extended_data)
    charts_js = _build_charts_js(full_data, extended_data)
    
    return (
        '<!DOCTYPE html>\n<html lang="zh-CN">\n<head>\n'
        '    <meta charset="utf-8">\n'
        '    <meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
        + f'    <title>课堂分析报告 - {folder_name}</title>\n'
        + '    <script src="https://cdn.tailwindcss.com"></' + 'script>\n'
        + '    <script src="https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js"></' + 'script>\n'
        + '    <script src="https://cdn.jsdelivr.net/npm/echarts-wordcloud@2.1.0/dist/echarts-wordcloud.min.js"></' + 'script>\n'
        + '    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css">\n'
        + css + '\n'
        + '</head>\n<body>\n'
        + sidebar + '\n'
        + '    <main class="main-content" id="main-content">\n'
        + '      <div class="report-content-wrap">\n'
        + header + '\n'
        + group_a + '\n'
        + group_b + '\n'
        + group_c + '\n'
        + group_d + '\n'
        + '        <footer class="text-center text-xs text-gray-400 mt-8 py-4 no-print">\n'
        + '            Generated by ICAS Ultimate System III (Powered by AI)\n'
        + '        </footer>\n'
        + '      </div>\n'
        + '    </main>\n'
        + charts_js + '\n'
        + '</body>\n</html>'
    )

