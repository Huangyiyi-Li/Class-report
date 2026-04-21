# -*- coding: utf-8 -*-
"""
ICAS v3.0 命令行工具
v2 兼容 + v3 学科增强 + 教师分层 + 三视角报告

用法：
    # v3 增强模式（指定学科）
    python auto_analyze_v3.py "目录路径" --subject 语文

    # v3 完整参数
    python auto_analyze_v3.py "目录路径" --subject 数学 --lesson-type 新课 --teacher "张老师" --grade "三" --experience 5

    # v2 兼容模式（不传 subject）
    python auto_analyze_v3.py "目录路径"
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

# 路径设置
V3_DIR = Path(__file__).resolve().parent
PARENT_DIR = V3_DIR.parent
SRC_DIR = PARENT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
if str(PARENT_DIR) not in sys.path:
    sys.path.insert(0, str(PARENT_DIR))
if str(V3_DIR) not in sys.path:
    sys.path.insert(0, str(V3_DIR))

# v2 模块
from icas_core import analyze_classroom, read_excel_transcription, read_word_document
from icas_extended import analyze_extended
from icas_cache import (
    get_cached_core, save_cached_core,
    get_cached_extended, save_cached_extended,
    make_cache_key,
)

# v3 模块
from icas_subject_engine import (
    analyze_with_subject,
    load_subject_profile,
    load_lesson_type_config,
    list_available_subjects,
    list_available_lesson_types,
)
from icas_teacher_tier import (
    classify_static,
    classify_by_score,
    generate_tiered_advice,
)
from icas_report_v3 import generate_v3_report


def find_transcription(folder_path):
    """在文件夹中查找转录文件"""
    folder = Path(folder_path)
    if not folder.exists():
        raise FileNotFoundError(f"目录不存在: {folder}")

    # 优先查找 txt（最可靠，不会有格式问题）
    for f in folder.glob("*.txt"):
        if any(kw in f.name.lower() for kw in ["transcript", "转录", "逐字稿"]):
            return str(f), "text"

    # 其次查找 Word docx
    for f in folder.glob("*.docx"):
        if any(kw in f.name for kw in ["逐字稿", "转录", "transcript"]):
            return str(f), "word"

    # 再次查找 Excel（可能有 processed_text 列）
    for ext in ["*.xlsx", "*.xls"]:
        for f in folder.glob(ext):
            return str(f), "excel"

    # fallback: 任意 docx
    for f in folder.glob("*.docx"):
        return str(f), "word"

    # fallback: 任意 txt
    for f in folder.glob("*.txt"):
        return str(f), "text"

    raise FileNotFoundError(f"未找到转录文件: {folder}")


def find_teaching_design(folder_path):
    """在文件夹中查找教学设计文件"""
    folder = Path(folder_path)
    for f in folder.glob("*.docx"):
        if any(kw in f.name for kw in ["教学设计", "教案", "lesson_plan"]):
            return str(f)
    for f in folder.glob("*.txt"):
        if any(kw in f.name for kw in ["教学设计", "教案", "lesson_plan"]):
            return str(f)
    return None


def run_analysis(folder_path, subject=None, lesson_type=None,
                 teacher=None, grade=None, experience=None,
                 audience="teacher", school=None, output_dir=None):
    """
    执行完整分析流程

    v2 兼容：subject 为 None 时走纯 v2 流程
    v3 增强：subject 不为 None 时走 v2 + v3 流程
    """
    folder = Path(folder_path)
    folder_name = folder.name

    print(f"\n{'='*60}")
    print(f"ICAS v3.0 课堂分析")
    print(f"{'='*60}")
    print(f"目录: {folder}")
    if subject:
        print(f"学科: {subject}")
    if lesson_type:
        print(f"课型: {lesson_type}")
    if teacher:
        print(f"教师: {teacher}")
    print(f"{'='*60}\n")

    # ---- Step 1: 读取转录文本 ----
    print("[Step 1/5] 读取转录文本...")
    trans_file, file_type = find_transcription(folder_path)

    if file_type == "excel":
        transcription = read_excel_transcription(trans_file)
    elif file_type == "word":
        transcription = read_word_document(trans_file)
    else:
        with open(trans_file, "r", encoding="utf-8") as f:
            transcription = f.read()

    print(f"  转录文本长度: {len(transcription)} 字")

    # ---- Step 2: 读取教学设计（可选） ----
    teaching_design = None
    design_file = find_teaching_design(folder_path)
    if design_file:
        print(f"[Step 2/5] 读取教学设计: {Path(design_file).name}")
        if design_file.endswith(".docx"):
            teaching_design = read_word_document(design_file)
        else:
            with open(design_file, "r", encoding="utf-8") as f:
                teaching_design = f.read()
    else:
        print("[Step 2/5] 未找到教学设计文件（可选）")

    # ---- Step 3: v2 基础分析 ----
    print("[Step 3/5] 执行 v2 基础分析...")
    cached_core = get_cached_core(transcription, teaching_design or "")
    if cached_core is None:
        print("  缓存未命中，调用 AI 分析...")
        core_data = analyze_classroom(transcription, teaching_design)
        cache_key = make_cache_key(transcription, teaching_design or "")
        save_cached_core(cache_key, folder_name, transcription, teaching_design or "",
                         core_data, 0)
    else:
        core_data = cached_core[0]  # (data_dict, meta_dict)
        print("  命中缓存，复用已有分析")

    # v2 扩展分析
    ext_data = None
    try:
        cached_ext = get_cached_extended(transcription)
        if cached_ext is None:
            print("  执行扩展分析...")
            ext_data = analyze_extended(transcription)
            cache_key = make_cache_key(transcription, "")
            save_cached_extended(cache_key, folder_name, transcription, ext_data, 0)
        else:
            ext_data = cached_ext[0]  # (data_dict, meta_dict)
            print("  扩展分析命中缓存")
    except Exception as e:
        print(f"  扩展分析跳过: {e}")

    # ---- Step 4: v3 学科增强（如果指定了学科） ----
    v3_data = None
    if subject:
        print(f"[Step 4/5] 执行 v3 学科增强分析 ({subject})...")
        v3_data = analyze_with_subject(
            transcription_text=transcription,
            subject=subject,
            lesson_type=lesson_type,
            base_data=core_data,
            teaching_design_text=teaching_design,
        )
    else:
        print("[Step 4/5] 未指定学科，跳过 v3 增强")

    # ---- Step 4.5: 教师分层 ----
    tier_result = None
    if core_data and core_data.get("deep", {}).get("radar_scores"):
        print("[Step 4.5/5] 教师分层...")
        radar_scores = core_data["deep"]["radar_scores"]

        # 学科维度分数（如果有）
        subject_dim_scores = None
        if v3_data and v3_data.get("subject_dimensions"):
            dims = v3_data["subject_dimensions"].get("subject_dimensions", [])
            subject_dim_scores = [d.get("score", 0) for d in dims if "score" in d]

        tier_result = classify_by_score(radar_scores, subject_dim_scores)

        # 静态分层
        static_info = classify_static(subject=subject, grade=grade, experience=experience)
        tier_result["static_info"] = static_info

        print(f"  分层结果: {tier_result['tier_icon']} {tier_result['tier_label']} ({tier_result['composite_score']}分)")
    else:
        print("[Step 4.5/5] 数据不足，跳过教师分层")

    # ---- Step 5: 生成报告 ----
    print("[Step 5/5] 生成报告...")

    # 确定输出目录
    if output_dir:
        out_dir = Path(output_dir)
    else:
        out_dir = folder
    out_dir.mkdir(parents=True, exist_ok=True)

    # 生成 v3 报告（如果指定了学科）
    if subject:
        profile = load_subject_profile(subject)
        lt_config = load_lesson_type_config(lesson_type) if lesson_type else None

        html = generate_v3_report(
            core_data=core_data,
            ext_data=ext_data,
            v3_data=v3_data,
            tier_result=tier_result,
            subject_profile=profile,
            lesson_type_config=lt_config,
            audience=audience,
            teacher_name=teacher or folder_name,
            school_name=school or "",
        )

        timestamp = time.strftime("%Y%m%d_%H%M")
        report_file = out_dir / f"ICAS_v3_{subject}_{timestamp}.html"
        with open(report_file, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"\n{'='*60}")
        print(f"✅ v3 报告已生成: {report_file}")
        print(f"{'='*60}")
    else:
        # v2 兼容模式：生成原始报告
        from icas_report_extended import generate_extended_html
        html = generate_extended_html(core_data, ext_data, teaching_design)
        timestamp = time.strftime("%Y%m%d_%H%M")
        report_file = out_dir / f"ICAS_Report_{timestamp}.html"
        with open(report_file, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"\n{'='*60}")
        print(f"✅ v2 报告已生成: {report_file}")
        print(f"{'='*60}")

    # 保存 JSON 数据（供纵向追踪使用）
    json_data = {
        "folder_name": folder_name,
        "subject": subject,
        "lesson_type": lesson_type,
        "teacher": teacher,
        "grade": grade,
        "experience": experience,
        "school": school,
        "timestamp": time.strftime("%Y-%m-%d %H:%M"),
        "core_data": core_data,
        "ext_data": ext_data,
        "v3_data": {
            "subject": v3_data.get("subject") if v3_data else None,
            "subject_dimensions": v3_data.get("subject_dimensions") if v3_data else None,
            "subject_report": v3_data.get("subject_report") if v3_data else None,
        } if v3_data else None,
        "tier_result": tier_result,
    }
    json_file = out_dir / f"ICAS_v3_data_{time.strftime('%Y%m%d_%H%M')}.json"
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(json_data, f, ensure_ascii=False, indent=2)
    print(f"📊 分析数据已保存: {json_file}")

    return json_data


# ==========================================
# CLI 入口
# ==========================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ICAS v3.0 课堂分析工具")
    parser.add_argument("folder", nargs="?", help="课程文件夹路径")
    parser.add_argument("--subject", "-s", help="学科（语文/数学/英语/物理/化学/生物/政治/历史/地理）")
    parser.add_argument("--lesson-type", "-lt", help="课型（新课/复习课/讲题课）")
    parser.add_argument("--teacher", "-t", help="教师姓名")
    parser.add_argument("--grade", "-g", help="年级")
    parser.add_argument("--experience", "-e", type=int, help="教龄（年）")
    parser.add_argument("--audience", "-a", default="teacher",
                        choices=["teacher", "researcher", "principal"],
                        help="报告受众视角（默认: teacher）")
    parser.add_argument("--school", help="学校名称")
    parser.add_argument("--output", "-o", help="报告输出目录")
    parser.add_argument("--list-subjects", action="store_true", help="列出可用学科")
    parser.add_argument("--list-lesson-types", action="store_true", help="列出可用课型")

    args = parser.parse_args()

    if args.list_subjects:
        print("可用学科:", ", ".join(list_available_subjects()))
    elif args.list_lesson_types:
        print("可用课型:", ", ".join(list_available_lesson_types()))
    else:
        if not args.folder:
            parser.error("未提供课程文件夹路径")
        run_analysis(
            folder_path=args.folder,
            subject=args.subject,
            lesson_type=args.lesson_type,
            teacher=args.teacher,
            grade=args.grade,
            experience=args.experience,
            audience=args.audience,
            school=args.school,
            output_dir=args.output,
        )
