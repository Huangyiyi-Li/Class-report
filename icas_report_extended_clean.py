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



    """返回报告页面所需的CSS样式字符串"""
    return """
    <style>
    /* ========== CSS 变量 ========== */
    :root {
        --sidebar-width: 240px;
        --sidebar-bg: #1e293b;
        --sidebar-text: #cbd5e1;
        --sidebar-heading: #f1f5f9;
        --primary: #4f46e5;
        --primary-light: #818cf8;
        --accent-green: #10b981;
        --accent-pink: #ec4899;
        --accent-amber: #f59e0b;
        --card-bg: #ffffff;
        --card-border: #e2e8f0;
        --page-bg: #f8fafc;
        --shadow-sm: 0 1px 3px rgba(0,0,0,0.08);
        --shadow-md: 0 4px 12px rgba(0,0,0,0.1);
    }

    /* ========== 基础重置 ========== */
    *, *::before, *::after {
        box-sizing: border-box;
    }

    body {
        margin: 0;
        padding: 0;
        background: var(--page-bg);
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Microsoft YaHei", sans-serif;
        color: #1e293b;
        line-height: 1.6;
    }

    /* ========== 主内容区偏移 ========== */
    .main-content {
        margin-left: var(--sidebar-width);
        padding: 24px 32px;
        min-height: 100vh;
        transition: margin-left 0.3s ease;
    }

    /* ========== Section 卡片 ========== */
    .section-card {
        background: var(--card-bg);
        border-radius: 10px;
        padding: 20px 24px;
        margin-bottom: 20px;
        box-shadow: var(--shadow-sm);
        border-left: 4px solid var(--primary);
        position: relative;
    }

    .section-card[data-color="green"] { border-left-color: var(--accent-green); }
    .section-card[data-color="pink"]  { border-left-color: var(--accent-pink); }
    .section-card[data-color="amber"] { border-left-color: var(--accent-amber); }
    .section-card[data-color="indigo"] { border-left-color: var(--primary); }
    .section-card[data-color="purple"] { border-left-color: #8b5cf6; }

    .section-card h2 {
        margin: 0 0 12px 0;
        font-size: 16px;
        font-weight: 700;
        color: #1e293b;
    }

    /* ========== 图表容器 ========== */
    .chart-container {
        page-break-inside: avoid;
        break-inside: avoid;
    }

    /* ========== 排版优化 ========== */
    p {
        orphans: 3;
        widows: 3;
    }

    /* ========== Sidebar ========== */
    .sidebar {
        position: fixed;
        top: 0;
        left: 0;
        width: var(--sidebar-width);
        height: 100vh;
        background: var(--sidebar-bg);
        color: var(--sidebar-text);
        overflow-y: auto;
        z-index: 1000;
        transition: transform 0.3s ease;
        display: flex;
        flex-direction: column;
    }

    .sidebar-header {
        padding: 20px 16px 12px;
        border-bottom: 1px solid rgba(255,255,255,0.08);
    }

    .sidebar-header .report-title {
        font-size: 15px;
        font-weight: 700;
        color: var(--sidebar-heading);
        display: flex;
        align-items: center;
        gap: 8px;
    }

    .sidebar-header .report-title .title-icon {
        width: 28px;
        height: 28px;
        background: var(--primary);
        border-radius: 6px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 14px;
        color: #fff;
        font-weight: 800;
        flex-shrink: 0;
    }

    .sidebar-header .report-subtitle {
        font-size: 11px;
        color: #64748b;
        margin-top: 4px;
        padding-left: 36px;
    }

    .sidebar-body {
        flex: 1;
        overflow-y: auto;
        padding: 12px 0;
    }

    /* Sidebar 分组 */
    .sidebar-group {
        margin-bottom: 4px;
    }

    .sidebar-group-header {
        padding: 8px 16px;
        font-size: 11px;
        font-weight: 700;
        color: #94a3b8;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        cursor: pointer;
        display: flex;
        align-items: center;
        justify-content: space-between;
        user-select: none;
    }

    .sidebar-group-header:hover {
        color: var(--sidebar-heading);
    }

    .sidebar-group-header .toggle-arrow {
        font-size: 10px;
        transition: transform 0.2s;
    }

    .sidebar-group.collapsed .toggle-arrow {
        transform: rotate(-90deg);
    }

    .sidebar-group.collapsed .sidebar-group-items {
        display: none;
    }

    /* Checkbox 项 */
    .sidebar-item {
        padding: 5px 16px 5px 28px;
        display: flex;
        align-items: center;
        gap: 8px;
        cursor: pointer;
        font-size: 12px;
        color: var(--sidebar-text);
        transition: background 0.15s;
    }

    .sidebar-item:hover {
        background: rgba(255,255,255,0.05);
        color: var(--sidebar-heading);
    }

    .sidebar-item input[type="checkbox"] {
        accent-color: var(--primary);
        width: 14px;
        height: 14px;
        cursor: pointer;
        flex-shrink: 0;
    }

    .sidebar-item label {
        cursor: pointer;
        flex: 1;
    }

    /* Sidebar 底部按钮区 */
    .sidebar-footer {
        padding: 12px 16px;
        border-top: 1px solid rgba(255,255,255,0.08);
    }

    .sidebar-footer .btn-row {
        display: flex;
        gap: 6px;
        margin-bottom: 8px;
    }

    .sidebar-footer .btn-row button {
        flex: 1;
        padding: 6px 0;
        font-size: 11px;
        font-weight: 600;
        border: 1px solid rgba(255,255,255,0.15);
        border-radius: 5px;
        background: transparent;
        color: var(--sidebar-text);
        cursor: pointer;
        transition: all 0.15s;
    }

    .sidebar-footer .btn-row button:hover {
        background: rgba(255,255,255,0.1);
        color: var(--sidebar-heading);
    }

    .btn-export-pdf {
        display: block;
        width: 100%;
        padding: 10px 0;
        font-size: 13px;
        font-weight: 700;
        border: none;
        border-radius: 6px;
        background: var(--accent-green);
        color: #fff;
        cursor: pointer;
        text-align: center;
        transition: background 0.15s;
        letter-spacing: 0.5px;
    }

    .btn-export-pdf:hover {
        background: #059669;
    }

    /* ========== Hamburger 按钮 (移动端) ========== */
    .hamburger-btn {
        display: none;
        position: fixed;
        top: 12px;
        left: 12px;
        z-index: 1100;
        width: 40px;
        height: 40px;
        border-radius: 8px;
        background: var(--sidebar-bg);
        border: none;
        color: #fff;
        font-size: 20px;
        cursor: pointer;
        box-shadow: var(--shadow-md);
        align-items: center;
        justify-content: center;
        line-height: 1;
    }

    /* 遮罩层 */
    .sidebar-overlay {
        display: none;
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: rgba(0,0,0,0.4);
        z-index: 999;
    }

    /* ========== 响应式: 移动端 ========== */
    @media (max-width: 767px) {
        .hamburger-btn {
            display: flex;
        }

        .sidebar {
            transform: translateX(-100%);
        }

        .sidebar.open {
            transform: translateX(0);
        }

        .sidebar-overlay.open {
            display: block;
        }

        .main-content {
            margin-left: 0;
            padding: 60px 12px 24px;
        }

        /* 移动端图表高度自适应 */
        .chart-container [id$="-chart"] {
            height: 220px !important;
        }

        .section-card {
            padding: 14px 16px;
            margin-bottom: 14px;
        }

        /* 移动端单列布局 */
        .section-card .grid {
            grid-template-columns: 1fr !important;
        }
    }

    /* ========== 打印样式 ========== */
    @media print {
        @page {
            size: A4;
            margin: 15mm 12mm;
        }

        /* 隐藏 sidebar */
        .sidebar,
        .hamburger-btn,
        .sidebar-overlay,
        .no-print {
            display: none !important;
        }

        /* 主内容区取消偏移 */
        .main-content {
            margin-left: 0 !important;
            padding: 0 !important;
        }

        /* 隐藏未选中的 section */
        .no-print-section {
            display: none !important;
        }

        /* Section 卡片打印优化 */
        .section-card {
            break-inside: avoid;
            page-break-inside: avoid;
            box-shadow: none;
            border: 1px solid #d1d5db;
            margin-bottom: 12px;
        }

        body {
            background: #fff;
        }

        /* 图表避免分页截断 */
        .chart-container {
            page-break-inside: avoid;
            break-inside: avoid;
        }

        /* 排版优化 */
        p {
            orphans: 3;
            widows: 3;
        }

        h1, h2, h3 {
            page-break-after: avoid;
            break-after: avoid;
        }

        /* 打印时隐藏尾注中非必要元素 */
        .print-hide {
            display: none !important;
        }
    }
    </style>
    """





def _build_sidebar():



    """返回报告左侧导航栏的HTML字符串"""
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
                    <div class="sidebar-item">
                        <input type="checkbox" id="chk-sec-overview" data-section="sec-overview" checked>
                        <label for="chk-sec-overview">课堂总览</label>
                    </div>
                    <div class="sidebar-item">
                        <input type="checkbox" id="chk-sec-recommend" data-section="sec-recommend" checked>
                        <label for="chk-sec-recommend">教学建议</label>
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
                    <div class="sidebar-item">
                        <input type="checkbox" id="chk-sec-time" data-section="sec-time" checked>
                        <label for="chk-sec-time">时间分配</label>
                    </div>
                    <div class="sidebar-item">
                        <input type="checkbox" id="chk-sec-knowledge" data-section="sec-knowledge" checked>
                        <label for="chk-sec-knowledge">知识点覆盖</label>
                    </div>
                    <div class="sidebar-item">
                        <input type="checkbox" id="chk-sec-checklist" data-section="sec-checklist" checked>
                        <label for="chk-sec-checklist">教学清单</label>
                    </div>
                    <div class="sidebar-item">
                        <input type="checkbox" id="chk-sec-scaffold" data-section="sec-scaffold" checked>
                        <label for="chk-sec-scaffold">支架分析</label>
                    </div>
                    <div class="sidebar-item">
                        <input type="checkbox" id="chk-sec-st" data-section="sec-st" checked>
                        <label for="chk-sec-st">S-T 师生行为</label>
                    </div>
                    <div class="sidebar-item">
                        <input type="checkbox" id="chk-sec-speech" data-section="sec-speech" checked>
                        <label for="chk-sec-speech">语速分析</label>
                    </div>
                    <div class="sidebar-item">
                        <input type="checkbox" id="chk-sec-wordcloud" data-section="sec-wordcloud" checked>
                        <label for="chk-sec-wordcloud">高频词汇</label>
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
                    <div class="sidebar-item">
                        <input type="checkbox" id="chk-sec-radar" data-section="sec-radar" checked>
                        <label for="chk-sec-radar">能力雷达图</label>
                    </div>
                    <div class="sidebar-item">
                        <input type="checkbox" id="chk-sec-bloom" data-section="sec-bloom" checked>
                        <label for="chk-sec-bloom">布鲁姆分层</label>
                    </div>
                    <div class="sidebar-item">
                        <input type="checkbox" id="chk-sec-hattie" data-section="sec-hattie" checked>
                        <label for="chk-sec-hattie">Hattie 可见学习</label>
                    </div>
                    <div class="sidebar-item">
                        <input type="checkbox" id="chk-sec-chains" data-section="sec-chains" checked>
                        <label for="chk-sec-chains">问题链分析</label>
                    </div>
                    <div class="sidebar-item">
                        <input type="checkbox" id="chk-sec-fourmat" data-section="sec-fourmat" checked>
                        <label for="chk-sec-fourmat">4MAT 分类</label>
                    </div>
                    <div class="sidebar-item">
                        <input type="checkbox" id="chk-sec-interaction" data-section="sec-interaction" checked>
                        <label for="chk-sec-interaction">互动分析</label>
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
                    <div class="sidebar-item">
                        <input type="checkbox" id="chk-sec-thinking" data-section="sec-thinking" checked>
                        <label for="chk-sec-thinking">思维五维分析</label>
                    </div>
                    <div class="sidebar-item">
                        <input type="checkbox" id="chk-sec-response" data-section="sec-response" checked>
                        <label for="chk-sec-response">学生应答</label>
                    </div>
                    <div class="sidebar-item">
                        <input type="checkbox" id="chk-sec-feedback-detail" data-section="sec-feedback-detail" checked>
                        <label for="chk-sec-feedback-detail">教师反馈</label>
                    </div>
                    <div class="sidebar-item">
                        <input type="checkbox" id="chk-sec-cognition" data-section="sec-cognition" checked>
                        <label for="chk-sec-cognition">认知诊断</label>
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

        // 导出 PDF
        var btnExportPdf = document.getElementById('btnExportPdf');
        if (btnExportPdf) {
            btnExportPdf.addEventListener('click', function() {
                // 根据checkbox状态，给未选中的section加上 no-print-section 类
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
                window.print();
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
      <h3 class="section-title"><i class="fa-solid fa-binoculars"></i> 宏观教学综述</h3>
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
      <h3 class="section-title"><i class="fa-solid fa-lightbulb"></i> 导师改进建议</h3>
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
      <h3 class="section-title"><i class="fa-solid fa-clock"></i> 时间分配</h3>
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
      <h3 class="section-title"><i class="fa-solid fa-diagram-project"></i> 知识图谱</h3>
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
      <h3 class="section-title"><i class="fa-solid fa-list-check"></i> 教学常规核查</h3>
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
      <h3 class="section-title"><i class="fa-solid fa-layer-group"></i> 知识脚手架分析</h3>
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
          <h3 class="section-title"><i class="fa-solid fa-chart-pie"></i> S-T 师生行为分析</h3>
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
          <h3 class="section-title"><i class="fa-solid fa-chart-pie"></i> S-T 师生行为分析</h3>
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
          <h3 class="section-title"><i class="fa-solid fa-microphone"></i> 语速分析</h3>
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
          <h3 class="section-title"><i class="fa-solid fa-microphone"></i> 语速分析</h3>
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
          <h3 class="section-title"><i class="fa-solid fa-cloud"></i> 高频词汇</h3>
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
          <h3 class="section-title"><i class="fa-solid fa-cloud"></i> 高频词汇</h3>
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
      <h3 class="section-title"><i class="fa-solid fa-satellite-dish"></i> 五维能力雷达</h3>
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
      <h3 class="section-title"><i class="fa-solid fa-layer-group"></i> 认知激发深度 (Bloom)</h3>
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
      <h3 class="section-title"><i class="fa-solid fa-chart-pie"></i> 反馈质量分布 (Hattie)</h3>
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
        q_li = "".join([f'<li class="text-xs text-gray-600 mb-1">{q}</li>' for q in c.get('questions', [])])
        chain_cards += f'''
            <div class="bg-white rounded-lg border p-3 shadow-sm mb-3">
                <div class="flex items-center gap-2 mb-2">
                    <span class="inline-block px-2 py-0.5 rounded text-white text-xs font-bold" style="background:{color}">{c.get('thinking_type','')}</span>
                    <span class="text-sm font-semibold text-gray-800">{c.get('topic','')}</span>
                </div>
                <div class="flex gap-1 mb-2">
                    <span class="text-xs px-1.5 py-0.5 bg-blue-50 text-blue-700 rounded border border-blue-100">{c.get('question_type','')}</span>
                    <span class="text-xs px-1.5 py-0.5 bg-gray-50 text-gray-600 rounded border border-gray-200">{c.get('complexity','')}</span>
                </div>
                <ul class="list-disc list-inside mt-2">{q_li}</ul>
            </div>'''
            
    chain_analysis = _safe_get(extended_data, "qa_analysis", "chain_analysis", default="") if extended_data else ""
    chain_suggestions = _safe_get(extended_data, "qa_analysis", "chain_suggestions", default="") if extended_data else ""
    
    html += f'''
    <section id="sec-chains" class="section-card printable" style="border-left: 4px solid #8b5cf6;">
      <h3 class="section-title"><i class="fa-solid fa-link"></i> 问题链分析</h3>
      <div class="section-body">
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
            {chain_cards if chain_cards else '<p class="text-muted">暂无问题链数据</p>'}
        </div>
        {"<div class='mt-4 p-3 bg-gray-50 rounded text-sm text-gray-700'><span class='font-bold'>分析: </span>" + chain_analysis + "</div>" if chain_analysis else ""}
        {"<div class='mt-2 p-3 bg-blue-50 rounded text-sm text-blue-800'><span class='font-bold'>建议: </span>" + chain_suggestions + "</div>" if chain_suggestions else ""}
      </div>
    </section>
    '''
    
    # sec-fourmat
    html += f'''
    <section id="sec-fourmat" class="section-card printable" style="border-left: 4px solid #6366f1;">
      <h3 class="section-title"><i class="fa-solid fa-shapes"></i> 问题分类统计</h3>
      <div class="section-body">
        <div class="grid grid-cols-2 gap-4">
            <div class="chart-container">
                <div id="ext-fourmat-chart" style="width:100%; height:200px;"></div>
            </div>
            <div class="chart-container">
                <div id="ext-openness-chart" style="width:100%; height:200px;"></div>
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
        <div class="bg-white border border-gray-200 rounded-xl p-5 mb-4 shadow-sm no-break">
            <h4 class="font-bold text-indigo-700 mb-2 border-b border-indigo-100 pb-2">{m.get('title','')}</h4>
            <div class="bg-gray-50 p-3 rounded text-sm font-mono text-gray-600 mb-3 whitespace-pre-wrap">{m.get('dialogue','')}</div>
            <div class="flex items-start gap-2">
                <span class="text-xl">👩‍🏫</span>
                <p class="text-gray-700 text-sm italic leading-relaxed"><span class="font-bold text-gray-900">导师点评: </span>{m.get('analysis','')}</p>
            </div>
        </div>
        '''
        
    html += f'''
    <section id="sec-interaction" class="section-card printable" style="border-left: 4px solid #4f46e5;">
      <h3 class="section-title"><i class="fa-solid fa-comments"></i> 关键互动切片 (Micro-Teaching)</h3>
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
    lc = {"全面体现": "#10b981", "初步体现": "#f59e0b", "尚未体现": "#ef4444"}
    lb = {"全面体现": "#ecfdf5", "初步体现": "#fffbeb", "尚未体现": "#fef2f2"}
    thinking_cards = ""
    for t in thinking:
        level = t.get('level', '尚未体现')
        thinking_cards += f'''
            <div class="rounded-lg border p-3 shadow-sm" style="background:{lb.get(level,'#f9fafb')}; border-color:{lc.get(level,'#9ca3af')}30">
                <div class="flex items-center justify-between mb-1">
                    <span class="font-bold text-sm text-gray-800">{t.get('type','')}</span>
                    <span class="text-xs font-bold px-2 py-0.5 rounded-full text-white" style="background:{lc.get(level,'#9ca3af')}">{level}</span>
                </div>
                <p class="text-xs text-gray-600 leading-relaxed">{t.get('analysis','')}</p>
                <p class="text-xs text-blue-600 mt-1">{t.get('suggestion','')}</p>
            </div>'''
            
    html += f'''
    <section id="sec-thinking" class="section-card printable" style="border-left: 4px solid #10b981;">
      <h3 class="section-title"><i class="fa-solid fa-brain"></i> 学生思维五维分析</h3>
      <div class="section-body">
        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
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
      <h3 class="section-title"><i class="fa-solid fa-hand-sparkles"></i> 学生应答分析</h3>
      <div class="section-body">
        <div class="grid grid-cols-2 gap-4 mb-4">
            <div class="chart-container">
                <div id="ext-response-chart" style="width:100%; height:200px;"></div>
            </div>
            <div class="flex flex-col justify-center text-sm text-gray-600 space-y-2">
                <p><strong>总体应答:</strong> <span class="text-lg font-bold text-gray-800">{resp_total}</span> 次</p>
                <p><strong>主动应答:</strong> {resp_active}%</p>
                <p><strong>被动应答:</strong> {resp_passive}%</p>
                {"<p class='mt-2 p-2 bg-gray-50 rounded text-xs'><strong>分 </strong>" + resp_analysis + "</p>" if resp_analysis else ""}
                {"<p class='mt-1 p-2 bg-blue-50 rounded text-xs text-blue-700'><strong>建 </strong>" + resp_suggestions + "</p>" if resp_suggestions else ""}
            </div>
        </div>
      </div>
    </section>
    '''
    
    # sec-feedback-detail
    phrases = _safe_get(extended_data, "student_analysis", "common_phrases", default=[]) if extended_data else []
    phrase_html = ""
    for p in phrases:
        phrase_html += f'''
            <div class="bg-gray-50 border-l-4 border-indigo-400 p-3 rounded-r-lg mb-2">
                <p class="text-sm text-gray-800 italic font-bold">"{p.get('phrase','')}"</p>
                <span class="text-xs text-gray-500">[{p.get('type','')}] {p.get('context','')}</span>
            </div>'''
            
    fb = _safe_get(extended_data, "student_analysis", "teacher_feedback", default={}) if extended_data else {}
    fb_analysis = fb.get('analysis', '')
    fb_suggestions = fb.get('suggestions', '')
            
    html += f'''
    <section id="sec-feedback-detail" class="section-card printable" style="border-left: 4px solid #ec4899;">
      <h3 class="section-title"><i class="fa-solid fa-comment-dots"></i> 教师反馈分析</h3>
      <div class="section-body">
        <div class="grid grid-cols-2 gap-4 mb-4">
            <div class="chart-container">
                <div id="ext-feedback-chart" style="width:100%; height:200px;"></div>
            </div>
            <div class="flex flex-col justify-center text-sm text-gray-600">
                {"<p class='mb-2 p-2 bg-gray-50 rounded text-xs'><strong>分 </strong>" + fb_analysis + "</p>" if fb_analysis else ""}
                {"<p class='p-2 bg-blue-50 rounded text-xs text-blue-700'><strong>建 </strong>" + fb_suggestions + "</p>" if fb_suggestions else ""}
            </div>
        </div>
        <div class="mt-4 border-t pt-4">
            <h4 class="font-bold text-gray-700 mb-2 text-sm"><i class="fa-solid fa-quote-left mr-1"></i>常用反馈语分析</h4>
            {phrase_html if phrase_html else '<p class="text-muted text-xs">暂无常用反馈语</p>'}
        </div>
      </div>
    </section>
    '''
    
    # sec-cognition
    cognition = _safe_get(full_data, "report", "student_cognition", default="")
    html += f'''
    <section id="sec-cognition" class="section-card printable" style="border-left: 4px solid #10b981;">
      <h3 class="section-title"><i class="fa-solid fa-magnifying-glass-chart"></i> 学生认知诊断</h3>
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
        + '    <script src="https://cdn.tailwindcss.com"><\/script>\n'
        + '    <script src="https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js"><\/script>\n'
        + '    <script src="https://cdn.jsdelivr.net/npm/echarts-wordcloud@2.1.0/dist/echarts-wordcloud.min.js"><\/script>\n'
        + '    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css">\n'
        + css + '\n'
        + '</head>\n<body>\n'
        + sidebar + '\n'
        + '    <main class="main-content" id="main-content">\n'
        + header + '\n'
        + group_a + '\n'
        + group_b + '\n'
        + group_c + '\n'
        + group_d + '\n'
        + '        <footer class="text-center text-xs text-gray-400 mt-8 py-4 no-print">\n'
        + '            Generated by ICAS Ultimate System III (Powered by AI)\n'
        + '        </footer>\n'
        + '    </main>\n'
        + charts_js + '\n'
        + '</body>\n</html>'
    )

