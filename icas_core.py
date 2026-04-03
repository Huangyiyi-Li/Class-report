# -*- coding: utf-8 -*-
"""
ICAS 课堂分析核心模块
提取自 app.py,用于命令行自动化调用
"""

import json
import re
import time
from openai import OpenAI
import markdown
import pandas as pd
from docx import Document
from pathlib import Path


# ==========================================
# 全局配置
# ==========================================

API_KEY = "12f6605e-5f2b-48e2-80e4-0f937557ec1a"
BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"
MODEL_NAME = "ep-20251223144447-7946z"


# ==========================================
# Prompt 模板
# ==========================================

PROMPT_AGENT_B = """
将课堂切分为:1.导入 2.讲授 3.练习 4.总结 5.互动/问答。
对于每个阶段,请根据文本内容量估算其时长占比(百分比)和大概的持续时间(分钟,假设正常语速)。
**特别注意**:请准确区分"教师讲授"和"问答/互动"的时间。

输出 JSON:
{
  "segments": [
    {"phase": "阶段名", "type": "Lecture" | "Interaction" | "Practice" | "Other", "summary": "摘要", "percentage": 15, "duration_minutes": 5}
  ],
  "overall_stats": {
    "total_lecture_minutes": 20,
    "total_interaction_minutes": 10,
    "total_practice_minutes": 10,
    "total_other_minutes": 5
  }
}
"""

PROMPT_AGENT_DEEP = """
你是由教育测量学家组成的专家组。请分析文本,输出用于绘制图表的严格 JSON 数据:

1. **Bloom 分布**:统计记忆、理解、应用、分析、评价、创造六类问题的数量。
2. **Hattie 反馈**:统计任务层级、过程层级、自我层级反馈的数量。
3. **五维能力评分 (Radar Data)**:请根据表现给教师打分 (0-100分):
   - 教学逻辑 (Logic)
   - 互动技巧 (Interaction)
   - 提问深度 (Questioning)
   - 情感支持 (Support)
   - 课堂管理 (Management)

4. **教学风格画像**:
   - 风格标签 (Tag): 4-6字。
   - 关键词 (Keywords): 5个。

输出 JSON:
{
  "bloom_stats": [{"level": "记忆", "count": 5}, ...],
  "hattie_stats": {"task_level": 5, "process_level": 3, "self_level": 2},
  "radar_scores": [85, 70, 60, 90, 80],
  "persona": {"tag": "循循善诱型导师", "keywords": ["思考", "逻辑"]}
}
"""

PROMPT_AGENT_CONTENT = """
你是一位严谨的教研组长。请对课堂进行"显微镜式"的深度审计。输出以下 JSON:

1. **知识图谱 (Knowledge Graph)**:
   - Root: 核心主题 (不超过6个字)
   - Nodes: 3-5个核心关键词 (⚠️⚠️严格限制每个节点字数在6个字以内,例如"复习旧知",禁止长句)
   - Logic: 知识点逻辑关系描述 (简练)

2. **教学常规清单 (Checklist)**:
   - review (复习): boolean
   - homework (作业): boolean
   - summary (总结): boolean
   - homework_detail: 作业详情字符串

3. **微格教学切片 (Micro_Moments)**:
   - ⚠️⚠️⚠️ **必须从原文中提取真实的师生对话片段**，绝对禁止编造！
   - 在全文中找到 **2个最典型的师生互动片段**(Dialogues)。
   - 对话内容必须完全来自原文，可以直接引用或轻微整理格式
   - 对每个片段进行逐字逐句的点评(Analysis)。
   - 指出这个片段体现了什么教学策略,或者暴露了什么问题。

输出 JSON:
{
  "knowledge_graph": {
    "root": "主题",
    "nodes": ["A", "B"],
    "logic": "..."
  },
  "checklist": { ... },
  "micro_moments": [
    {
      "title": "片段一:对于难点X的追问",
      "dialogue": "师:... \n生:...",
      "analysis": "教师在这里连续使用了三个反问句,有效地迫使学生跳出思维定势..."
    },
    {
      "title": "片段二:...",
      "dialogue": "...",
      "analysis": "..."
    }
  ]
}
"""

PROMPT_AGENT_F = """
你是一位带教新教师的**特级教师导师**。请撰写一份**万字长文级别的深度听课反馈**(实际输出约 800-1000 字)。
目标是帮助新教师实现职业跃迁,因此必须**知无不言,言无不尽**。

输入数据包含了课堂实录分析和(可选的)教师预设的【教学设计】。

**报告结构要求**:
1.  **宏观综述**:
    - 概括课堂内容、教学流派。
    - **【重要】教学设计契合度评价**:如果提供了教学设计,请详细评价实际授课是否达成了预设目标?有哪些偏离?偏离是精彩生成的还是失误?(若无教学设计则略过此点)。
2.  **内容逻辑链解构**:分析老师是如何一步步搭建知识脚手架的。逻辑是否顺畅?
3.  **微格案例点评**:结合 Agent G 提供的互动切片,进行深度剖析。
4.  **学生认知诊断**:分析学生听懂了吗?在哪里卡住了?(基于互动反应推测)。
5.  **大师级建议**:给出 3 条极具操作性的建议,每条建议都要包含"原理"、"现状"和"具体做法"。

输出严格 JSON:
{
  "macro_review": "深度综述(包含教学设计契合度分析)...",
  "logic_analysis": "关于知识构建逻辑的详细分析...",
  "student_cognition": "对学生学习状态的深度洞察...",
  "recommendations": [
    { "title": "建议1标题", "content": "详细内容..." },
    { "title": "建议2标题", "content": "详细内容..." },
    { "title": "建议3标题", "content": "详细内容..." }
  ]
}
"""


# ==========================================
# 工具函数
# ==========================================

def clean_json_string(text):
    """强力清洗 JSON,防止 Extra Data 报错"""
    pattern = r"```json\s*(.*?)\s*```"
    match = re.search(pattern, text, re.DOTALL)
    if match:
        text = match.group(1)

    text = text.strip()
    first_brace = text.find('{')
    last_brace = text.rfind('}')

    if first_brace != -1 and last_brace != -1:
        text = text[first_brace : last_brace+1]

    return text


def call_volc_agent(system_prompt, user_content):
    """调用火山引擎 (Doubao) API"""
    client = OpenAI(
        api_key=API_KEY,
        base_url=BASE_URL
    )
    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
            top_p=0.9,
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"❌ API 调用失败: {e}")
        return None


def read_excel_transcription(file_path):
    """从Excel读取H列(processed_text)的转录文本"""
    try:
        df = pd.read_excel(file_path)
        if 'processed_text' in df.columns:
            # 优先使用列名读取H列
            content = "\n".join(df['processed_text'].dropna().astype(str).tolist())
            return content
        elif len(df.columns) > 7:
            # 备用方案：使用索引7（H列）
            content = "\n".join(df.iloc[:, 7].dropna().astype(str).tolist())
            return content
        else:
            raise ValueError("Excel文件列数不足,无法读取H列(processed_text)")
    except Exception as e:
        raise Exception(f"读取Excel失败: {e}")


def read_word_document(file_path):
    """从Word读取教案文本"""
    try:
        doc = Document(file_path)
        text = []
        for para in doc.paragraphs:
            text.append(para.text)
        return "\n".join(text)
    except Exception as e:
        raise Exception(f"读取Word失败: {e}")


def analyze_classroom(transcription_text, teaching_design_text=None):
    """
    执行完整的课堂分析流程

    参数:
        transcription_text: 课堂转录文本
        teaching_design_text: 教学设计文本(可选)

    返回:
        dict: 完整的分析报告数据
    """
    report_data = {}

    print("[AI] Agent B: 梳理教学脉络与时间分配...")
    prompt_b_final = PROMPT_AGENT_B
    if "SPK" not in transcription_text and "00:" not in transcription_text:
        prompt_b_final += "\n(注意:文本似乎缺少时间戳,请根据字数和语速估算时间占比)"

    result_b = call_volc_agent(prompt_b_final, transcription_text)
    if not result_b:
        raise Exception("Agent B 分析失败")
    report_data['structure'] = json.loads(clean_json_string(result_b))

    print("[AI] Agent Deep: 计算五维雷达与风格...")
    result_deep = call_volc_agent(PROMPT_AGENT_DEEP, transcription_text)
    if not result_deep:
        raise Exception("Agent Deep 分析失败")
    report_data['deep'] = json.loads(clean_json_string(result_deep))

    print("[AI] Agent Content: 显微镜式扫描互动切片...")
    result_content = call_volc_agent(PROMPT_AGENT_CONTENT, transcription_text)
    if not result_content:
        raise Exception("Agent Content 分析失败")
    report_data['content'] = json.loads(clean_json_string(result_content))

    print("[AI] Agent F: 撰写万字长文诊断书...")
    f_context = {
        "analysis_data": report_data,
        "teaching_design": teaching_design_text if teaching_design_text else "未提供"
    }
    context_str = json.dumps(f_context, ensure_ascii=False)

    result_f = call_volc_agent(PROMPT_AGENT_F, context_str)
    if not result_f:
        raise Exception("Agent F 分析失败")
    report_data['report'] = json.loads(clean_json_string(result_f))

    print("[完成] 深度诊断完成!")
    return report_data


def generate_ultimate_html(full_data, teaching_design=None):
    """生成包含微格分析的终极报告HTML"""

    structure = full_data['structure']
    deep = full_data['deep']
    content = full_data['content']
    report = full_data['report']

    # Unpack
    bloom_data = deep['bloom_stats']
    hattie_data = deep['hattie_stats']
    radar_data = deep['radar_scores']
    persona = deep['persona']
    kg = content['knowledge_graph']
    check = content['checklist']
    micro = content.get('micro_moments', [])

    # Time Data
    time_stats = structure.get('overall_stats', {})
    time_chart_data = [
        {'value': time_stats.get('total_lecture_minutes', 0), 'name': '教师讲授', 'itemStyle': {'color': '#6366f1'}},
        {'value': time_stats.get('total_interaction_minutes', 0), 'name': '师生互动', 'itemStyle': {'color': '#ec4899'}},
        {'value': time_stats.get('total_practice_minutes', 0), 'name': '学生练习', 'itemStyle': {'color': '#10b981'}},
        {'value': time_stats.get('total_other_minutes', 0), 'name': '其他环节', 'itemStyle': {'color': '#9ca3af'}}
    ]

    hattie_chart_data = [
        {'value': hattie_data.get('task_level', 0), 'name': '任务层级'},
        {'value': hattie_data.get('process_level', 0), 'name': '过程层级'},
        {'value': hattie_data.get('self_level', 0), 'name': '自我层级'}
    ]

    kg_data = [{'name': kg['root'], 'symbolSize': 60, 'itemStyle': {'color': '#4f46e5'}}]
    kg_links = []
    for node in kg['nodes']:
        kg_data.append({'name': node, 'symbolSize': 40, 'itemStyle': {'color': '#3b82f6'}})
        kg_links.append({'source': kg['root'], 'target': node})

    micro_html = ""
    for m in micro:
        micro_html += f"""
        <div class="bg-white border border-gray-200 rounded-xl p-5 mb-4 shadow-sm no-break">
            <h4 class="font-bold text-indigo-700 mb-2 border-b border-indigo-100 pb-2">{m['title']}</h4>
            <div class="bg-gray-50 p-3 rounded text-sm font-mono text-gray-600 mb-3 whitespace-pre-wrap">{m['dialogue']}</div>
            <div class="flex items-start gap-2">
                <span class="text-xl">👩‍🏫</span>
                <p class="text-gray-700 text-sm italic leading-relaxed"><span class="font-bold text-gray-900">导师点评:</span>{m['analysis']}</p>
            </div>
        </div>
        """

    def get_icon(status): return '✅' if status else '⬜'
    checklist_html = f"""
    <div class="grid grid-cols-2 gap-2 text-sm">
        <div class="bg-gray-50 p-2 rounded">{get_icon(check['review'])} 回顾旧知</div>
        <div class="bg-gray-50 p-2 rounded">{get_icon(check['summary'])} 课堂小结</div>
        <div class="bg-gray-50 p-2 rounded col-span-2">{get_icon(check['homework'])} 作业: {check['homework_detail']}</div>
    </div>
    """

    design_section_html = ""
    if teaching_design:
        design_section_html = f"""
        <div class="bg-indigo-50 p-5 rounded-xl border border-indigo-100 mb-6">
            <h2 class="section-title" style="border-color: #f43f5e;">教学设计契合度评价</h2>
            <div class="text-gray-800 text-sm leading-relaxed">
                <p class="mb-2"><strong>📎 提交的教学设计概览:</strong><br><span class="text-gray-500 italic">(已提交给专家系统)</span></p>
                <div class="p-3 bg-white rounded border border-indigo-100 mb-3 text-xs text-gray-500 max-h-24 overflow-y-auto">
                    {teaching_design[:200]}...
                </div>
                <p class="font-bold text-indigo-900">Expert Analysis:</p>
            </div>
        </div>
        """

    html = f"""
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="utf-8">
        <script src="https://cdn.tailwindcss.com"></script>
        <script src="https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js"></script>

        <style>
            @import url('https://fonts.googleapis.com/css2?family=Noto+Serif+SC:wght@400;700&display=swap');
            body {{ font-family: "Microsoft YaHei", sans-serif; background: #f3f4f6; color: #1f2937; }}

            .paper {{
                background: white;
                width: 100%;
                max-width: 210mm;
                margin: 0 auto;
                padding: 10mm;
                box-sizing: border-box;
                box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
            }}

            .tag-pill {{ background: #eff6ff; color: #1d4ed8; padding: 2px 10px; border-radius: 999px; font-size: 0.8rem; font-weight: 600; margin-right: 5px; }}
            .section-title {{ font-size: 1.1rem; font-weight: 800; color: #111827; margin-bottom: 1rem; border-left: 5px solid #4f46e5; padding-left: 0.75rem; display: flex; align-items: center; }}

            @media print {{
                body {{ background: white !important; -webkit-print-color-adjust: exact !important; print-color-adjust: exact !important; }}
                .paper {{ width: 100% !important; max-width: none !important; box-shadow: none !important; padding: 0 !important; margin: 0 !important; }}
                .no-print {{ display: none !important; }}

                /* ========== 关键分页控制 ========== */
                .chart-container, .chart-wrapper,
                .no-break, .bg-white.border.rounded-xl, .grid.grid-cols-2, .grid.grid-cols-3 {{
                    page-break-inside: avoid !important;
                    break-inside: avoid !important;
                }}

                h2, h3, h4 {{ page-break-after: avoid !important; break-after: avoid !important; }}
                p, li, td {{ orphans: 3 !important; widows: 3 !important; }}

                /* ========== 图表完整显示，不要截断 ========== */
                [id$="-chart"] {{
                    page-break-inside: avoid !important;
                    break-inside: avoid !important;
                    /* 移除 overflow: hidden 和 max-height 限制 */
                }}

                /* 优化边距和字体 */
                .mb-6 {{ margin-bottom: 1rem !important; }}
                .mb-8 {{ margin-bottom: 1.5rem !important; }}
                .text-3xl {{ font-size: 1.5rem !important; }}
                .text-sm {{ font-size: 0.8rem !important; }}
            }}
        </style>
    </head>
    <body class="py-10">
        <div class="fixed top-6 right-6 z-50 no-print">
            <div class="bg-green-50 border border-green-200 rounded-lg p-4 shadow-lg max-w-sm">
                <div class="flex items-start gap-3">
                    <span class="text-2xl">✅</span>
                    <div>
                        <p class="font-bold text-green-800 text-sm">PDF已自动生成!</p>
                        <p class="text-green-700 text-xs mt-1">PDF文件和HTML在同一文件夹,可直接使用</p>
                        <p class="text-green-600 text-xs mt-2 italic">如需手动保存,请等待页面完全加载后再操作</p>
                    </div>
                </div>
            </div>
        </div>

        <div id="report-content" class="paper">
            <div class="border-b-2 border-indigo-100 pb-6 mb-8">
                <div class="flex justify-between items-end">
                    <div>
                        <h1 class="text-3xl font-extrabold text-gray-900 tracking-tight">课堂教学深度诊断书</h1>
                        <p class="text-indigo-600 font-medium mt-1">ICAS ULTIMATE EDITION II</p>
                    </div>
                    <div class="text-right text-gray-500 text-sm">
                        <div>生成日期: {time.strftime("%Y-%m-%d")}</div>
                        <div>教学风格: {persona['tag']}</div>
                    </div>
                </div>
                <div class="mt-4">
                    {''.join([f'<span class="tag-pill">#{k}</span>' for k in persona['keywords']])}
                </div>
            </div>

            <div class="mb-6">
                <h2 class="section-title">宏观教学综述</h2>
                {design_section_html}
                <div class="text-gray-700 leading-relaxed text-justify text-sm">
                    {markdown.markdown(report['macro_review'], extensions=['nl2br'])}
                </div>
            </div>

             <div class="no-break mb-6 border border-indigo-50 bg-indigo-50/30 rounded-xl p-4 chart-container">
                <h2 class="section-title" style="border-left-color: #6366f1;">时间分配与教学节奏</h2>
                <div class="grid grid-cols-2 gap-4">
                     <div class="chart-wrapper">
                        <div id="time-chart" style="width: 100%; height: 200px;"></div>
                     </div>
                     <div class="flex flex-col justify-center text-sm text-gray-600">
                        <p><strong>👨‍🏫 讲授时长:</strong> {time_stats.get('total_lecture_minutes', 0)} 分钟</p>
                        <p><strong>🙋 互动/问答:</strong> {time_stats.get('total_interaction_minutes', 0)} 分钟</p>
                        <p><strong>📝 学生练习:</strong> {time_stats.get('total_practice_minutes', 0)} 分钟</p>
                        <p class="mt-2 text-xs text-gray-400">注:基于文本内容量的AI估算值</p>
                     </div>
                </div>
            </div>

            <div class="grid grid-cols-3 gap-6 mb-6 no-break chart-container">
                <div class="col-span-2 border border-gray-100 rounded-xl p-4 shadow-sm chart-wrapper">
                    <h3 class="font-bold text-gray-700 mb-2 text-sm">知识图谱与逻辑链</h3>
                    <div id="kg-chart" style="width: 100%; height: 200px;"></div>
                    <p class="text-xs text-gray-500 mt-2">{kg['logic']}</p>
                </div>
                <div class="col-span-1 border border-gray-100 rounded-xl p-4 shadow-sm bg-gray-50 chart-wrapper">
                    <h3 class="font-bold text-gray-700 mb-3 text-sm">教学常规核查</h3>
                    {checklist_html}
                    <div class="mt-4 pt-4 border-t border-gray-200">
                        <h3 class="font-bold text-gray-700 mb-2 text-sm">五维能力雷达</h3>
                        <div id="radar-chart" style="width: 100%; height: 150px;"></div>
                    </div>
                </div>
            </div>

            <div class="mb-6 bg-indigo-50 p-5 rounded-xl border border-indigo-100">
                <h2 class="section-title" style="border-color: #818cf8;">知识脚手架搭建分析</h2>
                <div class="text-gray-800 text-sm leading-relaxed">
                    {markdown.markdown(report['logic_analysis'], extensions=['nl2br'])}
                </div>
            </div>

            <div class="no-break">
                <h2 class="section-title">关键互动切片 (Micro-Teaching)</h2>
                {micro_html}
            </div>

            <div class="grid grid-cols-2 gap-6 mb-6 no-break chart-container">
                <div class="border border-gray-100 rounded-xl p-4 chart-wrapper">
                    <h3 class="font-bold text-gray-700 mb-2 text-center text-sm">认知激发深度 (Bloom)</h3>
                    <div id="bloom-chart" style="width: 100%; height: 250px;"></div>
                </div>
                <div class="border border-gray-100 rounded-xl p-4 chart-wrapper">
                    <h3 class="font-bold text-gray-700 mb-2 text-center text-sm">反馈质量分布 (Hattie)</h3>
                    <div id="hattie-chart" style="width: 100%; height: 250px;"></div>
                </div>
            </div>

            <div class="mb-6">
                <h2 class="section-title">学生认知诊断</h2>
                <div class="text-gray-700 text-sm mb-6 leading-relaxed">
                    {markdown.markdown(report['student_cognition'], extensions=['nl2br'])}
                </div>
                <h2 class="section-title">导师改进建议</h2>
                <div class="grid grid-cols-1 gap-4">
                    {''.join([f'''
                    <div class="flex gap-4 p-4 bg-white border-l-4 border-indigo-500 shadow-sm rounded-r-lg">
                        <div class="flex-shrink-0 w-8 h-8 rounded-full bg-indigo-100 text-indigo-600 flex items-center justify-center font-bold">{i+1}</div>
                        <div>
                            <h4 class="font-bold text-gray-900 text-sm mb-1">{rec['title']}</h4>
                            <p class="text-gray-600 text-sm">{markdown.markdown(rec['content'], extensions=['nl2br'])}</p>
                        </div>
                    </div>
                    ''' for i, rec in enumerate(report['recommendations'])])}
                </div>
            </div>

            <div class="mt-8 text-center text-xs text-gray-400">
                Generated by ICAS Ultimate System II (Powered by AI)
            </div>
            <div style="height: 50px;"></div>
        </div>

        <script>
            window.onload = function() {{
                // 1. 知识图谱
                echarts.init(document.getElementById('kg-chart')).setOption({{
                    series: [{{
                        type: 'graph', layout: 'force', symbolSize: 30,
                        label: {{ show: true, fontSize: 9 }},
                        data: {json.dumps(kg_data, ensure_ascii=False)},
                        links: {json.dumps(kg_links, ensure_ascii=False)},
                        force: {{ repulsion: 100, edgeLength: 50 }}
                    }}]
                }});

                // 2. 雷达图
                echarts.init(document.getElementById('radar-chart')).setOption({{
                    radar: {{
                        indicator: [
                            {{ name: '逻辑', max: 100 }}, {{ name: '互动', max: 100 }},
                            {{ name: '提问', max: 100 }}, {{ name: '支持', max: 100 }},
                            {{ name: '管理', max: 100 }}
                        ],
                        radius: '65%', splitNumber: 3, axisName: {{ fontSize: 8 }}
                    }},
                    series: [{{
                        type: 'radar',
                        data: [{{ value: {json.dumps(radar_data)}, areaStyle: {{ color: 'rgba(79, 70, 229, 0.2)' }} }}]
                    }}]
                }});

                // 3. Bloom
                echarts.init(document.getElementById('bloom-chart')).setOption({{
                    grid: {{ top: 20, bottom: 20, left: 30, right: 10 }},
                    xAxis: {{ type: 'category', data: {json.dumps([i['level'] for i in bloom_data], ensure_ascii=False)}, axisLabel: {{ fontSize: 9 }} }},
                    yAxis: {{ type: 'value', splitLine: {{ show: false }} }},
                    series: [{{ type: 'bar', data: {json.dumps([i['count'] for i in bloom_data])}, itemStyle: {{ color: '#6366f1', borderRadius: [3,3,0,0] }} }}]
                }});

                // 4. Hattie
                echarts.init(document.getElementById('hattie-chart')).setOption({{
                    tooltip: {{ trigger: 'item' }},
                    legend: {{ bottom: '0%', left: 'center', itemWidth: 10, itemHeight: 10, textStyle: {{ fontSize: 10 }} }},
                    series: [{{
                        type: 'pie',
                        radius: ['40%', '65%'],
                        center: ['50%', '40%'],
                        avoidLabelOverlap: true,
                        label: {{ show: false }},
                        labelLine: {{ show: false }},
                        data: {json.dumps(hattie_chart_data, ensure_ascii=False)}
                    }}]
                }});

                // 5. Time Analysis
                echarts.init(document.getElementById('time-chart')).setOption({{
                    tooltip: {{ trigger: 'item' }},
                    legend: {{ bottom: '0%', left: 'center', itemWidth: 10, itemHeight: 10, textStyle: {{ fontSize: 10 }} }},
                    series: [{{
                        type: 'pie',
                        radius: '70%',
                        center: ['50%', '40%'],
                        data: {json.dumps(time_chart_data, ensure_ascii=False)},
                        emphasis: {{
                            itemStyle: {{
                                shadowBlur: 10,
                                shadowOffsetX: 0,
                                shadowColor: 'rgba(0, 0, 0, 0.5)'
                            }}
                        }}
                    }}]
                }});
            }};
        </script>
    </body>
    </html>
    """
    return html
