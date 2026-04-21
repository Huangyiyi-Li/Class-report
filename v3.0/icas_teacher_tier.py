# -*- coding: utf-8 -*-
"""
ICAS v3.0 教师分层模块
静态分层（学科×年级×教龄）+ 结果分层（卓越/成熟/成长/待提升）+ 个性化建议

设计原则：
- 基于分析数据自动判定层级
- 不同层级匹配不同的建议策略
- 支持纵向追踪的趋势判断
"""

import json
from pathlib import Path


# ==========================================
# 分层标准定义
# ==========================================

TIER_DEFINITIONS = {
    "卓越": {
        "score_range": (90, 100),
        "label": "卓越教师",
        "color": "#10b981",
        "icon": "🌟",
        "strategy": "赋能他人",
        "advice_direction": [
            "可作为学科示范课教师，承担校内公开课和带教任务",
            "建议探索教学创新，形成个人教学风格体系",
            "可参与区域教研分享，贡献优质课例资源",
            "关注高阶教学能力：项目式学习、跨学科整合、个性化教学"
        ]
    },
    "成熟": {
        "score_range": (75, 89),
        "label": "成熟教师",
        "color": "#3b82f6",
        "icon": "💪",
        "strategy": "精进方向",
        "advice_direction": [
            "基础扎实，建议聚焦1-2个维度进行精进突破",
            "关注高阶思维培养，提升提问的认知层次",
            "尝试差异化教学，关注不同层次学生的学习需求",
            "可开展教学小课题研究，实现教研一体"
        ]
    },
    "成长": {
        "score_range": (60, 74),
        "label": "成长型教师",
        "color": "#f59e0b",
        "icon": "📈",
        "strategy": "聚焦薄弱项",
        "advice_direction": [
            "有成长空间，建议聚焦最薄弱的1-2个维度重点突破",
            "夯实教学基本功：教学设计、课堂提问、反馈技巧",
            "建议多观摩优秀课例，学习成熟教师的教学策略",
            "制定短期可执行的改进计划（2-3周一个小目标）"
        ]
    },
    "待提升": {
        "score_range": (0, 59),
        "label": "待提升教师",
        "color": "#ef4444",
        "icon": "🔧",
        "strategy": "基础夯实",
        "advice_direction": [
            "需要重点帮扶，建议安排经验丰富的教师进行一对一指导",
            "优先夯实教学常规：明确教学目标、合理分配时间、规范教学语言",
            "建议从模仿优秀课例开始，先掌握基本教学流程",
            "高频次听课和被听课（每周至少1次），加速成长"
        ]
    }
}


# ==========================================
# 静态分层
# ==========================================

def classify_static(subject=None, grade=None, experience=None):
    """
    静态分层：基于学科、年级、教龄

    返回:
        dict: 静态分层信息，用于对比基准选择
    """
    cohort = []

    # 学科分组
    if subject:
        cohort.append(f"学科={subject}")

    # 年级分组
    grade_group = None
    if grade:
        grade_str = str(grade)
        if grade_str in ["1", "2", "3", "一", "二", "三", "一年级", "二年级", "三年级"]:
            grade_group = "低段"
        elif grade_str in ["4", "5", "6", "四", "五", "六", "四年级", "五年级", "六年级"]:
            grade_group = "高段"
        elif grade_str in ["7", "8", "9", "七", "八", "九", "初一", "初二", "初三",
                           "七年级", "八年级", "九年级"]:
            grade_group = "初中"
        elif grade_str in ["10", "11", "12", "高一", "高二", "高三"]:
            grade_group = "高中"
        if grade_group:
            cohort.append(f"年级段={grade_group}")

    # 教龄分组
    exp_group = None
    if experience is not None:
        exp = int(experience)
        if exp <= 3:
            exp_group = "新手期(0-3年)"
        elif exp <= 5:
            exp_group = "适应期(4-5年)"
        elif exp <= 10:
            exp_group = "成长期(6-10年)"
        elif exp <= 20:
            exp_group = "成熟期(11-20年)"
        else:
            exp_group = "专家期(20年+)"
        cohort.append(f"教龄段={exp_group}")

    return {
        "subject": subject,
        "grade": grade,
        "grade_group": grade_group,
        "experience": experience,
        "experience_group": exp_group,
        "cohort": " | ".join(cohort) if cohort else "未分组",
    }


# ==========================================
# 结果分层
# ==========================================

def classify_by_score(radar_scores, subject_dimension_scores=None):
    """
    基于分析结果自动分层

    参数:
        radar_scores: 五维雷达分数 [逻辑, 互动, 提问, 支持, 管理]
        subject_dimension_scores: 学科特有维度分数列表，可选

    返回:
        dict: 分层结果 + 建议策略
    """
    # 基础分数：五维雷达均值
    base_avg = sum(radar_scores) / len(radar_scores) if radar_scores else 0

    # 如果有学科维度分数，合并计算
    all_scores = list(radar_scores)
    if subject_dimension_scores:
        all_scores.extend(subject_dimension_scores)

    composite_score = sum(all_scores) / len(all_scores)

    # 确定层级
    tier_name = "待提升"
    for name, definition in TIER_DEFINITIONS.items():
        low, high = definition["score_range"]
        if low <= composite_score <= high:
            tier_name = name
            break

    tier_def = TIER_DEFINITIONS[tier_name]

    # 识别薄弱项
    radar_labels = ["教学逻辑", "互动技巧", "提问深度", "情感支持", "课堂管理"]
    weak_items = []
    for label, score in zip(radar_labels, radar_scores):
        if score < 70:
            weak_items.append({"dimension": label, "score": score, "urgency": "高" if score < 60 else "中"})

    # 识别优势项
    strong_items = []
    for label, score in zip(radar_labels, radar_scores):
        if score >= 85:
            strong_items.append({"dimension": label, "score": score})

    return {
        "tier": tier_name,
        "tier_label": tier_def["label"],
        "tier_icon": tier_def["icon"],
        "tier_color": tier_def["color"],
        "strategy": tier_def["strategy"],
        "composite_score": round(composite_score, 1),
        "base_radar_avg": round(base_avg, 1),
        "weak_items": weak_items,
        "strong_items": strong_items,
        "advice_direction": tier_def["advice_direction"],
    }


def generate_tiered_advice(tier_result, subject_profile=None, trend_data=None):
    """
    生成分层个性化建议

    参数:
        tier_result: classify_by_score 的输出
        subject_profile: 学科配置（可选，用于学科针对性）
        trend_data: 纵向趋势数据（可选，用于判断改进方向）

    返回:
        str: 个性化建议文本
    """
    parts = []

    # 分层定位
    parts.append(f"## 教师分层定位：{tier_result['tier_icon']} {tier_result['tier_label']}")
    parts.append(f"综合评分：{tier_result['composite_score']}分")
    parts.append(f"建议策略：**{tier_result['strategy']}**\n")

    # 薄弱项
    if tier_result["weak_items"]:
        parts.append("### 重点突破维度")
        for item in tier_result["weak_items"]:
            parts.append(f"- **{item['dimension']}**（{item['score']}分，紧急度：{item['urgency']}）")
        parts.append("")

    # 优势项
    if tier_result["strong_items"]:
        parts.append("### 优势维度")
        for item in tier_result["strong_items"]:
            parts.append(f"- **{item['dimension']}**（{item['score']}分）")
        parts.append("")

    # 分层建议方向
    parts.append("### 分层建议方向")
    for advice in tier_result["advice_direction"]:
        parts.append(f"- {advice}")

    # 学科针对性补充
    if subject_profile:
        subject = subject_profile["subject"]
        parts.append(f"\n### {subject}学科针对性建议")
        if tier_result["weak_items"]:
            weak_dim = tier_result["weak_items"][0]["dimension"]
            parts.append(f"结合{subject}学科特点，建议优先在「{weak_dim}」方向发力，")
            parts.append(f"参考{subject}学科特级教师的课堂实践进行针对性学习。")

    # 纵向趋势
    if trend_data:
        parts.append("\n### 成长趋势")
        if trend_data.get("trend") == "improving":
            parts.append("📈 整体呈上升趋势，建议保持当前改进节奏。")
        elif trend_data.get("trend") == "declining":
            parts.append("⚠️ 近期有所下滑，建议关注近期教学状态变化，排查原因。")
        elif trend_data.get("trend") == "stable":
            parts.append("➡️ 整体稳定，建议寻找突破口进入下一个成长阶段。")
        else:
            parts.append("📊 首次建立基线，后续分析将持续追踪成长轨迹。")

    return "\n".join(parts)


# ==========================================
# 趋势判断（依赖纵向数据）
# ==========================================

def judge_trend(historical_scores):
    """
    判断教师成长趋势

    参数:
        historical_scores: 按时间排序的分数列表 [{date, score}, ...]

    返回:
        dict: 趋势判断结果
    """
    if len(historical_scores) < 2:
        return {"trend": "baseline", "description": "数据不足，首次建立基线"}

    scores = [h["score"] for h in historical_scores]
    latest = scores[-1]
    previous = scores[-2]
    diff = latest - previous

    if diff >= 5:
        trend = "improving"
        description = f"显著进步（+{diff:.1f}分），保持势头"
    elif diff >= 2:
        trend = "improving"
        description = f"稳步提升（+{diff:.1f}分）"
    elif diff <= -5:
        trend = "declining"
        description = f"明显下滑（{diff:.1f}分），需要关注"
    elif diff <= -2:
        trend = "declining"
        description = f"略有下降（{diff:.1f}分），建议复盘"
    else:
        trend = "stable"
        description = "基本稳定，寻找突破口"

    return {
        "trend": trend,
        "description": description,
        "latest_score": latest,
        "change": round(diff, 1),
        "data_points": len(scores),
    }
