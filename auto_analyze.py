#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ICAS 课堂录音分析自动化脚本
自动扫描文件夹中的录音和教案,生成PDF报告
"""

import sys
import json
import time
from pathlib import Path
from icas_core import (
    analyze_classroom,
    generate_ultimate_html,
    read_excel_transcription,
    read_word_document
)


def scan_folder(folder_path):
    """
    自动扫描文件夹,识别录音文件和教案文件

    返回: {
        'transcript_file': Path对象,
        'design_file': Path对象或None
    }
    """
    folder = Path(folder_path)

    if not folder.exists():
        raise FileNotFoundError(f"文件夹不存在: {folder_path}")

    if not folder.is_dir():
        raise NotADirectoryError(f"路径不是文件夹: {folder_path}")

    # 支持的文件扩展名
    transcript_extensions = ['.xlsx', '.xls', '.txt']
    design_extensions = ['.docx', '.doc', '.txt']

    transcript_file = None
    design_file = None

    print(f"\n🔍 正在扫描文件夹: {folder.name}")
    print("-" * 60)

    # 遍历文件夹中的文件
    for file in folder.iterdir():
        if file.is_file():
            ext = file.suffix.lower()

            # 识别录音文件(优先级: xlsx > xls > txt)
            if ext in transcript_extensions:
                if transcript_file is None or ext == '.xlsx':
                    transcript_file = file
                    print(f"  📂 发现录音文件: {file.name}")

            # 识别教案文件(优先级: docx > doc > txt)
            elif ext in design_extensions:
                # 避免同一个txt文件既当录音又当教案
                if transcript_file and file == transcript_file:
                    continue

                if design_file is None or ext == '.docx':
                    design_file = file
                    print(f"  📋 发现教案文件: {file.name}")

    print("-" * 60)

    if not transcript_file:
        raise FileNotFoundError(
            f"未找到录音文件!\n"
            f"支持的格式: Excel (.xlsx, .xls) 或 文本 (.txt)\n"
            f"请确保录音文件在文件夹中"
        )

    return {
        'transcript_file': transcript_file,
        'design_file': design_file
    }


def read_file_content(file_path):
    """根据文件类型读取内容"""
    ext = file_path.suffix.lower()

    if ext in ['.xlsx', '.xls']:
        print(f"\n📖 正在读取Excel文件 (F列): {file_path.name}")
        return read_excel_transcription(file_path)

    elif ext in ['.docx', '.doc']:
        print(f"\n📖 正在读取Word文件: {file_path.name}")
        return read_word_document(file_path)

    else:  # .txt 或其他
        print(f"\n📖 正在读取文本文件: {file_path.name}")
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()


def convert_html_to_pdf(html_path, pdf_path):
    """
    将HTML转换为PDF
    使用Playwright的浏览器自动化功能
    """
    print(f"\n🖨️  正在转换为PDF...")

    try:
        # 尝试使用Playwright (如果MCP服务可用)
        # 这里创建一个简单的Python脚本调用Playwright
        import subprocess

        convert_script = f"""
import asyncio
from playwright.async_api import async_playwright

async def convert():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.goto('file:///{html_path.as_posix()}')
        await page.pdf(path='{pdf_path}', format='A4', print_background=True)
        await browser.close()

asyncio.run(convert())
"""

        script_path = html_path.parent / '_temp_convert.py'
        with open(script_path, 'w', encoding='utf-8') as f:
            f.write(convert_script)

        result = subprocess.run(
            [sys.executable, str(script_path)],
            capture_output=True,
            text=True,
            timeout=60
        )

        # 清理临时脚本
        script_path.unlink()

        if result.returncode == 0:
            print(f"✅ PDF已生成: {pdf_path.name}")
            return True
        else:
            print(f"⚠️  自动转PDF失败,可以手动打开HTML打印")
            print(f"   错误信息: {result.stderr}")
            return False

    except ImportError:
        print(f"⚠️  未安装playwright,尝试手动转PDF...")
        print(f"   安装方法: pip install playwright && playwright install chromium")
        return False

    except Exception as e:
        print(f"⚠️  自动转PDF失败: {e}")
        print(f"   HTML文件已保存,可以手动打开后打印为PDF")
        return False


def analyze_folder(folder_path):
    """
    分析指定文件夹中的课堂录音

    工作流程:
    1. 扫描文件夹,识别录音和教案
    2. 读取文件内容
    3. 执行AI分析
    4. 生成HTML报告
    5. 转换为PDF
    6. 保存到原文件夹
    """
    folder = Path(folder_path)

    print("\n" + "="*60)
    print("🚀 ICAS 智能课堂分析".center(60))
    print("="*60)

    # Step 1: 扫描文件夹
    try:
        files = scan_folder(folder)
    except Exception as e:
        print(f"❌ 扫描文件夹失败: {e}")
        return False

    transcript_file = files['transcript_file']
    design_file = files['design_file']

    # Step 2: 读取录音内容
    try:
        transcription_text = read_file_content(transcript_file)
        print(f"✅ 录音内容: {len(transcription_text)} 字符")
    except Exception as e:
        print(f"❌ 读取录音文件失败: {e}")
        return False

    # Step 3: 读取教案内容(如果有)
    teaching_design_text = None
    if design_file:
        try:
            teaching_design_text = read_file_content(design_file)
            print(f"✅ 教案内容: {len(teaching_design_text)} 字符")
        except Exception as e:
            print(f"⚠️  读取教案失败: {e}")
            print(f"   将继续进行无教案的分析")
            teaching_design_text = None
    else:
        print("ℹ️  未找到教案文件,将进行常规分析")

    # Step 4: 执行AI分析
    print("\n" + "⏳"*30)
    print("AI深度分析中...".center(60))
    print("⏳"*30)

    start_time = time.time()

    try:
        report_data = analyze_classroom(
            transcription_text=transcription_text,
            teaching_design_text=teaching_design_text
        )
    except Exception as e:
        print(f"\n❌ AI分析失败: {e}")
        import traceback
        traceback.print_exc()
        return False

    elapsed_time = time.time() - start_time
    print(f"\n⏱️  分析完成! 耗时: {elapsed_time:.2f} 秒")

    # Step 5: 生成HTML报告
    print("\n📄 正在生成报告...")

    timestamp = time.strftime('%Y%m%d_%H%M')
    folder_name = folder.name

    html_filename = f"{folder_name}_分析报告_{timestamp}.html"
    html_path = folder / html_filename

    try:
        html_content = generate_ultimate_html(
            full_data=report_data,
            teaching_design=teaching_design_text
        )

        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)

        print(f"✅ HTML报告: {html_filename}")

    except Exception as e:
        print(f"❌ 生成HTML失败: {e}")
        return False

    # Step 6: 转换为PDF
    pdf_filename = f"{folder_name}_分析报告_{timestamp}.pdf"
    pdf_path = folder / pdf_filename

    convert_success = convert_html_to_pdf(html_path, pdf_path)

    # 完成
    print("\n" + "="*60)
    print("✨ 分析完成!".center(60))
    print("="*60 + "\n")

    print(f"📁 文件夹: {folder.absolute()}")
    print(f"📄 HTML报告: {html_filename}")
    print(f"📕 PDF报告: {pdf_filename} {'✅' if convert_success else '⚠️ (需手动转换)'}")

    if not convert_success:
        print(f"\n💡 提示: 可以手动打开HTML文件,按Ctrl+P打印为PDF")

    print()

    return True


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("使用方法: python auto_analyze.py <文件夹路径>")
        print("示例: python auto_analyze.py ./第一次课")
        sys.exit(1)

    folder_path = sys.argv[1]

    try:
        success = analyze_folder(folder_path)
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ 执行失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
