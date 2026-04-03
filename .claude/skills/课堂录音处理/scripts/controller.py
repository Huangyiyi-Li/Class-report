#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
课堂录音处理 - 统一控制入口
整合AI分析和音频处理两大功能
"""

import os
import sys
import argparse
import subprocess
from pathlib import Path

# 设置UTF-8输出编码
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


def print_banner():
    """打印横幅"""
    print("\n" + "=" * 60)
    print("  [ICAS] 课堂录音处理系统 v2.0")
    print("=" * 60)


def scan_course_folder(course_path):
    """扫描课程文件夹，判断可用功能"""
    print(f"\n[扫描] 文件夹: {course_path}")
    print("-" * 60)

    course_path = Path(course_path)
    if not course_path.exists():
        print(f"  ✗ 文件夹不存在")
        return None

    # 查找Excel文件
    excel_files = list(course_path.glob("*.xlsx")) + list(course_path.glob("*.xls"))
    if not excel_files:
        print(f"  ✗ 未找到Excel文件")
        return None

    excel_file = excel_files[0]
    print(f"  [Excel] {excel_file.name}")

    # 读取Excel检查列
    try:
        import pandas as pd
        df = pd.read_excel(excel_file)

        has_f_column = 'F' in df.columns or len(df.columns) >= 6
        has_file_path = 'file_path' in df.columns
        has_segment_index = 'segment_index' in df.columns

        # 检查是否有实际内容
        has_transcript = False
        if has_f_column:
            f_col = df.iloc[:, 5] if len(df.columns) >= 6 else df['F']
            has_transcript = f_col.notna().any() and f_col.str.len().sum() > 100

        has_audio_links = has_file_path and has_segment_index
        if has_audio_links:
            has_audio_links = df['file_path'].notna().any()

        features = {
            'excel_file': str(excel_file),
            'has_transcript': has_transcript,
            'has_audio_links': has_audio_links,
            'has_lesson_plan': False
        }

        # 检查教案
        docx_files = list(course_path.glob("*.docx")) + list(course_path.glob("*.doc"))
        if docx_files:
            features['has_lesson_plan'] = True
            features['lesson_plan_file'] = str(docx_files[0])
            print(f"  [教案] {docx_files[0].name}")

        # 显示可用功能
        print(f"\n[功能检测]")
        if has_transcript:
            print(f"  ✓ AI教学分析 (F列有转录文本)")
        if has_audio_links:
            print(f"  ✓ 音频处理 (有音频链接)")
        if features['has_lesson_plan']:
            print(f"  ✓ 教案对比")

        return features

    except Exception as e:
        print(f"  ✗ 读取Excel失败: {e}")
        return None


def run_ai_analysis(course_path, features):
    """运行AI分析"""
    print("\n" + "=" * 60)
    print("  [AI] 开始教学分析...")
    print("=" * 60)

    try:
        script_path = Path(__file__).parent / "auto_analyze_simple.py"
        result = subprocess.run(
            [sys.executable, str(script_path), course_path],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='ignore'
        )

        print(result.stdout)
        if result.stderr:
            print(result.stderr)

        return result.returncode == 0

    except Exception as e:
        print(f"\n✗ AI分析失败: {e}")
        return False


def run_audio_processing(course_path, features):
    """运行音频处理"""
    print("\n" + "=" * 60)
    print("  [音频] 开始处理音频...")
    print("=" * 60)

    try:
        # 需要先修改audio_processor.py的配置
        script_path = Path(__file__).parent / "audio_processor.py"
        excel_file = features['excel_file']
        course_name = Path(course_path).name

        # 读取脚本内容
        with open(script_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # 临时修改配置
        import re
        content = re.sub(
            r'EXCEL_FILE = ".*?"',
            f'EXCEL_FILE = "{course_name}/{Path(excel_file).name}"',
            content
        )
        content = re.sub(
            r'DOWNLOAD_DIR = ".*?"',
            f'DOWNLOAD_DIR = "{course_name}/downloads"',
            content
        )
        content = re.sub(
            r'CONVERTED_DIR = ".*?"',
            f'CONVERTED_DIR = "{course_name}/converted"',
            content
        )

        # 从Excel提取时间范围（假设文件名包含时间）
        output_name = course_name.replace("课", "").replace("次", "")
        content = re.sub(
            r'OUTPUT_FILE = ".*?"',
            f'OUTPUT_FILE = "{course_name}/{output_name}.mp3"',
            content
        )

        # 写入临时脚本
        temp_script = script_path.parent / "audio_processor_temp.py"
        with open(temp_script, 'w', encoding='utf-8') as f:
            f.write(content)

        # 运行脚本
        result = subprocess.run(
            [sys.executable, str(temp_script)],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='ignore'
        )

        print(result.stdout)
        if result.stderr:
            print(result.stderr)

        # 清理临时脚本
        try:
            temp_script.unlink()
        except:
            pass

        return result.returncode == 0

    except Exception as e:
        print(f"\n✗ 音频处理失败: {e}")
        return False


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='课堂录音处理系统')
    parser.add_argument('--course', help='课程文件夹路径')
    parser.add_argument('--mode', choices=['analyze', 'audio', 'full', 'auto'],
                       default='auto', help='处理模式')
    parser.add_argument('--no-open', action='store_true',
                       help='不自动打开浏览器')

    args = parser.parse_args()

    print_banner()

    # 获取课程路径
    if args.course:
        course_path = args.course
    else:
        # 默认查找第一个课程文件夹
        course_folders = [d for d in Path('.').iterdir()
                         if d.is_dir() and '课' in d.name]
        if not course_folders:
            print("\n✗ 未找到课程文件夹")
            print("\n提示：请使用 --course 指定文件夹")
            print("例如：python controller.py --course \"第七次课0318\"")
            return 1
        course_path = str(course_folders[0])

    # 扫描文件夹
    features = scan_course_folder(course_path)
    if not features:
        print("\n✗ 无法处理该文件夹")
        return 1

    # 确定处理模式
    mode = args.mode

    if mode == 'auto':
        # 自动判断模式
        if features['has_transcript'] and features['has_audio_links']:
            mode = 'full'
        elif features['has_transcript']:
            mode = 'analyze'
        elif features['has_audio_links']:
            mode = 'audio'
        else:
            print("\n✗ 未找到可处理的内容")
            return 1

    print(f"\n[模式] {mode.upper()}")

    # 执行处理
    results = {}

    if mode in ['analyze', 'full']:
        results['ai_analysis'] = run_ai_analysis(course_path, features)

    if mode in ['audio', 'full']:
        results['audio_processing'] = run_audio_processing(course_path, features)

    # 显示结果
    print("\n" + "=" * 60)
    print("  [完成] 处理结果")
    print("=" * 60)

    for task, success in results.items():
        status = "✓ 成功" if success else "✗ 失败"
        task_name = "AI分析" if task == 'ai_analysis' else "音频处理"
        print(f"  {task_name}: {status}")

    print("\n[位置] " + str(Path(course_path).resolve()))

    # 打开浏览器（如果有HTML报告）
    if not args.no_open and results.get('ai_analysis'):
        html_files = list(Path(course_path).glob("*_分析报告_*.html"))
        if html_files:
            import webbrowser
            webbrowser.open(f"file:///{html_files[0].absolute()}")

    return 0 if all(results.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
