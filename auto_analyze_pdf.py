#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ICAS 课堂录音分析 - 自动生成PDF版
使用Playwright自动生成HTML和PDF
"""

import sys
import os
import time
import asyncio
from pathlib import Path

# 设置Windows控制台编码为UTF-8
if sys.platform == 'win32':
    os.system('chcp 65001 > nul 2>&1')

from icas_core import (
    analyze_classroom,
    generate_ultimate_html,
    read_excel_transcription,
    read_word_document
)


def scan_folder(folder_path):
    """自动扫描文件夹,识别录音文件和教案文件"""
    folder = Path(folder_path)

    if not folder.exists():
        raise FileNotFoundError(f"文件夹不存在: {folder_path}")

    transcript_extensions = ['.xlsx', '.xls', '.txt']
    design_extensions = ['.docx', '.doc', '.txt']

    transcript_file = None
    design_file = None

    print(f"\n[扫描] 文件夹: {folder.name}")
    print("-" * 50)

    for file in folder.iterdir():
        if file.is_file():
            ext = file.suffix.lower()

            if ext in transcript_extensions and not transcript_file:
                transcript_file = file
                print(f"  [录音] {file.name}")

            elif ext in design_extensions:
                # 避免txt文件重复
                if not (transcript_file and file == transcript_file):
                    if not design_file:
                        design_file = file
                        print(f"  [教案] {file.name}")

    if not transcript_file:
        raise FileNotFoundError("未找到录音文件")

    return {'transcript_file': transcript_file, 'design_file': design_file}


def read_file_content(file_path):
    """根据文件类型读取内容"""
    ext = file_path.suffix.lower()

    if ext in ['.xlsx', '.xls']:
        return read_excel_transcription(file_path)
    elif ext in ['.docx', '.doc']:
        return read_word_document(file_path)
    else:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()


async def convert_html_to_pdf_playwright(html_path, pdf_path):
    """使用Playwright将HTML转换为PDF（优化版）"""
    try:
        from playwright.async_api import async_playwright

        print(f"[PDF] 正在生成PDF文件...")

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
                # 创建页面
                page = await browser.new_page()

                # 加载HTML文件
                await page.goto(f'file:///{html_path.as_posix()}')

                # 等待页面完全加载,包括图表渲染
                await page.wait_for_load_state('networkidle')
                await page.wait_for_timeout(5000)  # 等待5秒确保图表完全渲染

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

    except ImportError:
        print(f"[警告] 未安装playwright，无法自动生成PDF")
        print(f"[提示] 安装方法:")
        print(f"       pip install playwright")
        print(f"       playwright install chromium")
        return False

    except Exception as e:
        print(f"[错误] PDF生成失败: {e}")
        return False


def analyze_folder(folder_path, auto_open=True, generate_pdf=True):
    """分析指定文件夹，生成HTML和PDF"""
    folder = Path(folder_path)

    print("\n" + "="*50)
    print("[ICAS] 课堂分析系统".center(50))
    print("="*50)

    # 1. 扫描文件夹
    files = scan_folder(folder)
    transcript_file = files['transcript_file']
    design_file = files['design_file']

    # 2. 读取内容
    print(f"\n[读取] 正在读取文件...")
    transcription_text = read_file_content(transcript_file)
    print(f"   录音: {len(transcription_text)} 字符")

    teaching_design_text = None
    if design_file:
        teaching_design_text = read_file_content(design_file)
        print(f"   教案: {len(teaching_design_text)} 字符")

    # 3. AI分析
    print(f"\n[AI] 开始深度分析...")
    start_time = time.time()

    report_data = analyze_classroom(
        transcription_text=transcription_text,
        teaching_design_text=teaching_design_text
    )

    elapsed_time = time.time() - start_time
    print(f"   分析完成! 耗时: {elapsed_time:.1f} 秒")

    # 4. 生成报告
    print(f"\n[生成] 正在生成报告...")
    timestamp = time.strftime('%Y%m%d_%H%M')
    folder_name = folder.name

    # HTML文件路径
    html_filename = f"{folder_name}_分析报告_{timestamp}.html"
    html_path = folder / html_filename

    # PDF文件路径
    pdf_filename = f"{folder_name}_分析报告_{timestamp}.pdf"
    pdf_path = folder / pdf_filename

    # 生成HTML内容
    html_content = generate_ultimate_html(
        full_data=report_data,
        teaching_design=teaching_design_text
    )

    # 保存HTML文件
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(html_content)

    print(f"   HTML报告: {html_filename}")

    # 5. 生成PDF
    pdf_success = False
    if generate_pdf:
        try:
            # 尝试使用异步方式生成PDF
            loop = asyncio.get_event_loop()
            pdf_success = loop.run_until_complete(
                convert_html_to_pdf_playwright(html_path, pdf_path)
            )

            if pdf_success:
                print(f"   PDF报告: {pdf_filename}")
        except Exception as e:
            print(f"   PDF生成失败: {e}")

    # 6. 自动打开浏览器
    if auto_open:
        print(f"\n[浏览器] 正在打开...")
        import webbrowser
        webbrowser.open(f'file://{html_path.absolute()}')

        if pdf_success:
            print(f"   提示: HTML和PDF都已生成")
        else:
            print(f"   提示: 在浏览器中按 Ctrl+P 可保存为PDF")

    # 完成
    print("\n" + "="*50)
    print("[完成] 分析成功!".center(50))
    print("="*50)
    print(f"\n[位置] {folder.absolute()}")
    print(f"[报告] {html_filename}")

    if pdf_success:
        print(f"[报告] {pdf_filename}")

    print()

    return True


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("使用方法: python auto_analyze_pdf.py <文件夹路径>")
        print("示例: python auto_analyze_pdf.py ./第一次课")
        sys.exit(1)

    folder_path = sys.argv[1]
    analyze_folder(folder_path)
