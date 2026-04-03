#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ICAS 课堂录音分析 - 自动生成HTML和PDF
使用Playwright自动生成PDF报告
"""

import sys
import os
import time
import asyncio
import argparse
import webbrowser
from pathlib import Path

# 设置Windows控制台编码为UTF-8
if sys.platform == 'win32':
    os.system('chcp 65001 > nul 2>&1')

from icas_core import (
    analyze_classroom,
    read_excel_transcription,
    read_word_document
)
from icas_extended import analyze_extended
from icas_report_extended import generate_combined_html
from icas_cache import (
    make_cache_key, make_extended_cache_key,
    get_cached_core, save_cached_core,
    get_cached_extended, save_cached_extended,
    print_cache_status, clear_cache
)


def scan_folder(folder_path):
    """自动扫描文件夹,识别录音文件和教案文件"""
    folder = Path(folder_path)

    if not folder.exists():
        raise FileNotFoundError(f"文件夹不存在: {folder_path}")

    transcript_extensions = ['.xlsx', '.xls', '.txt']
    # 优先使用.docx，最后才用.doc
    design_extensions_priority = ['.docx', '.txt', '.doc']

    transcript_file = None
    design_file = None

    print(f"\n[扫描] 文件夹: {folder.name}")
    print("-" * 50)

    for file in folder.iterdir():
        if file.is_file():
            ext = file.suffix.lower()

            # 查找录音文件
            if ext in transcript_extensions and not transcript_file:
                transcript_file = file
                print(f"  [录音] {file.name}")

            # 跳过临时文件
            if file.name.startswith('~$'):
                continue

    # 优先查找.docx文件，如果没有再查找其他格式
    for ext in design_extensions_priority:
        for file in folder.iterdir():
            if file.is_file() and not file.name.startswith('~$'):
                if file.suffix.lower() == ext:
                    # 避免txt文件重复
                    if not (transcript_file and file == transcript_file):
                        design_file = file
                        print(f"  [教案] {file.name}")
                        break
        if design_file:
            break

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


async def convert_html_to_pdf(html_path, pdf_path):
    """使用Playwright将HTML转换为PDF"""
    try:
        from playwright.async_api import async_playwright

        print(f"[PDF] 正在生成PDF...")

        async with async_playwright() as p:
            browser = await p.chromium.launch()
            try:
                page = await browser.new_page()

                # 使用绝对路径并正确编码
                file_url = html_path.absolute().as_uri()
                await page.goto(file_url)
                await page.wait_for_load_state('networkidle')

                await page.pdf(
                    path=str(pdf_path),
                    format='A4',
                    print_background=True,
                    margin={'top': '0.5cm', 'right': '0.5cm', 'bottom': '0.5cm', 'left': '0.5cm'}
                )
                print(f"[PDF] PDF生成成功! [OK]")
                return True
            finally:
                await browser.close()

    except ImportError:
        print(f"[警告] 未安装playwright，跳过PDF生成")
        print(f"[提示] 安装: pip install playwright && playwright install chromium")
        return False
    except Exception as e:
        print(f"[错误] PDF生成失败: {e}")
        return False


def analyze_folder(folder_path, auto_open=True, generate_pdf=True, force=False,
                   school=None, teacher=None, lesson_date=None, subject=None, grade=None):
    """分析指定文件夹"""
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
        try:
            teaching_design_text = read_file_content(design_file)
            print(f"   教案: {len(teaching_design_text)} 字符")
        except Exception as e:
            print(f"   警告: 无法读取教案文件 ({e})")
            print(f"   提示: 将仅分析录音内容")
            teaching_design_text = None

    folder_name = folder.name

    # 3. 核心分析 (带缓存)
    core_key = make_cache_key(transcription_text, teaching_design_text or "")

    if not force:
        cached_core = get_cached_core(transcription_text, teaching_design_text or "")
        if cached_core:
            report_data, meta = cached_core
            print(f"\n[缓存] 核心分析命中! ({meta['created']}, 耗时{meta['duration']:.0f}秒)")
            print(f"   跳过4次AI调用")
        else:
            cached_core = None
    else:
        cached_core = None
        print(f"\n[强制] --force 忽略缓存，重新分析")

    if not cached_core:
        print(f"\n[AI] 缓存未命中，开始深度分析 (4次AI调用)...")
        start_time = time.time()

        report_data = analyze_classroom(
            transcription_text=transcription_text,
            teaching_design_text=teaching_design_text
        )

        elapsed_time = time.time() - start_time
        print(f"   分析完成! 耗时: {elapsed_time:.1f} 秒")

        save_cached_core(core_key, folder_name,
                         transcription_text, teaching_design_text or "",
                         report_data, elapsed_time)
        print(f"   [缓存] 核心分析已保存")

    # 4. 扩展分析 (带缓存)
    ext_key = make_extended_cache_key(transcription_text)

    if not force:
        cached_ext = get_cached_extended(transcription_text)
        if cached_ext:
            ext_data, meta = cached_ext
            print(f"\n[缓存] 扩展分析命中! ({meta['created']}, 耗时{meta['duration']:.0f}秒)")
            print(f"   跳过3次AI调用")
        else:
            cached_ext = None
    else:
        cached_ext = None

    ext_data = None
    if not cached_ext:
        print(f"\n[AI] 扩展缓存未命中，开始扩展分析 (3次AI调用)...")
        try:
            ext_start = time.time()
            ext_data = analyze_extended(transcription_text)
            ext_elapsed = time.time() - ext_start
            print(f"   扩展分析完成! 耗时: {ext_elapsed:.1f} 秒")

            save_cached_extended(ext_key, folder_name, transcription_text,
                                 ext_data, ext_elapsed)
            print(f"   [缓存] 扩展分析已保存")
        except Exception as e:
            print(f"   [!] 扩展分析失败或跳过: {e}")
    else:
        ext_data = cached_ext[0]

    # 5. 生成完整报告
    print(f"\n[生成] 正在组装报告...")
    timestamp = time.strftime('%Y%m%d_%H%M')

    html_filename = f"{folder_name}_分析报告_{timestamp}.html"
    html_path = folder / html_filename

    html_content = generate_combined_html(
        full_data=report_data,
        extended_data=ext_data,
        teaching_design=teaching_design_text,
        folder_name=folder_name
    )

    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(html_content)

    print(f"   HTML报告: {html_filename} [OK]")

    # 6. 生成PDF
    pdf_filename = f"{folder_name}_分析报告_{timestamp}.pdf"
    pdf_path = folder / pdf_filename
    pdf_success = False

    if generate_pdf:
        try:
            # 创建新的事件循环
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            pdf_success = loop.run_until_complete(
                convert_html_to_pdf(html_path, pdf_path)
            )
            loop.close()

            if pdf_success:
                print(f"   PDF报告: {pdf_filename} [OK]")
        except Exception as e:
            print(f"   PDF生成跳过: {e}")

    # 6. 写入数据仓库（如果提供了元数据）
    if teacher:
        try:
            from icas_warehouse import save_lesson
            save_lesson(
                school_name=school or "默认学校",
                teacher_name=teacher,
                folder_name=folder_name,
                lesson_date=lesson_date,
                subject=subject,
                grade=grade,
                core_data=report_data,
                ext_data=ext_data,
                core_cache_key=core_key,
                extended_cache_key=ext_key,
            )
            print(f"   [仓库] 已写入数据仓库 ({teacher}, {school or '默认学校'})")
        except Exception as e:
            print(f"   [仓库] 写入失败: {e}")

    # 7. 自动打开浏览器
    if auto_open:
        print(f"\n[浏览器] 正在打开HTML...")
        webbrowser.open(f'file://{html_path.absolute()}')

    # 完成
    print("\n" + "="*50)
    print("[完成] 分析成功!".center(50))
    print("="*50)
    print(f"\n[位置] {folder.absolute()}")
    print(f"[报告] {html_filename}")
    if pdf_success:
        print(f"[报告] {pdf_filename} [OK]")
    print()

    return True


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='ICAS 课堂分析系统')
    parser.add_argument('folder', nargs='?', help='课堂文件夹路径')
    parser.add_argument('--force', action='store_true', help='强制重新分析，忽略缓存')

    # 元数据参数
    parser.add_argument('--school', help='学校名称 (写入数据仓库)')
    parser.add_argument('--teacher', help='授课教师 (写入数据仓库)')
    parser.add_argument('--date', dest='lesson_date', help='授课日期 YYYY-MM-DD')
    parser.add_argument('--subject', help='学科')
    parser.add_argument('--grade', help='年级')

    # 纵向追踪命令
    parser.add_argument('--growth', metavar='TEACHER_ID', help='生成教师成长追踪报告')
    parser.add_argument('--overview', metavar='SCHOOL_ID', help='生成学校教学概览报告')
    parser.add_argument('--warehouse', action='store_true', help='查看数据仓库状态')

    # 缓存管理
    parser.add_argument('--cache-list', action='store_true', help='列出所有缓存条目')
    parser.add_argument('--cache-clear', nargs='?', const='__all__', metavar='FOLDER',
                        help='清除缓存 (可指定文件夹名，不指定则清除全部)')
    args = parser.parse_args()

    # 数据仓库命令
    if args.warehouse:
        from icas_warehouse import print_warehouse_status
        print_warehouse_status()
        sys.exit(0)

    if args.growth:
        from icas_warehouse import get_growth_data
        from icas_report_growth import generate_growth_html
        import webbrowser

        tid = int(args.growth)
        lessons = get_growth_data(tid)
        if not lessons:
            print(f"\n[错误] 教师 ID={tid} 没有课次数据")
            sys.exit(1)

        teacher_name = lessons[0].get("teacher_name", f"教师{tid}")
        output = Path(__file__).parent / f"成长追踪_{teacher_name}_{time.strftime('%Y%m%d_%H%M')}.html"
        generate_growth_html(teacher_name, lessons, output_path=str(output))
        print(f"\n[报告] {output.name}")
        webbrowser.open(f'file://{output.absolute()}')
        sys.exit(0)

    if args.overview:
        from icas_warehouse import get_school_overview, get_all_lessons_for_report
        from icas_report_growth import generate_school_overview_html
        import webbrowser

        sid = int(args.overview)
        overview = get_school_overview(sid)
        if not overview:
            print(f"\n[错误] 学校 ID={sid} 没有数据")
            sys.exit(1)

        school_name = overview["school"]["name"]
        all_lessons = get_all_lessons_for_report(sid)
        output = Path(__file__).parent / f"学校概览_{school_name}_{time.strftime('%Y%m%d_%H%M')}.html"
        generate_school_overview_html(school_name, overview, all_lessons, output_path=str(output))
        print(f"\n[报告] {output.name}")
        webbrowser.open(f'file://{output.absolute()}')
        sys.exit(0)

    # 缓存管理命令
    if args.cache_list:
        print("\n[缓存] 本地缓存状态:")
        print_cache_status()
        sys.exit(0)

    if args.cache_clear is not None:
        if args.cache_clear == '__all__':
            n = clear_cache()
            print(f"\n[缓存] 已清除全部 {n} 条缓存记录")
        else:
            n = clear_cache(args.cache_clear)
            print(f"\n[缓存] 已清除 '{args.cache_clear}' 的 {n} 条缓存记录")
        sys.exit(0)

    # 正常分析
    if not args.folder:
        parser.print_help()
        sys.exit(1)

    analyze_folder(args.folder, force=args.force,
                   school=args.school, teacher=args.teacher,
                   lesson_date=args.lesson_date, subject=args.subject,
                   grade=args.grade)
