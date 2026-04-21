#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ICAS 数据回填工具
将已有的分析缓存结果按学校/教师/课次维度写入数据仓库。

用法:
  python backfill_lessons.py

交互式输入每次课的元数据（学校/教师/日期/学科/年级），
自动从 icas_cache.db 读取已有分析结果，提取指标写入数据仓库。
"""

import sys
import os
import json
import sqlite3
from pathlib import Path

if sys.platform == 'win32':
    os.system('chcp 65001 > nul 2>&1')

sys.path.insert(0, str(Path(__file__).parent))

from icas_warehouse import (
    save_lesson, list_schools, list_teachers,
    get_growth_data, print_warehouse_status
)

DB_PATH = Path(__file__).parent / "icas_cache.db"
LESSONS_ROOT = Path(__file__).parent.parent  # 上一级 = 1濮东-课堂录音


def get_cache_data():
    """读取所有缓存的分析结果"""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        core_rows = conn.execute(
            "SELECT cache_key, folder_name, full_data FROM core_cache"
        ).fetchall()
        ext_rows = conn.execute(
            "SELECT cache_key, folder_name, extended_data FROM extended_cache"
        ).fetchall()
        return {
            "core": {r["folder_name"]: {"key": r["cache_key"], "data": json.loads(r["full_data"])} for r in core_rows},
            "extended": {r["folder_name"]: {"key": r["cache_key"], "data": json.loads(r["extended_data"])} for r in ext_rows},
        }
    finally:
        conn.close()


def scan_lesson_folders():
    """扫描所有课次文件夹"""
    folders = []
    if LESSONS_ROOT.exists():
        for d in sorted(LESSONS_ROOT.iterdir()):
            if d.is_dir() and ("次课" in d.name or "第一次" in d.name):
                folders.append(d)
    return folders


def input_with_default(prompt: str, default: str = "") -> str:
    """带默认值的输入"""
    if default:
        result = input(f"{prompt} [{default}]: ").strip()
        return result if result else default
    return input(f"{prompt}: ").strip()


def main():
    print("\n" + "=" * 50)
    print("[ICAS] 数据仓库回填工具".center(50))
    print("=" * 50)

    # 1. 检查缓存
    cache = get_cache_data()
    core_folders = set(cache["core"].keys())
    ext_folders = set(cache["extended"].keys())

    print(f"\n[缓存状态]")
    print(f"  核心分析缓存: {len(core_folders)} 条 ({', '.join(core_folders) if core_folders else '空'})")
    print(f"  扩展分析缓存: {len(ext_folders)} 条 ({', '.join(ext_folders) if ext_folders else '空'})")

    # 2. 扫描课次文件夹
    folders = scan_lesson_folders()
    print(f"\n[课次文件夹] 找到 {len(folders)} 个:")
    for f in folders:
        status = "✓ 已缓存" if f.name in core_folders else "✗ 未缓存"
        print(f"  {status}  {f.name}")

    # 3. 默认学校名
    default_school = "濮东小学"

    # 4. 交互式输入每次课的元数据
    print(f"\n{'─' * 50}")
    print("请为每次课输入元数据（直接回车使用默认值）")
    print(f"{'─' * 50}")

    entries = []
    for folder in folders:
        folder_name = folder.name

        # 如果没有缓存，跳过
        if folder_name not in core_folders:
            print(f"\n[跳过] {folder_name} — 无分析缓存，请先运行 auto_analyze_simple.py")
            continue

        print(f"\n── {folder_name} ──")

        teacher = input_with_default("  授课教师", "")
        if not teacher:
            print("  [跳过] 未输入教师名")
            continue

        date_str = input_with_default("  授课日期(YYYY-MM-DD)", "")
        subject = input_with_default("  学科", "")
        grade = input_with_default("  年级", "")

        entries.append({
            "folder_name": folder_name,
            "teacher": teacher,
            "date": date_str or None,
            "subject": subject or None,
            "grade": grade or None,
            "school": default_school,
        })

    if not entries:
        print("\n[结束] 没有可回填的数据")
        return

    # 5. 批量写入
    print(f"\n{'─' * 50}")
    print(f"准备写入 {len(entries)} 条课次记录:")
    for e in entries:
        print(f"  {e['teacher']} | {e['subject']} | {e['date']} | {e['folder_name']}")

    confirm = input("\n确认写入？(y/N): ").strip().lower()
    if confirm != 'y':
        print("[取消]")
        return

    success_count = 0
    for e in entries:
        core_info = cache["core"].get(e["folder_name"])
        ext_info = cache["extended"].get(e["folder_name"])

        core_data = core_info["data"] if core_info else None
        ext_data = ext_info["data"] if ext_info else None

        ok = save_lesson(
            school_name=e["school"],
            teacher_name=e["teacher"],
            folder_name=e["folder_name"],
            lesson_date=e["date"],
            subject=e["subject"],
            grade=e["grade"],
            core_data=core_data,
            ext_data=ext_data,
            core_cache_key=core_info["key"] if core_info else None,
            extended_cache_key=ext_info["key"] if ext_info else None,
        )
        if ok:
            success_count += 1
            print(f"  ✓ {e['folder_name']} → {e['teacher']}")
        else:
            print(f"  ✗ {e['folder_name']} 写入失败")

    # 6. 结果
    print(f"\n{'=' * 50}")
    print(f"[完成] 成功写入 {success_count}/{len(entries)} 条".center(50))
    print(f"{'=' * 50}")

    print_warehouse_status()


if __name__ == "__main__":
    main()
