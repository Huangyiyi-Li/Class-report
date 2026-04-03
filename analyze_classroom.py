#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ICAS 课堂录音分析命令行工具
一键自动化分析课堂录音,生成专业诊断报告
"""

import argparse
import sys
import time
from pathlib import Path
from icas_core import (
    analyze_classroom,
    generate_ultimate_html,
    read_excel_transcription,
    read_word_document
)


def main():
    parser = argparse.ArgumentParser(
        description='ICAS 课堂录音分析 - 自动化AI诊断工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  # 分析文本文件中的录音转录
  python analyze_classroom.py -t transcript.txt

  # 分析Excel文件(读取F列)和Word教案
  python analyze_classroom.py -e recording.xlsx -d lesson_plan.docx

  # 指定输出HTML文件名
  python analyze_classroom.py -t transcript.txt -o report.html

  # 混合输入:Excel录音 + 文本教案
  python analyze_classroom.py -e recording.xlsx -d design.txt
        """
    )

    # 录音输入参数(互斥)
    transcript_group = parser.add_mutually_exclusive_group(required=True)
    transcript_group.add_argument(
        '-t', '--transcript',
        type=str,
        help='课堂录音转录文本文件路径 (.txt)'
    )
    transcript_group.add_argument(
        '-e', '--excel',
        type=str,
        help='课堂录音Excel文件路径 (读取F列, .xlsx/.xls)'
    )

    # 教案输入参数(可选)
    design_group = parser.add_mutually_exclusive_group()
    design_group.add_argument(
        '-d', '--design',
        type=str,
        help='教学设计/教案文件路径 (.docx/.txt)'
    )

    # 输出参数
    parser.add_argument(
        '-o', '--output',
        type=str,
        default=None,
        help='输出HTML文件路径 (默认: ICAS_Report_YYYYMMDD_HHMM.html)'
    )

    parser.add_argument(
        '--no-browser',
        action='store_true',
        help='不在浏览器中自动打开报告'
    )

    args = parser.parse_args()

    # ================================
    # 1. 读取录音转录文本
    # ================================
    print("\n" + "="*60)
    print("🚀 ICAS 课堂录音分析系统".center(60))
    print("="*60 + "\n")

    transcription_text = ""
    try:
        if args.transcript:
            print(f"📂 正在读取录音转录文件: {args.transcript}")
            transcript_path = Path(args.transcript)
            if not transcript_path.exists():
                print(f"❌ 错误: 文件不存在 - {args.transcript}")
                sys.exit(1)

            with open(transcript_path, 'r', encoding='utf-8') as f:
                transcription_text = f.read()
            print(f"✅ 成功读取 {len(transcription_text)} 个字符")

        elif args.excel:
            print(f"📂 正在读取Excel文件: {args.excel}")
            excel_path = Path(args.excel)
            if not excel_path.exists():
                print(f"❌ 错误: 文件不存在 - {args.excel}")
                sys.exit(1)

            transcription_text = read_excel_transcription(excel_path)
            print(f"✅ 成功从F列读取 {len(transcription_text)} 个字符")

    except Exception as e:
        print(f"❌ 读取录音文件失败: {e}")
        sys.exit(1)

    if not transcription_text.strip():
        print("❌ 错误: 录音转录文本为空")
        sys.exit(1)

    # ================================
    # 2. 读取教学设计(可选)
    # ================================
    teaching_design_text = None
    if args.design:
        try:
            print(f"\n📂 正在读取教学设计文件: {args.design}")
            design_path = Path(args.design)
            if not design_path.exists():
                print(f"⚠️  警告: 教学设计文件不存在 - {args.design}")
                print("   将继续进行无教学设计的分析...")
            else:
                # 根据文件扩展名选择读取方式
                if design_path.suffix.lower() in ['.docx', '.doc']:
                    teaching_design_text = read_word_document(design_path)
                else:
                    # 默认按文本文件读取
                    with open(design_path, 'r', encoding='utf-8') as f:
                        teaching_design_text = f.read()

                print(f"✅ 成功读取教学设计 {len(teaching_design_text)} 个字符")
        except Exception as e:
            print(f"⚠️  读取教学设计失败: {e}")
            print("   将继续进行无教学设计的分析...")
            teaching_design_text = None
    else:
        print("\n📋 未提供教学设计,将进行常规分析")

    # ================================
    # 3. 执行AI分析
    # ================================
    print("\n" + "⏳"*30)
    print("开始AI深度分析...".center(60))
    print("⏳"*30 + "\n")

    start_time = time.time()

    try:
        report_data = analyze_classroom(
            transcription_text=transcription_text,
            teaching_design_text=teaching_design_text
        )
    except Exception as e:
        print(f"\n❌ 分析过程发生错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    elapsed_time = time.time() - start_time
    print(f"\n⏱️  分析完成! 耗时: {elapsed_time:.2f} 秒")

    # ================================
    # 4. 生成HTML报告
    # ================================
    print("\n📄 正在生成HTML报告...")

    try:
        html_content = generate_ultimate_html(
            full_data=report_data,
            teaching_design=teaching_design_text
        )
    except Exception as e:
        print(f"❌ 生成HTML报告失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # ================================
    # 5. 保存文件
    # ================================
    # 确定输出文件名
    if args.output:
        output_path = Path(args.output)
    else:
        timestamp = time.strftime('%Y%m%d_%H%M')
        output_path = Path(f"ICAS_Report_{timestamp}.html")

    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        print(f"✅ 报告已保存: {output_path.absolute()}")
    except Exception as e:
        print(f"❌ 保存文件失败: {e}")
        sys.exit(1)

    # ================================
    # 6. 自动打开浏览器(可选)
    # ================================
    if not args.no_browser:
        print("\n🌐 正在打开浏览器...")
        try:
            import webbrowser
            webbrowser.open(f'file://{output_path.absolute()}')
            print("✅ 已在浏览器中打开报告")
        except Exception as e:
            print(f"⚠️  无法自动打开浏览器: {e}")
            print(f"   请手动打开: {output_path.absolute()}")

    # ================================
    # 完成
    # ================================
    print("\n" + "="*60)
    print("✨ 分析完成!".center(60))
    print("="*60 + "\n")

    print("💡 提示:")
    print("   - 在浏览器中按 Ctrl+P 可将报告另存为PDF")
    print("   - HTML报告包含完整的交互式图表")
    print("   - 所有数据已自动保存\n")


if __name__ == '__main__':
    main()
