# -*- coding: utf-8 -*-
"""
PDF 优化方案 - 课堂录音分析报告
解决分页和浏览器卡死问题
"""

# ========================================
# 优化方案 1: 改进的 @media print CSS
# ========================================

IMPROVED_PRINT_CSS = """
@media print {
    /* 基础设置 */
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

    /* ========== 关键分页控制 ========== */

    /* 页面内元素避免分割 */
    .no-break,
    .bg-white.border.rounded-xl,
    .grid.grid-cols-2,
    #time-chart,
    #bloom-chart,
    #hattie-chart,
    #kg-chart,
    #radar-chart {
        page-break-inside: avoid !important;
        break-inside: avoid !important;
    }

    /* 主要章节前强制分页 */
    .mb-6:nth-of-type(1),
    h2.section-title {
        page-break-before: auto !important;
        break-before: auto !important;
    }

    /* 特定章节强制分页 */
    #micro-teaching {
        page-break-before: always !important;
        break-before: page !important;
    }

    /* 图表容器避免跨页 */
    [id$="-chart"] {
        page-break-inside: avoid !important;
        break-inside: avoid !important;
        max-height: 400px !important;
        overflow: hidden !important;
    }

    /* 文本段落优化 */
    p, li, td {
        orphans: 3 !important;
        widows: 3 !important;
    }

    /* 标题避免与后续内容分离 */
    h2, h3, h4 {
        page-break-after: avoid !important;
        break-after: avoid !important;
    }

    /* 减少边距以节省空间 */
    .mb-6 {
        margin-bottom: 1rem !important;
    }

    .mb-8 {
        margin-bottom: 1.5rem !important;
    }

    /* 字体大小优化 */
    .text-3xl {
        font-size: 1.5rem !important;
    }

    .text-sm {
        font-size: 0.8rem !important;
    }
}
"""

# ========================================
# 优化方案 2: Playwright PDF 生成配置
# ========================================

IMPROVED_PLAYWRIGHT_CONFIG = """
async def convert_html_to_pdf_optimized(html_path, pdf_path):
    '''优化后的 Playwright PDF 生成'''
    try:
        from playwright.async_api import async_playwright

        print(f"[PDF] 正在生成PDF文件(优化模式)...")

        async with async_playwright() as p:
            # 启动浏览器时添加性能优化参数
            browser = await p.chromium.launch(
                args=[
                    '--disable-dev-shm-usage',  # 解决资源限制问题
                    '--no-sandbox',              # 在某些环境中必需
                    '--disable-gpu',             # 禁用GPU加速
                ]
            )

            try:
                page = await browser.new_page()

                # 加载HTML文件
                await page.goto(f'file:///{html_path.as_posix()}')

                # 等待页面完全加载,包括图表渲染
                await page.wait_for_load_state('networkidle')
                await page.wait_for_timeout(2000)  # 额外等待2秒确保图表渲染完成

                # 生成PDF - 使用优化的参数
                await page.pdf(
                    path=str(pdf_path),
                    format='A4',
                    print_background=True,
                    display_header_footer=False,  # 不显示页眉页脚
                    margin={
                        'top': '1cm',      # 增加上边距避免内容被裁剪
                        'right': '0.8cm',
                        'bottom': '1cm',
                        'left': '0.8cm'
                    },
                    scale=0.95,  # 轻微缩放以适应更多内容
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
# 优化方案 3: 使用 WeasyPrint (推荐)
# ========================================

WEASYPRINT_SOLUTION = """
# 安装: pip install weasyprint

def convert_html_to_pdf_weasyprint(html_path, pdf_path):
    '''使用 WeasyPrint 生成 PDF - 更稳定,支持 CSS 分页'''
    try:
        from weasyprint import HTML, CSS

        print(f"[PDF] 正在生成PDF文件(WeasyPrint模式)...")

        # 读取 HTML 文件
        with open(html_path, 'r', encoding='utf-8') as f:
            html_content = f.read()

        # 添加额外的打印样式
        print_css = CSS(string="""
            @page {
                size: A4;
                margin: 1cm;
            }

            body {
                font-family: "Microsoft YaHei", sans-serif;
            }

            /* 避免元素跨页分割 */
            .no-break,
            .bg-white.border.rounded-xl {
                page-break-inside: avoid;
            }

            /* 章节分页 */
            h2.section-title {
                page-break-after: avoid;
            }

            /* 图表避免分割 */
            [id$="-chart"] {
                page-break-inside: avoid;
                max-height: 450px;
            }
        """)

        # 生成 PDF
        HTML(string=html_content, base_url=str(html_path.parent)).write_pdf(
            str(pdf_path),
            stylesheets=[print_css],
            presentational_hints=True
        )

        print(f"[PDF] PDF生成成功!")
        return True

    except ImportError:
        print(f"[警告] 未安装weasyprint")
        print(f"[提示] 安装方法: pip install weasyprint")
        return False

    except Exception as e:
        print(f"[错误] PDF生成失败: {e}")
        return False
"""

# ========================================
# 优化方案 4: HTML 结构优化
# ========================================

HTML_STRUCTURE_TIPS = """
在 generate_ultimate_html 函数中添加以下 class:

1. 为主要章节添加分页控制:
   <div class="mb-6 page-break-before">
       <h2 class="section-title">微格教学切片</h2>
       ...
   </div>

2. 为卡片添加防分割 class:
   <div class="bg-white border border-gray-200 rounded-xl p-5 mb-4 shadow-sm no-break">
       ...
   </div>

3. 为图表添加容器限制:
   <div class="chart-container no-break" style="max-height: 400px; overflow: hidden;">
       <div id="time-chart" style="width: 100%; height: 200px;"></div>
   </div>
"""

# ========================================
# 使用说明
# ========================================

USAGE_GUIDE = """
实施步骤:

方案 1: 最小改动 (推荐先尝试)
-----------------------------
1. 在 icas_core.py 的 @media print 中添加上面的 IMPROVED_PRINT_CSS
2. 在 auto_analyze_pdf.py 中使用 IMPROVED_PLAYWRIGHT_CONFIG
3. 重新运行测试

方案 2: 使用 WeasyPrint (推荐)
-----------------------------
1. pip install weasyprint
2. 在 auto_analyze_pdf.py 中替换 convert_html_to_pdf_playwright 函数
3. 重新运行测试

方案 3: 组合方案 (最佳效果)
-----------------------------
1. 同时应用方案 1 和方案 2
2. 优先使用 WeasyPrint,失败时回退到 Playwright
3. 添加 HTML 结构优化

预期效果:
- PDF 正确分页,内容不跨页
- 浏览器不再卡死
- 生成速度提升
"""

if __name__ == "__main__":
    print(USAGE_GUIDE)
