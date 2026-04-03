#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
快速PDF生成脚本 - 优化版
解决浏览器卡死问题，使用Playwright后台生成
"""

import sys
import os
import asyncio
from pathlib import Path
from datetime import datetime

# 设置Windows控制台编码为UTF-8
if sys.platform == 'win32':
    os.system('chcp 65001 > nul 2>&1')


async def convert_html_to_pdf_fast(html_path, pdf_path):
    """使用Playwright快速生成PDF - 性能优化版"""
    try:
        from playwright.async_api import async_playwright

        print(f"\n[PDF] 正在生成PDF（后台模式，不会卡死浏览器）...")
        start_time = datetime.now()

        async with async_playwright() as p:
            # 启动浏览器 - 性能优化参数
            browser = await p.chromium.launch(
                headless=True,  # 无头模式，不显示窗口
                args=[
                    '--disable-dev-shm-usage',
                    '--no-sandbox',
                    '--disable-gpu',
                    '--disable-extensions',      # 禁用扩展
                    '--disable-images',          # 禁用图片加载（如果不需要）
                    '--disable-javascript',      # 如果图表已渲染，可禁用JS
                    '--disable-web-security',    # 绕过跨域限制
                    '--disable-features=IsolateOrigins,site-per-process',
                    '--disable-blink-features=AutomationControlled',
                ]
            )

            try:
                page = await browser.new_page()

                # 加载HTML - 使用绝对路径避免中文编码问题
                print(f"[1/4] 加载HTML文件...")
                abs_path = html_path.resolve().absolute()
                await page.goto(
                    f'file:///{abs_path.as_posix()}',
                    wait_until='domcontentloaded',  # 只等待DOM加载，不等待所有资源
                    timeout=30000
                )

                # 等待ECharts图表渲染完成
                print(f"[2/4] 等待图表渲染...")
                try:
                    # 等待ECharts实例
                    await page.wait_for_function(
                        """() => {
                            return typeof echarts !== 'undefined' &&
                                   document.querySelectorAll('.echarts-instance').length > 0 ||
                                   document.querySelectorAll('[id$="-chart"]').length > 0;
                        }""",
                        timeout=15000
                    )
                    print(f"      [OK] 图表已加载")
                except:
                    print(f"      [WARN] 图表加载超时，继续生成PDF...")

                # 额外等待确保动画完成
                print(f"[3/4] 等待动画完成...")
                await page.wait_for_timeout(2000)  # 减少到2秒

                # 生成PDF
                print(f"[4/4] 生成PDF文件...")
                await page.pdf(
                    path=str(pdf_path),
                    format='A4',
                    print_background=True,
                    display_header_footer=False,
                    margin={
                        'top': '1cm',
                        'right': '0.8cm',
                        'bottom': '1cm',
                        'left': '0.8cm'
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

                return True

            finally:
                await browser.close()

    except ImportError:
        print(f"\n[ERROR] 未安装playwright")
        print(f"[INSTALL] 请运行以下命令:")
        print(f"       pip install playwright")
        print(f"       playwright install chromium")
        return False

    except Exception as e:
        print(f"\n[ERROR] PDF生成失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主函数"""
    print("="*60)
    print("  快速PDF生成工具 v2.0（性能优化版）")
    print("="*60)

    # 检查参数
    if len(sys.argv) < 2:
        print("\n使用方法: python generate_pdf_fast.py <HTML文件路径> [PDF文件路径]")
        print("\n示例:")
        print("  python generate_pdf_fast.py \"第十次课0323/报告.html\"")
        print("  python generate_pdf_fast.py \"第十次课0323/报告.html\" \"output.pdf\"")
        print("\n特性:")
        print("  [OK] 后台运行，不会卡死浏览器")
        print("  [OK] 优化的加载速度")
        print("  [OK] 自动等待图表渲染")
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
        # 默认使用同名PDF
        pdf_path = html_path.with_suffix('.pdf')

    # 生成PDF
    success = asyncio.run(convert_html_to_pdf_fast(html_path, pdf_path))

    if success:
        print(f"\n[SUCCESS] PDF文件已保存")
        print(f"[PATH] {pdf_path.absolute()}")
        sys.exit(0)
    else:
        print(f"\n[FAILED] PDF生成失败")
        sys.exit(1)


if __name__ == '__main__':
    main()
