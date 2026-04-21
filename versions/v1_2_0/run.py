#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
v1.2.0 总览报告入口。
"""

import argparse
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
V3_DIR = ROOT_DIR / "v3.0"
if str(V3_DIR) not in sys.path:
    sys.path.insert(0, str(V3_DIR))

from generate_booklet import generate_booklet  # noqa: E402


def detect_data_dir():
    cwd = Path.cwd()
    parent = ROOT_DIR.parent
    for candidate in (cwd, parent):
        if any(candidate.glob("第*次课*")):
            return candidate
    return cwd


def load_latest_jsons(data_dir):
    all_data = []
    for lesson_dir in sorted(data_dir.glob("第*次课*")):
        if not lesson_dir.is_dir():
            continue
        jsons = sorted(lesson_dir.glob("ICAS_v3_data_*.json"))
        if not jsons:
            continue
        with open(jsons[-1], "r", encoding="utf-8") as f:
            all_data.append(json.load(f))
    return all_data


def main():
    parser = argparse.ArgumentParser(description="ICAS v1.2.0 总览报告")
    parser.add_argument("data_dir", nargs="?", help="课次数据目录")
    parser.add_argument("--school", default="濮东小学", help="学校名称")
    parser.add_argument("--output", help="输出 HTML 路径")
    args = parser.parse_args()

    data_dir = Path(args.data_dir) if args.data_dir else detect_data_dir()
    lessons_data = load_latest_jsons(data_dir)
    if not lessons_data:
        raise SystemExit(f"未在 {data_dir} 找到 ICAS_v3_data_*.json")

    output = Path(args.output) if args.output else data_dir / f"{args.school}_AI课堂诊断报告册.html"
    print(f"加载 {len(lessons_data)} 次课数据")
    generate_booklet(lessons_data, output, args.school)


if __name__ == "__main__":
    main()
