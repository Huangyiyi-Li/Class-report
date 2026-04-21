# -*- coding: utf-8 -*-
"""
ICAS v3.0 学科感知分析引擎
读取学科配置 + 课型配置 → 生成参数化 Prompt → 执行学科增强版分析

设计原则：
- 零侵入：不修改 icas_core.py / icas_extended.py
- 配置驱动：学科差异 = JSON 配置，不是 N 套 Prompt
- 产品核心：学科增强版 Agent F（特级教师诊断）
"""

import json
import os
import sys
from pathlib import Path

# 父目录导入 v2 模块（现在 v2 模块在 src/ 下）
PARENT_DIR = str(Path(__file__).resolve().parent.parent)
SRC_DIR = str(Path(__file__).resolve().parent.parent / "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)
if PARENT_DIR not in sys.path:
    sys.path.insert(0, PARENT_DIR)

from icas_core import call_volc_agent, clean_json_string

# 配置文件目录
PROFILES_DIR = Path(__file__).resolve().parent / "icas_subject_profiles"


# ==========================================
# 配置加载
# ==========================================

def load_subject_profile(subject_name):
    """加载学科配置"""
    path = PROFILES_DIR / f"{subject_name}.json"
    if not path.exists():
        available = [f.stem for f in PROFILES_DIR.glob("*.json")]
        raise FileNotFoundError(
            f"未找到学科配置 '{subject_name}'。可用学科: {', '.join(available)}"
        )
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_lesson_type_config(lesson_type):
    """加载课型配置"""
    if not lesson_type:
        return None
    path = PROFILES_DIR / "lesson_types" / f"{lesson_type}.json"
    if not path.exists():
        available = [f.stem for f in (PROFILES_DIR / "lesson_types").glob("*.json")]
        raise FileNotFoundError(
            f"未找到课型配置 '{lesson_type}'。可用课型: {', '.join(available)}"
        )
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def list_available_subjects():
    """列出所有可用学科"""
    return sorted([f.stem for f in PROFILES_DIR.glob("*.json")])


def list_available_lesson_types():
    """列出所有可用课型"""
    lt_dir = PROFILES_DIR / "lesson_types"
    if lt_dir.exists():
        return sorted([f.stem for f in lt_dir.glob("*.json")])
    return []


# ==========================================
# Prompt 生成器
# ==========================================

def build_subject_aware_prompt_f(profile, lesson_type_config=None):
    """
    生成学科增强版 Agent F Prompt（产品核心价值点）

    设计理念：
    - 角色设定为该学科的特级教师
    - 评价维度融入学科特有维度
    - 问题诊断嵌入四步法（定位→归因→预判→验证）
    - 常见问题模式作为"专家直觉"注入
    """

    subject = profile["subject"]
    label = profile["label"]
    competencies = "、".join(profile["core_competencies"])
    dimensions_text = "\n".join([
        f"  - {d['name']}：{d['description']}"
        for d in profile["extra_dimensions"]
    ])
    problems_text = "\n".join([
        f"  - 「{k}」：{v}"
        for k, v in profile["problem_patterns"].items()
    ])
    expert_style = profile["expert_advice_style"]

    # 教学流程（按课型选择）
    if lesson_type_config:
        lt = lesson_type_config["lesson_type"]
        lt_label = lesson_type_config["label"]
        flow = " → ".join(lesson_type_config.get("teaching_flow", profile["teaching_flow"].get(lt, [])))
        lt_injection = lesson_type_config.get("prompt_injection", "")
        lt_section = f"""
    **课型信息**：这是一节{lt_label}。
    **该课型理想的教学流程**：{flow}
    **课型评价侧重**：{lt_injection}
    """
    else:
        lt_section = ""

    prompt = f"""{expert_style}

你现在正在分析一堂{label}课。请基于以下学科框架进行深度诊断：

**{label}核心素养**：{competencies}

**{label}特有评价维度**：
{dimensions_text}

**{label}常见教学问题模式**（请对照检查是否存在）：
{problems_text}
{lt_section}
**报告结构要求**（严格按此结构输出）：

1. **学科宏观诊断**（约200字）：
   - 从{label}学科视角概括本节课的整体质量
   - 是否体现了{label}核心素养的培养
   - 教学流程是否符合{label}学科特点

2. **核心问题定位**（最关键部分）：
   - 从以上学科维度中，精准定位 **1-2 个最突出的问题**
   - 不要泛泛而谈"互动不够"，要具体到学科维度，例如"{label}课堂中'XX维度'存在明显不足"
   - 每个问题要附上课堂中的**具体证据**（引用原文片段）

3. **根因归因**：
   - 分析每个问题出现的可能原因
   - 结合学科特点和教师教学风格进行判断
   - 区分"知识性问题"（如学科功底不足）和"方法性问题"（如教学策略不当）

4. **改进预判**：
   - 如果不改进，对学生学习{label}会造成什么影响
   - 如果改进，预期会有什么效果

5. **特级教师建议**（3条，每条包含原理/现状/具体做法）：
   - 建议必须**用{label}学科的语言**来表述
   - 每条建议要给出**可直接操作的具体做法**，包括可以怎么提问、怎么设计环节
   - 建议要针对刚才定位的核心问题，而非泛泛的"多互动""多提问"

6. **下次课关注点**（用于纵向追踪闭环）：
   - 下次分析时应重点关注哪些指标的变化
   - 如何判断本次建议是否被采纳和生效

输出严格 JSON:
{{
  "subject_diagnosis": "学科宏观诊断...",
  "core_problems": [
    {{
      "problem": "问题描述",
      "evidence": "课堂原文证据",
      "dimension": "对应的学科维度",
      "severity": "高/中/低"
    }}
  ],
  "root_cause_analysis": "根因分析...",
  "improvement_forecast": "改进预判...",
  "expert_recommendations": [
    {{
      "title": "建议标题",
      "principle": "背后的教学原理",
      "current_situation": "课堂现状描述",
      "specific_action": "具体操作方法（可直接执行）"
    }}
  ],
  "next_focus": ["关注点1", "关注点2"]
}}"""
    return prompt


def build_subject_dimensions_prompt(profile):
    """
    生成学科特有维度分析 Prompt
    独立于 Agent F，用于产出学科特有维度的量化数据
    """
    subject = profile["subject"]
    label = profile["label"]
    dimensions_detail = "\n".join([
        f'{i+1}. **{d["name"]}**：{d["description"]}\n'
        f'   评估指标：{"、".join(d["indicators"])}'
        for i, d in enumerate(profile["extra_dimensions"])
    ])

    prompt = f"""你是一位{label}教研专家。请从以下{label}学科特有维度对这堂课进行分析评估。

**{label}特有评价维度**：
{dimensions_detail}

对于每个维度，请：
1. 根据课堂转录文本评估该维度的表现（0-100分）
2. 给出评分依据（引用课堂中的具体表现）
3. 列出做得好的地方和需要改进的地方

输出严格 JSON:
{{
  "subject_dimensions": [
    {{
      "name": "维度名",
      "score": 85,
      "evidence_good": "做得好的表现",
      "evidence_weak": "需要改进的表现",
      "detail": "详细分析"
    }}
  ],
  "subject_competencies_coverage": {{
    "competency": "核心素养名",
    "covered": true,
    "evidence": "课堂中的体现"
  }}
}}"""
    return prompt


def build_subject_flow_prompt(profile, lesson_type_config=None):
    """
    生成学科感知的教学环节切分 Prompt
    替代通用 5 阶段切分
    """
    subject = profile["subject"]
    label = profile["label"]

    # 按课型选择教学流程
    if lesson_type_config:
        lt = lesson_type_config["lesson_type"]
        flow = profile["teaching_flow"].get(lt, profile["teaching_flow"].get("新课", []))
    else:
        flow = profile["teaching_flow"].get("新课", [])

    flow_text = "、".join([f'"{f}"' for f in flow])

    prompt = f"""你是一位{label}学科教学专家。请将这堂{label}课切分为具体的教学环节。

**{label}学科的典型教学流程**：{flow_text}

请注意：
1. 尽量使用{label}学科的术语来命名环节，而非通用的"导入/讲授/练习/总结"
2. 准确区分教师讲授和学生活动的时间
3. 评估每个环节是否体现了{label}学科的教学特点

输出 JSON:
{{
  "segments": [
    {{"phase": "环节名（使用学科术语）", "type": "Lecture" | "Interaction" | "Practice" | "Other", "summary": "该环节内容摘要", "subject_note": "该环节体现的学科特点", "percentage": 15, "duration_minutes": 5}}
  ],
  "overall_stats": {{
    "total_lecture_minutes": 20,
    "total_interaction_minutes": 10,
    "total_practice_minutes": 10,
    "total_other_minutes": 5
  }},
  "flow_assessment": "教学流程是否符合{label}学科特点的评价"
}}"""
    return prompt


# ==========================================
# 分析执行
# ==========================================

def analyze_with_subject(transcription_text, subject, lesson_type=None,
                         base_data=None, teaching_design_text=None):
    """
    执行学科增强版分析

    参数:
        transcription_text: 课堂转录文本
        subject: 学科名称（如"语文"、"数学"）
        lesson_type: 课型（如"新课"、"复习课"、"讲题课"），可选
        base_data: v2 已有的分析结果（core_data），如果有则复用，避免重复调用
        teaching_design_text: 教学设计文本，可选

    返回:
        dict: 完整的 v3 分析数据
    """
    print(f"[v3.0] 学科: {subject}" + (f" | 课型: {lesson_type}" if lesson_type else ""))

    # 加载配置
    profile = load_subject_profile(subject)
    lt_config = load_lesson_type_config(lesson_type) if lesson_type else None
    print(f"[v3.0] 已加载学科配置: {profile['label']}")
    if lt_config:
        print(f"[v3.0] 已加载课型配置: {lt_config['label']}")

    v3_data = {
        "subject": subject,
        "lesson_type": lesson_type,
        "profile": profile,
        "lesson_type_config": lt_config,
        "base_data": base_data,
    }

    # Step 1: 学科特有维度分析
    print("[v3.0] 分析学科特有维度...")
    dim_prompt = build_subject_dimensions_prompt(profile)
    result_dim = call_volc_agent(dim_prompt, transcription_text)
    if result_dim:
        v3_data["subject_dimensions"] = json.loads(clean_json_string(result_dim))
    else:
        v3_data["subject_dimensions"] = None
        print("[v3.0] ⚠ 学科维度分析失败")

    # Step 2: 学科感知的教学环节切分（可选增强）
    if not base_data or "structure" not in base_data:
        print("[v3.0] 执行学科感知的教学环节切分...")
        flow_prompt = build_subject_flow_prompt(profile, lt_config)
        result_flow = call_volc_agent(flow_prompt, transcription_text)
        if result_flow:
            v3_data["subject_structure"] = json.loads(clean_json_string(result_flow))
        else:
            v3_data["subject_structure"] = None
    else:
        print("[v3.0] 复用 v2 教学环节分析数据")

    # Step 3: 学科增强版 Agent F（产品核心）
    print("[v3.0] 生成学科特级教师诊断...")
    prompt_f = build_subject_aware_prompt_f(profile, lt_config)

    # 组装上下文
    f_context = {}
    if base_data:
        f_context["v2_analysis"] = {
            "radar_scores": base_data.get("deep", {}).get("radar_scores"),
            "bloom_stats": base_data.get("deep", {}).get("bloom_stats"),
            "persona": base_data.get("deep", {}).get("persona"),
            "structure_summary": base_data.get("structure", {}).get("overall_stats"),
            "v2_recommendations": base_data.get("report", {}).get("recommendations"),
        }
    if teaching_design_text:
        f_context["teaching_design"] = teaching_design_text
    if v3_data.get("subject_dimensions"):
        f_context["subject_dimensions_result"] = v3_data["subject_dimensions"]

    context_str = json.dumps(f_context, ensure_ascii=False) if f_context else ""
    user_content = transcription_text + ("\n\n---\n参考数据:\n" + context_str if context_str else "")

    result_f = call_volc_agent(prompt_f, user_content)
    if result_f:
        v3_data["subject_report"] = json.loads(clean_json_string(result_f))
    else:
        v3_data["subject_report"] = None
        print("[v3.0] ⚠ 学科诊断失败")

    print("[v3.0] 学科增强分析完成!")
    return v3_data


# ==========================================
# CLI 快速测试
# ==========================================

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="ICAS v3.0 学科感知引擎测试")
    parser.add_argument("--list-subjects", action="store_true", help="列出可用学科")
    parser.add_argument("--list-lesson-types", action="store_true", help="列出可用课型")
    parser.add_argument("--show-prompt", type=str, help="显示指定学科的 Agent F Prompt")
    args = parser.parse_args()

    if args.list_subjects:
        print("可用学科:", ", ".join(list_available_subjects()))
    elif args.list_lesson_types:
        print("可用课型:", ", ".join(list_available_lesson_types()))
    elif args.show_prompt:
        profile = load_subject_profile(args.show_prompt)
        print(build_subject_aware_prompt_f(profile))
    else:
        parser.print_help()
