#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
图表截断问题修复方案
解决PDF中图表被截断的问题
"""

# ========================================
# 问题分析
# ========================================

PROBLEM_ANALYSIS = """
问题原因：
1. CSS中使用了 overflow: hidden - 会直接截断图表
2. 图表在grid布局中，没有专门的容器保护
3. Playwright等待时间不足，图表可能未完全渲染
4. CSS的max-height限制太严格

当前问题代码：
@media print {
    [id$="-chart"] {
        max-height: 400px !important;    # 限制太严格
        overflow: hidden !important;      # 会截断！
    }
}
"""

# ========================================
# 解决方案 1: 优化CSS（推荐）
# ========================================

IMPROVED_CSS = """
@media print {
    body {
        background: white !important;
        -webkit-print-color-adjust: exact !important;
        print-color-adjust: exact !important;
    }

    .paper {
        width: 100% !important;
        max-width: none !important;
        box-shadow: none !important;
        padding: 0 !important;
        margin: 0 !important;
    }

    .no-print {
        display: none !important;
    }

    /* ========== 关键修复：图表容器 ========== */

    /* 为图表添加专门的容器类 */
    .chart-container {
        page-break-inside: avoid !important;
        break-inside: avoid !important;
        page-break-before: auto !important;
        break-before: auto !important;
        page-break-after: auto !important;
        break-after: auto !important;
    }

    /* 外层的grid和卡片也要避免分割 */
    .no-break,
    .bg-white.border.rounded-xl,
    .grid.grid-cols-2,
    .grid.grid-cols-3 {
        page-break-inside: avoid !important;
        break-inside: avoid !important;
    }

    /* 标题不与内容分离 */
    h2, h3, h4 {
        page-break-after: avoid !important;
        break-after: avoid !important;
    }

    /* 文本段落优化 */
    p, li, td {
        orphans: 3 !important;
        widows: 3 !important;
    }

    /* ========== 修复：不要截断图表 ========== */

    /* 移除overflow限制，允许图表完整显示 */
    [id$="-chart"] {
        page-break-inside: avoid !important;
        break-inside: avoid !important;
        /* 不要使用 overflow: hidden */
        /* 不要使用 max-height 限制 */
    }

    /* 如果图表太高，允许适当调整 */
    .chart-wrapper {
        page-break-inside: avoid !important;
        break-inside: avoid !important;
        min-height: 200px;
        /* 允许内容自适应，不强制截断 */
    }

    /* 优化边距和字体 */
    .mb-6 {
        margin-bottom: 1rem !important;
    }

    .mb-8 {
        margin-bottom: 1.5rem !important;
    }

    .text-3xl {
        font-size: 1.5rem !important;
    }

    .text-sm {
        font-size: 0.8rem !important;
    }
}
"""

# ========================================
# 解决方案 2: HTML结构优化
# ========================================

HTML_STRUCTURE_FIX = """
在每个图表外层添加专门的容器：

当前结构（问题）：
<div class="grid grid-cols-2 gap-4">
    <div id="time-chart" style="width: 100%; height: 200px;"></div>
</div>

修复后结构：
<div class="grid grid-cols-2 gap-4 chart-container">
    <div class="chart-wrapper">
        <div id="time-chart" style="width: 100%; height: 200px;"></div>
    </div>
</div>

关键点：
1. 添加 chart-container class 到grid容器
2. 添加 chart-wrapper class 包裹图表
3. 确保每个容器都有 page-break-inside: avoid
"""

# ========================================
# 解决方案 3: Playwright配置优化
# ========================================

PLAYWRIGHT_CONFIG_FIX = """
async def convert_html_to_pdf_playwright(html_path, pdf_path):
    '''优化的PDF生成配置'''
    try:
        from playwright.async_api import async_playwright

        print(f"[PDF] 正在生成PDF文件...")

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                args=[
                    '--disable-dev-shm-usage',
                    '--no-sandbox',
                    '--disable-gpu',
                ]
            )

            try:
                page = await browser.new_page()

                # 加载HTML
                await page.goto(f'file:///{html_path.as_posix()}')

                # 等待页面加载
                await page.wait_for_load_state('networkidle')

                # ========== 关键：等待图表完全渲染 ==========
                # 增加等待时间到5秒
                await page.wait_for_timeout(5000)

                # 或者使用更精确的等待方式
                # await page.wait_for_selector('[id$="-chart"]', state='attached')

                # 生成PDF
                await page.pdf(
                    path=str(pdf_path),
                    format='A4',
                    print_background=True,
                    display_header_footer=False,
                    margin={
                        'top': '1.5cm',    # 增加上边距
                        'right': '1cm',
                        'bottom': '1.5cm', # 增加下边距
                        'left': '1cm'
                    },
                    scale=1.0,  # 使用1.0，不要缩放
                    prefer_css_page_size=False,
                )

                print(f"[PDF] PDF生成成功!")
                return True

            finally:
                await browser.close()

    except Exception as e:
        print(f"[错误] PDF生成失败: {e}")
        return False
"""

# ========================================
# 解决方案 4: 使用WeasyPrint（最佳）
# ========================================

WEASYPRINT_SOLUTION = """
WeasyPrint对图表的支持最好，因为：
1. 不依赖浏览器渲染
2. 不会截断图表
3. 分页控制更精确
4. 性能更稳定

安装：
pip install weasyprint

使用：
from weasyprint import HTML, CSS

HTML(string=html_content).write_pdf(
    output_path,
    stylesheets=[CSS(string=print_css)]
)
"""

# ========================================
# 快速修复步骤
# ========================================

QUICK_FIX_STEPS = """
步骤1：修改 icas_core.py 中的 @media print CSS
------------------------------------------------
找到 @media print 部分，替换为：

@media print {
    body { background: white !important; -webkit-print-color-adjust: exact !important; print-color-adjust: exact !important; }
    .paper { width: 100% !important; max-width: none !important; box-shadow: none !important; padding: 0 !important; margin: 0 !important; }
    .no-print { display: none !important; }

    /* 图表容器 */
    .chart-container, .chart-wrapper,
    .no-break, .bg-white.border.rounded-xl, .grid {
        page-break-inside: avoid !important;
        break-inside: avoid !important;
    }

    h2, h3, h4 { page-break-after: avoid !important; break-after: avoid !important; }

    p, li, td { orphans: 3 !important; widows: 3 !important; }
}

步骤2：修改 auto_analyze_pdf.py 的等待时间
------------------------------------------------
将 wait_for_timeout(2000) 改为 wait_for_timeout(5000)

步骤3：重新生成PDF测试
------------------------------------------------
python auto_analyze_pdf.py "文件夹路径"
"""

# ========================================
# 最佳推荐方案
# ========================================

BEST_SOLUTION = """
方案A：CSS修复 + Playwright优化（快速）
- 修改CSS，移除overflow限制
- 增加等待时间到5秒
- 重新测试

方案B：使用WeasyPrint（推荐，最稳定）
- 安装WeasyPrint
- 使用 auto_analyze_pdf_weasyprint.py
- 图表不会被截断，分页更准确

方案C：调整图表高度（临时方案）
- 减小图表高度：height: 180px
- 增加容器padding
- 可能会影响视觉效果
"""

if __name__ == "__main__":
    print("=" * 60)
    print("图表截断问题修复方案")
    print("=" * 60)
    print()
    print(PROBLEM_ANALYSIS)
    print()
    print(QUICK_FIX_STEPS)
    print()
    print("推荐：使用 WeasyPrint 方案（最稳定）")
