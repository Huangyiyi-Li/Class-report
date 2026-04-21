# -*- coding: utf-8 -*-
"""
ICAS 扩展分析模块
对标科大讯飞课堂分析，新增9大分析维度
生成独立补充报告

新增维度:
  - S-T师生行为分析 (Rt/Ch/课堂类型)
  - 教师语速分析
  - 高频词汇/词云
  - 问题链分析 (思维类型/问题类型/情境复杂度)
  - 4MAT问题分类 (是何/如何/若何/为何)
  - 问题开放性分类
  - 学生思维五维 (形象/逻辑/元认知/系统/辩证)
  - 学生应答分析
  - 教师反馈类型细化
"""

import json
import re
import jieba
from icas_core import call_volc_agent, clean_json_string


# ==========================================
# 中文停用词 (词频分析用)
# ==========================================
STOP_WORDS = {
    '的', '了', '在', '是', '我', '有', '和', '就', '不', '人', '都', '一', '上',
    '也', '很', '到', '说', '要', '去', '你', '会', '着', '看', '好', '这', '他',
    '她', '么', '那', '啊', '吧', '呢', '嗯', '哦', '呀', '啦', '哈', '嘛', '哎',
    '吗', '但', '但是', '因为', '所以', '如果', '虽然', '已经', '就是', '可能',
    '应该', '需要', '我们', '他们', '你们', '然后', '接着', '那么', '怎样', '怎么',
    '还是', '可以', '不是', '没有', '什么', '这个', '那个', '这些', '那些', '这样',
    '那样', '只是', '而且', '并且', '或者', '以及', '同时', '另外', '此外', '还有',
    '自己', '比较', '非常', '特别', '更', '最', '太', '真', '真的', '确实',
    '一些', '一下', '一个', '一点', '这种', '那种', '怎样', '时候', '现在',
    '出来', '起来', '下来', '上去', '下去', '过来', '回来', '进来',
    '把', '被', '让', '给', '向', '从', '往', '于', '为', '跟', '与', '同',
    '及', '等', '之', '其', '地', '得', '着', '过', '来', '去',
    # 转录标记 (s1, s2, spk 等说话人标识)
    's1', 's2', 's3', 's4', 'spk', 'spk0', 'spk1', 'spk2', 'speaker',
    'unk', 'silence', 'na', 'nan',
}


# ==========================================
# Agent Prompt 模板
# ==========================================

PROMPT_AGENT_ST = """你是一位课堂观察分析专家。请对课堂转录文本进行S-T师生行为分析。

分析要求:

1. **师生行为时间估算**:
   - 识别哪些内容是教师说的，哪些是学生说的
   - 估算教师说话总时长(分钟)和学生说话总时长(分钟)
   - 计算Rt值(教师行为占有率 = 教师时长/总时长)
   - 估算行为转换次数Ch(师生交替说话的次数)除以总行为段数

2. **课堂类型判定** (基于Rt和Ch):
   - Rt ≥ 0.7: 讲授型
   - Rt ≤ 0.3: 练习型
   - 0.3 < Rt < 0.7 且转换少: 对话型
   - 0.3 < Rt < 0.7 且转换多: 混合型

3. **各环节师生行为分布**:
   - 将课堂分为4-6个环节(如导入、讲授、练习等)
   - 每个环节估算教师和学生各自的说话时长占比

4. **教师语速分析**:
   - 估算教师总发言字数
   - 估算教师说话时长(分钟)
   - 计算平均语速(字/分钟)
   - 推荐范围: 150-250字/分钟，给出评估

输出严格JSON:
{
  "teacher_minutes": 21.6,
  "student_minutes": 4.8,
  "total_minutes": 26.4,
  "rt": 0.82,
  "ch": 0.33,
  "classroom_type": "讲授型",
  "type_description": "简要说明...",
  "per_phase": [
    {"phase": "环节名", "teacher_pct": 85, "student_pct": 15},
    ...
  ],
  "speech_rate": {
    "total_words": 3600,
    "speaking_minutes": 25.0,
    "words_per_minute": 144,
    "assessment": "语速评估..."
  },
  "suggestions": "针对师生互动平衡的改进建议..."
}
"""


PROMPT_AGENT_QA = """你是一位教学策略分析专家。请对课堂转录文本中的提问进行深度分析。

分析要求:

1. **问题链分析**:
   - 将教师的提问按主题分组为3-7个"问题链"
   - 每个问题链标注:
     - 思维类型: 逻辑思维 | 形象思维 | 元认知思维 | 系统思维 | 辩证思维
     - 问题类型: 平行型 | 收敛型 | 提高型 | 拓展型
     - 情境复杂度: 简单情境 | 复杂情境 | 无情境
   - 列出该链中的2-3个代表性问题(从原文提取)

2. **4MAT问题分类** (统计每类数量):
   - 是何(What/事实型): 询问事实、定义、识别
   - 如何(How/方法型): 询问方法、步骤、操作
   - 若何(What-if/变化型): 假设性、变换条件的问题
   - 为何(Why/原理型): 探究原因、原理、本质

3. **问题开放性分类** (统计数量):
   - 开放性: 没有固定答案，鼓励多元思考
   - 封闭性: 有明确唯一答案

4. **总提问数**: 统计教师提出的所有问题

输出严格JSON:
{
  "total_questions": 28,
  "question_chains": [
    {
      "id": 1,
      "topic": "问题链主题(简短)",
      "thinking_type": "逻辑思维",
      "question_type": "平行型",
      "complexity": "简单情境",
      "questions": ["原文问题1", "原文问题2"]
    }
  ],
  "fourmat": {"what": 24, "how": 3, "what_if": 0, "why": 1},
  "openness": {"open": 8, "closed": 20},
  "chain_analysis": "对整体问题链设计的分析评语...",
  "chain_suggestions": "针对提问策略的改进建议..."
}
"""


PROMPT_AGENT_STUDENT = """你是一位学生认知发展分析专家。请对课堂转录文本中学生的表现和教师的反馈进行分析。

分析要求:

1. **学生思维五维分析** (每个维度):
   - 形象思维: 通过观察、想象理解内容的能力
   - 逻辑思维: 通过推理、分析理解内容的能力
   - 元认知思维: 自我监控、反思评价的能力
   - 系统思维: 整体把握、关联思考的能力
   - 辩证思维: 对立统一、多角度思考的能力
   每个维度评级: "全面体现" | "初步体现" | "尚未体现"
   每个维度给出具体表现分析和教学建议

2. **学生应答分析**:
   - 估算学生回答问题的次数
   - 应答方式: 主动回答% 和 被动回答%
   - 回答字数分布: 短(1-5字)、中(6-15字)、长(16字以上)

3. **教师反馈类型分析**:
   - 评价性反馈: 对学生回答进行价值判断("很好""不对"等)
   - 指导性反馈: 给予方向性引导("再想想""从XX角度"等)
   - 鼓励性反馈: 正向激励("不错""继续"等)
   - 统计每种类型的次数

4. **常用反馈语提取**:
   - 从原文中提取3-5句典型的教师反馈语
   - 标注每句的反馈类型和情境

输出严格JSON:
{
  "student_thinking": [
    {
      "type": "形象思维",
      "level": "全面体现",
      "analysis": "具体表现分析...",
      "suggestion": "教学建议..."
    }
  ],
  "student_response": {
    "total": 15,
    "active_pct": 40,
    "passive_pct": 60,
    "length": {"short": 8, "medium": 5, "long": 2},
    "analysis": "学生应答情况分析...",
    "suggestions": "改进建议..."
  },
  "teacher_feedback": {
    "total": 20,
    "evaluative": 8,
    "directive": 5,
    "encouraging": 7,
    "analysis": "反馈情况分析...",
    "suggestions": "改进建议..."
  },
  "common_phrases": [
    {"phrase": "反馈语原文", "type": "评价性", "context": "情境"}
  ]
}
"""


# ==========================================
# 词频分析 (本地计算，不需要AI)
# ==========================================

def analyze_word_frequency(text, top_n=30):
    """使用jieba分析词频，返回高频词列表"""
    # 分词
    words = jieba.cut(text)

    # 过滤：去停用词、去单字、去纯数字/标点/转录标记
    filtered = []
    for w in words:
        w = w.strip()
        if len(w) < 2:
            continue
        if w in STOP_WORDS:
            continue
        if w.isdigit():
            continue
        if w.isascii():  # 过滤纯英文/字母数字(如 s1, spk2)
            continue
        if all(c in '，。！？、；：""''（）《》【】…—·,.\'\"!?;:()[]{}/<> \t\n\r' for c in w):
            continue
        filtered.append(w)

    # 统计词频
    from collections import Counter
    counter = Counter(filtered)

    # 返回 top N
    result = []
    for word, count in counter.most_common(top_n):
        result.append({"name": word, "value": count})

    return result


# ==========================================
# 扩展分析主函数
# ==========================================

def analyze_extended(transcription_text):
    """
    执行扩展分析流程 (3个新Agent + 词频分析)

    参数:
        transcription_text: 课堂转录文本

    返回:
        dict: 扩展分析数据
    """
    extended_data = {}

    # 1. 词频分析 (本地计算，无需API)
    print("[扩展] 分析高频词汇...")
    extended_data['word_freq'] = analyze_word_frequency(transcription_text, top_n=30)

    # 2. Agent ST: S-T师生行为分析
    print("[扩展] Agent ST: S-T师生行为分析...")
    result_st = call_volc_agent(PROMPT_AGENT_ST, transcription_text)
    if result_st:
        extended_data['st_analysis'] = json.loads(clean_json_string(result_st))
    else:
        print("  ⚠️ Agent ST 失败，使用空数据")
        extended_data['st_analysis'] = None

    # 3. Agent QA: 提问与问题链分析
    print("[扩展] Agent QA: 提问与问题链分析...")
    result_qa = call_volc_agent(PROMPT_AGENT_QA, transcription_text)
    if result_qa:
        extended_data['qa_analysis'] = json.loads(clean_json_string(result_qa))
    else:
        print("  ⚠️ Agent QA 失败，使用空数据")
        extended_data['qa_analysis'] = None

    # 4. Agent Student: 学生思维与反馈分析
    print("[扩展] Agent Student: 学生思维与反馈分析...")
    result_student = call_volc_agent(PROMPT_AGENT_STUDENT, transcription_text)
    if result_student:
        extended_data['student_analysis'] = json.loads(clean_json_string(result_student))
    else:
        print("  ⚠️ Agent Student 失败，使用空数据")
        extended_data['student_analysis'] = None

    print("[扩展] 扩展分析完成!")
    return extended_data
