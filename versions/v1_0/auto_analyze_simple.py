#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
ICAS v1.0 单次报告入口。

按历史文档约定，v1.0 的核心脚本名为 `auto_analyze_simple.py`，
核心模块名为 `icas_core.py`。
"""

import argparse
import asyncio
import os
import sys
import time
import webbrowser
from pathlib import Path

from icas_core import (
    analyze_classroom,
    generate_ultimate_html,
    read_excel_transcription,
    read_word_document,
)


def scan_folder(folder_path):
    """自动扫描文件夹，识别录音文件和教案文件。"""
    folder = Path(folder_path)

    if not folder.exists():
        raise FileNotFoundError(f"文件夹不存在: {folder_path}")

    transcript_extensions = [".xlsx", ".xls", ".txt"]
    design_extensions_priority = [".docx", ".txt", ".doc"]

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

    for ext in design_extensions_priority:
        for file in folder.iterdir():
            if file.is_file() and not file.name.startswith("~$"):
                if file.suffix.lower() == ext:
                    if not (transcript_file and file == transcript_file):
                        design_file = file
                        print(f"  [教案] {file.name}")
                        break
        if design_file:
            break

    if not transcript_file:
        raise FileNotFoundError("未找到录音文件")

    return transcript_file, design_file


def read_file_content(file_path):
    """根据文件类型读取内容。"""
    ext = file_path.suffix.lower()

    if ext in [".xlsx", ".xls"]:
        return read_excel_transcription(file_path)
    if ext in [".docx", ".doc"]:
        return read_word_document(file_path)
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()


async def convert_html_to_pdf(html_path, pdf_path):
    """使用 Playwright 生成 PDF。"""
    try:
        from playwright.async_api import async_playwright

        print("[PDF] 正在生成PDF...")

        async with async_playwright() as p:
            browser = await p.chromium.launch()
            try:
                page = await browser.new_page()
                await page.goto(html_path.absolute().as_uri())
                await page.wait_for_load_state("networkidle")
                await page.pdf(
                    path=str(pdf_path),
                    format="A4",
                    print_background=True,
                    margin={"top": "0.5cm", "right": "0.5cm", "bottom": "0.5cm", "left": "0.5cm"},
                )
                print("[PDF] PDF生成成功! [OK]")
                return True
            finally:
                await browser.close()
    except ImportError:
        print("[警告] 未安装playwright，跳过PDF生成")
        print("[提示] 安装: pip install playwright && playwright install chromium")
        return False
    except Exception as e:
        print(f"[错误] PDF生成失败: {e}")
        return False


def analyze_folder(folder_path, auto_open=True, generate_pdf=True):
    """分析指定文件夹并输出 v1.0 单次报告。"""
    folder = Path(folder_path)

    print("\n" + "=" * 50)
    print("[ICAS] v1.0 单次报告".center(50))
    print("=" * 50)

    transcript_file, design_file = scan_folder(folder)

    print("\n[读取] 正在读取文件...")
    transcription_text = read_file_content(transcript_file)
    print(f"   录音: {len(transcription_text)} 字符")

    teaching_design_text = None
    if design_file:
        try:
            teaching_design_text = read_file_content(design_file)
            print(f"   教案: {len(teaching_design_text)} 字符")
        except Exception as e:
            print(f"   警告: 无法读取教案文件 ({e})")
            print("   提示: 将仅分析录音内容")

    print("\n[AI] 开始生成 v1.0 单次报告...")
    start_time = time.time()
    report_data = analyze_classroom(
        transcription_text=transcription_text,
        teaching_design_text=teaching_design_text,
    )
    elapsed = time.time() - start_time
    print(f"   分析完成! 耗时: {elapsed:.1f} 秒")

    timestamp = time.strftime("%Y%m%d_%H%M")
    html_path = folder / f"{folder.name}_分析报告_{timestamp}.html"
    pdf_path = folder / f"{folder.name}_分析报告_{timestamp}.pdf"

    html_content = generate_ultimate_html(report_data, teaching_design=teaching_design_text)
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"[报告] HTML: {html_path.name}")

    pdf_success = False
    if generate_pdf:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            pdf_success = loop.run_until_complete(convert_html_to_pdf(html_path, pdf_path))
        finally:
            loop.close()

    if pdf_success:
        print(f"[报告] PDF: {pdf_path.name}")

    if auto_open:
        webbrowser.open(f"file://{html_path.absolute()}")


def main():
    parser = argparse.ArgumentParser(description="ICAS v1.0 单次报告")
    parser.add_argument("folder", help="课堂文件夹路径")
    parser.add_argument("--no-open", action="store_true", help="不自动打开 HTML")
    parser.add_argument("--no-pdf", action="store_true", help="不生成 PDF")
    args = parser.parse_args()

    if sys.platform == "win32":
        os.system("chcp 65001 > nul 2>&1")

    analyze_folder(
        folder_path=args.folder,
        auto_open=not args.no_open,
        generate_pdf=not args.no_pdf,
    )


if __name__ == "__main__":
    main()
