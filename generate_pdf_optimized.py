#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
PDF分页优化脚本 - 解决图表截断问题
使用更强的分页控制和优化参数
"""

import sys
import os
import asyncio
from pathlib import Path
from datetime import datetime

# 设置Windows控制台编码为UTF-8
if sys.platform == 'win32':
    os.system('chcp 65001 > nul 2>&1')


async def convert_html_to_pdf_optimized(html_path, pdf_path):
    """使用Playwright生成PDF - 分页优化版"""
    try:
        from playwright.async_api import async_playwright

        print(f"\n[PDF] 正在生成PDF（分页优化版）...")
        start_time = datetime.now()

        async with async_playwright() as p:
            # 启动浏览器
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    '--disable-dev-shm-usage',
                    '--no-sandbox',
                    '--disable-gpu',
                ]
            )

            try:
                page = await browser.new_page()

                # 加载HTML
                print(f"[1/5] 加载HTML文件...")
                abs_path = html_path.resolve().absolute()
                await page.goto(
                    f'file:///{abs_path.as_posix()}',
                    wait_until='domcontentloaded',
                    timeout=30000
                )

                # 等待ECharts图表渲染
                print(f"[2/5] 等待图表渲染...")
                try:
                    await page.wait_for_function(
                        """() => {
                            return typeof echarts !== 'undefined' &&
                                   document.querySelectorAll('[id$="-chart"]').length > 0;
                        }""",
                        timeout=15000
                    )
                    print(f"      [OK] 图表已加载")
                except:
                    print(f"      [WARN] 图表加载超时")

                # 注入额外的分页控制CSS
                print(f"[3/5] 注入分页优化CSS...")
                await page.add_style_tag(content="""
                    /* 强制分页控制 */
                    @media print {
                        /* 所有图表容器避免分页 */
                        .chart-container,
                        .chart-wrapper,
                        [id$="-chart"],
                        .no-break,
                        .grid,
                        .border.rounded-xl {
                            page-break-inside: avoid !important;
                            break-inside: avoid !important;
                        }

                        /* 标题避免与内容分离 */
                        h1, h2, h3, h4 {
                            page-break-after: avoid !important;
                            break-after: avoid !important;
                        }

                        /* 图表容器完整显示 */
                        div[id$="-chart"] {
                            page-break-inside: avoid !important;
                            break-inside: avoid !important;
                            max-height: none !important;
                            overflow: visible !important;
                        }

                        /* 避免列表和段落跨页 */
                        p, li, td {
                            orphans: 4 !important;
                            widows: 4 !important;
                        }
                    }
                """)

                # 等待页面稳定
                print(f"[4/5] 等待页面稳定...")
                await page.wait_for_timeout(2000)

                # 生成PDF - 优化分页参数
                print(f"[5/5] 生成PDF（优化分页）...")
                await page.pdf(
                    path=str(pdf_path),
                    format='A4',
                    print_background=True,
                    display_header_footer=False,
                    margin={
                        'top': '1.5cm',      # 增加上边距
                        'right': '1cm',
                        'bottom': '1.5cm',   # 增加下边距
                        'left': '1cm'
                    },
                    scale=0.92,  # 轻微缩小，给内容更多空间
                    prefer_css_page_size=False,
                )

                elapsed_time = (datetime.now() - start_time).total_seconds()
                file_size_mb = os.path.getsize(pdf_path) / 1024 / 1024

                print(f"\n[SUCCESS] PDF生成成功!")
                print(f"    文件: {pdf_path}")
                print(f"    大小: {file_size_mb:.2f} MB")
                print(f"    耗时: {elapsed_time:.1f} 秒")

                return True

            finally:
                await browser.close()

    except ImportError:
        print(f"\n[ERROR] 未安装playwright")
        print(f"[INSTALL] pip install playwright && playwright install chromium")
        return False

    except Exception as e:
        print(f"\n[ERROR] PDF生成失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主函数"""
    print("="*60)
    print("  PDF分页优化工具 - 解决图表截断问题")
    print("="*60)

    if len(sys.argv) < 2:
        print("\n使用方法: python generate_pdf_optimized.py <HTML文件路径> [PDF文件路径]")
        print("\n特性:")
        print("  [OK] 优化的分页控制，避免图表截断")
        print("  [OK] 增加边距，给内容更多空间")
        print("  [OK] 动态注入CSS，确保分页正确")
        print("  [OK] 详细的进度提示")
        sys.exit(1)

    html_path = Path(sys.argv[1])

    if not html_path.exists():
        print(f"\n[ERROR] HTML文件不存在: {html_path}")
        sys.exit(1)

    # 确定PDF路径
    if len(sys.argv) >= 3:
        pdf_path = Path(sys.argv[2])
    else:
        # 默认添加 _optimized 后缀
        pdf_path = html_path.with_stem(html_path.stem + '_optimized').with_suffix('.pdf')

    # 生成PDF
    success = asyncio.run(convert_html_to_pdf_optimized(html_path, pdf_path))

    if success:
        print(f"\n[SUCCESS] PDF文件已保存")
        print(f"[PATH] {pdf_path.absolute()}")
        print(f"\n[TIP] 如果图表仍然被截断，请尝试:")
        print(f"      1. 在浏览器中打开HTML")
        print(f"      2. 按 Ctrl+P")
        print(f"      3. 勾选 '背景图形'")
        print(f"      4. 保存为PDF")
        sys.exit(0)
    else:
        print(f"\n[FAILED] PDF生成失败")
        sys.exit(1)


if __name__ == '__main__':
    main()
