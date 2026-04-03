#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
PDF智能分页脚本 - 图表不截断，文字可跨页
最终优化版 - 解决大段空白问题
"""

import sys
import os
import asyncio
from pathlib import Path
from datetime import datetime

# 设置Windows控制台编码为UTF-8
if sys.platform == 'win32':
    os.system('chcp 65001 > nul 2>&1')


async def convert_html_to_pdf_final(html_path, pdf_path):
    """智能分页PDF - 最终版"""
    try:
        from playwright.async_api import async_playwright

        print(f"\n[PDF] 正在生成PDF（智能分页版）...")
        print(f"      图表不截断，文字可跨页")
        start_time = datetime.now()

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=['--disable-dev-shm-usage', '--no-sandbox', '--disable-gpu']
            )

            try:
                page = await browser.new_page()

                # 加载HTML
                print(f"[1/4] 加载HTML文件...")
                abs_path = html_path.resolve().absolute()
                await page.goto(
                    f'file:///{abs_path.as_posix()}',
                    wait_until='domcontentloaded',
                    timeout=30000
                )

                # 等待图表渲染
                print(f"[2/4] 等待图表渲染...")
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

                # 注入智能分页CSS - 关键优化
                print(f"[3/4] 注入智能分页CSS...")
                await page.add_style_tag(content="""
                    @media print {
                        /* ========== 核心策略 ========== */

                        /* 1. 图表 - 绝对不截断 */
                        [id$="-chart"],
                        div[id*="chart"] {
                            page-break-inside: avoid !important;
                            break-inside: avoid !important;
                            display: block !important;
                        }

                        /* 2. 标题 - 不与内容分离 */
                        h1, h2, h3, h4 {
                            page-break-after: avoid !important;
                            break-after: avoid !important;
                        }

                        /* 3. 关键：移除容器的分页限制 - 允许文字跨页 */
                        .mb-6,
                        .border.rounded-xl,
                        .bg-indigo-50,
                        .chart-container,
                        .chart-wrapper,
                        .grid {
                            page-break-inside: auto !important;
                            break-inside: auto !important;
                        }

                        /* 4. 文字内容 - 允许跨页 */
                        p, li, td, div, span {
                            page-break-inside: auto !important;
                            break-inside: auto !important;
                        }

                        /* 5. 段落优化 */
                        p, li {
                            orphans: 3 !important;
                            widows: 3 !important;
                        }

                        /* 6. 小标签避免跨页 */
                        .tag-pill {
                            page-break-inside: avoid !important;
                        }
                    }
                """)

                # 等待页面稳定
                print(f"[4/4] 等待页面稳定...")
                await page.wait_for_timeout(2000)

                # 生成PDF
                print(f"[PDF] 生成PDF...")
                await page.pdf(
                    path=str(pdf_path),
                    format='A4',
                    print_background=True,
                    display_header_footer=False,
                    margin={
                        'top': '1.2cm',
                        'right': '1cm',
                        'bottom': '1.2cm',
                        'left': '1cm'
                    },
                    scale=0.95,
                    prefer_css_page_size=False,
                )

                elapsed_time = (datetime.now() - start_time).total_seconds()
                file_size_mb = os.path.getsize(pdf_path) / 1024 / 1024

                print(f"\n[SUCCESS] PDF生成成功!")
                print(f"    文件: {pdf_path}")
                print(f"    大小: {file_size_mb:.2f} MB")
                print(f"    耗时: {elapsed_time:.1f} 秒")
                print(f"\n[特点]")
                print(f"    [OK] 图表完整不截断")
                print(f"    [OK] 文字可以跨页")
                print(f"    [OK] 减少空白页面")
                print(f"    [OK] 优化页面布局")

                return True

            finally:
                await browser.close()

    except Exception as e:
        print(f"\n[ERROR] PDF生成失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主函数"""
    print("="*60)
    print("  PDF智能分页工具 v3.0（最终版）")
    print("="*60)
    print("\n特性:")
    print("  [OK] 图表绝对不截断")
    print("  [OK] 文字内容可以跨页")
    print("  [OK] 减少大段空白")
    print("  [OK] 优化页面布局")

    if len(sys.argv) < 2:
        print("\n使用方法: python generate_pdf_final.py <HTML文件路径> [PDF文件路径]")
        print("\n示例:")
        print("  python generate_pdf_final.py \"../第十次课0323/报告.html\"")
        sys.exit(1)

    html_path = Path(sys.argv[1])

    if not html_path.exists():
        print(f"\n[ERROR] HTML文件不存在: {html_path}")
        sys.exit(1)

    # 确定PDF路径
    if len(sys.argv) >= 3:
        pdf_path = Path(sys.argv[2])
    else:
        pdf_path = html_path.with_stem(html_path.stem + '_final').with_suffix('.pdf')

    # 生成PDF
    success = asyncio.run(convert_html_to_pdf_final(html_path, pdf_path))

    if success:
        print(f"\n[SUCCESS] PDF文件已保存")
        print(f"[PATH] {pdf_path.absolute()}")
        sys.exit(0)
    else:
        print(f"\n[FAILED] PDF生成失败")
        sys.exit(1)


if __name__ == '__main__':
    main()
