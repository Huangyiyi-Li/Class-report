#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
ICAS 版本选择入口。

支持两种方式：
1. `python run_version.py --list` 查看全部版本
2. `python run_version.py` 进入交互式选择
3. `python run_version.py <version-id> [args...]` 直接启动指定版本
"""

import argparse
import json
import shlex
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
MANIFEST_PATH = ROOT_DIR / "versions" / "manifest.json"


def load_manifest():
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def print_versions(entries):
    print("\n可用版本:\n")
    for index, entry in enumerate(entries, start=1):
        print(f"  {index}. {entry['title']} ({entry['id']})")
        print(f"     入口: {entry['script']}")
        print(f"     说明: {entry['description']}")
    print()


def resolve_entry(entries, selector):
    if selector.isdigit():
        index = int(selector) - 1
        if 0 <= index < len(entries):
            return entries[index]
    for entry in entries:
        if entry["id"] == selector:
            return entry
    raise ValueError(f"未找到版本: {selector}")


def build_command(entry, passthrough_args):
    script_path = ROOT_DIR / entry["script"]
    if not script_path.exists():
        raise FileNotFoundError(f"版本入口不存在: {script_path}")

    runner = entry.get("runner", "python")
    if runner == "streamlit":
        return [sys.executable, "-m", "streamlit", "run", str(script_path), *passthrough_args]
    if runner == "python":
        return [sys.executable, str(script_path), *passthrough_args]
    raise ValueError(f"不支持的运行器: {runner}")


def prompt_selection(entries):
    print_versions(entries)
    selector = input("请选择版本编号或 ID: ").strip()
    entry = resolve_entry(entries, selector)
    raw_args = input("如需附加参数，请直接输入；没有可直接回车: ").strip()
    passthrough_args = shlex.split(raw_args, posix=False) if raw_args else []
    return entry, passthrough_args


def main():
    parser = argparse.ArgumentParser(description="ICAS 版本选择器")
    parser.add_argument("version", nargs="?", help="版本编号或版本 ID")
    parser.add_argument("--list", action="store_true", help="列出全部版本")
    args, passthrough_args = parser.parse_known_args()

    entries = load_manifest()

    if args.list:
        print_versions(entries)
        return 0

    if args.version:
        entry = resolve_entry(entries, args.version)
    else:
        entry, passthrough_args = prompt_selection(entries)

    command = build_command(entry, passthrough_args)
    print(f"\n启动版本: {entry['title']} ({entry['id']})")
    print("执行命令:")
    print("  " + " ".join(command))
    print()

    completed = subprocess.run(command, cwd=ROOT_DIR)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
