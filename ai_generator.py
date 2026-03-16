"""
AI 内容生成模块
三阶段生成教案：
  Stage 1：全量PPT → 整体框架 + 教学大纲（含授课顺序、幻灯片对应关系）
  Stage 2：逐节丰富（多次调用）— 左栏知识内容（以AI知识库为主）+ 右栏教学活动（含思政、互动、手段）
  Stage 3：图片定位插入（由 template_filler 完成，本模块不涉及）
"""
import re
import anthropic
import json


# ─────────────────────────────────────────────
# 基础工具函数
# ─────────────────────────────────────────────

def _call_api(provider: str, api_key: str, prompt: str, max_tokens: int = 4096) -> str:
    """统一 API 调用入口，返回文本内容"""
    if provider == "deepseek":
        from openai import OpenAI
        client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
        response = client.chat.completions.create(
            model="deepseek-chat",
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content.strip()
    else:
        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}]
        )
        return message.content[0].text.strip()


def _extract_json(raw: str) -> dict:
    """从模型输出中提取 JSON 对象"""
    start = raw.find("{")
    end = raw.rfind("}") + 1
    return json.loads(raw[start:end])


def _extract_json_array(raw: str) -> list:
    """从模型输出中提取 JSON 数组"""
    start = raw.find("[")
    end = raw.rfind("]") + 1
    return json.loads(raw[start:end])


def _extract_slides_text(ppt_data: dict, slide_indices: list) -> str:
    """按页码从 ppt_data 中提取对应幻灯片的文字内容"""
    if not ppt_data or not slide_indices:
        return "（本节无对应PPT页面）"
    result = []
    for slide in ppt_data.get("slides", []):
        if slide["index"] in slide_indices:
            result.append(f"【第{slide['index']}页】{slide.get('title','')}\n{slide.get('text','')}")
    return "\n\n".join(result) if result else "（本节无对应PPT页面）"


# ─────────────────────────────────────────────
# Stage 1：生成整体框架与教学大纲
# ─────────────────────────────────────────────

def _generate_structure(
    provider: str, api_key: str,
    course_name: str, teacher_name: str, title: str,
    department: str, college: str, students: str,
    classroom: str, teaching_date: str,
    ppt_text: str, extra_notes: str,
    user_references: str = ""
) -> dict:
    """
    第一次调用：全量PPT → 教案所有字段 + 含授课顺序/幻灯片对应的教学大纲
    """
    prompt = f"""你是一位经验丰富的医学院校教学设计专家。请仔细阅读以下PPT全文，
理解本节课的全部授课内容和顺序，然后生成完整的教案框架。

## 基本信息
- 课程名称：{course_name}
- 授课教师：{teacher_name}
- 章节/主题：{title}
- 教研室：{department}
- 学院：{college}
- 教学对象：{students}
- 教学地点：{classroom}
- 授课时间：{teaching_date}
- 总课时：90分钟

## PPT完整内容（请仔细阅读每一页，理解授课顺序与内容架构）
{ppt_text if ppt_text else "（未提供PPT，请根据章节主题合理生成）"}

## 补充说明
{extra_notes if extra_notes else "无"}

## 参考文献（用户提供）
{user_references if user_references.strip() else "（用户未提供，请AI自动生成至少5条相关参考文献）"}

---

请严格按照以下JSON格式返回，不要输出任何JSON以外的内容：

{{
  "teaching_objective_knowledge": "【掌握】...（具体知识点，要求掌握的用※标记）\\n【了解】...（了解内容）\\n【自学】...（自学内容）",
  "teaching_objective_ability": "结合...知识，通过...，培养学生...能力。（2-3句话）",
  "teaching_objective_value": "结合...历史事件/人物，引导学生...，培养...精神。（融入思政，2-3句话）",
  "student_analysis_knowledge": "学生已完成...知识的学习，具备...基础，能够理解...。（3-4句话）",
  "student_analysis_cognition": "学生对...尚不熟悉，在...方面存在困难，需要...方式引导。（3-4句话）",
  "student_analysis_psychology": "学生对本课程有一定兴趣，...。（1-2句话）",
  "key_points": "※重点：\\n1. ...\\n2. ...\\n解决方法：【讲授法】【案例分析】【启发式提问】",
  "difficult_points": "△难点：\\n1. ...\\n解决方法：\\n- 难点1破解：采用...方法，通过...步骤，帮助学生理解...",
  "teaching_expansion": "1. 新进展：...\\n2. 历史回顾：...\\n3. 新医科展望：...",
  "self_study": "...",
  "teaching_method": "讲授式、启发式、讨论式；借助雨课堂平台授课；案例教学法",
  "teaching_tools": "多媒体课件（含图片、结构式）；雨课堂实时互动；学习通线上资源",
  "keywords_en": "关键词1；关键词2；关键词3；关键词4；关键词5（专业英语词汇）",
  "references": "（若用户提供了参考文献，则将其整理为标准格式；若未提供，则自动生成至少5条与本课程内容密切相关的参考文献，格式：序号. 作者. 《书名》（版次）. 出版社, 出版年份. 或期刊格式）",
  "blackboard_left": "章节标题\\n一、...\\n  ※（一）...\\n  △（二）...\\n二、...\\n  ※（一）...",
  "blackboard_right": "三、...\\n  ※（一）...\\n  △（二）...",
  "homework": "1. （选择题，针对重点）...\\nA. ...  B. ...  C. ...  D. ...\\n答案：\\n\\n2. （思考题）...",
  "self_study_resources": "1. 学习通课程资源\\n2. 中国大学MOOC：...\\n3. 推荐文献：...",
  "teaching_plan_outline": [
    {{
      "phase": "导课",
      "duration": 5,
      "knowledge_points": ["复习上节课核心内容（具体列出2-3个知识点）", "引出本节主题的切入点"],
      "related_slides": [1, 2]
    }},
    {{
      "phase": "正文",
      "duration": 70,
      "related_slides": [],
      "sections": [
        {{
          "section_id": "S1",
          "title": "一、XXX（按PPT授课顺序，不含重难点标记）",
          "duration": 20,
          "subsections": [
            {{"title": "※（一）XXX", "is_key": true, "is_difficult": false, "knowledge_points": ["...", "..."]}},
            {{"title": "※（二）XXX", "is_key": true, "is_difficult": false, "knowledge_points": ["..."]}},
            {{"title": "△（三）XXX", "is_key": false, "is_difficult": true, "knowledge_points": ["..."]}}
          ],
          "related_slides": [3, 4, 5],
          "ideological_point": "（与本节内容相关的思政切入点，如：结合XXX历史事件/人物，引导XXX精神；若无合适切入点则留空）"
        }},
        {{
          "section_id": "S2",
          "title": "二、XXX",
          "duration": 25,
          "subsections": [...],
          "related_slides": [6, 7, 8],
          "ideological_point": ""
        }}
      ]
    }},
    {{
      "phase": "小结",
      "duration": 10,
      "knowledge_points": ["本节核心知识点列表", "重难点强调"],
      "related_slides": []
    }},
    {{
      "phase": "课后布置",
      "duration": 5,
      "knowledge_points": ["布置作业内容", "自学任务"],
      "related_slides": []
    }}
  ]
}}

要求：
1. teaching_plan_outline 中各 phase 的 duration 之和必须等于90
2. 正文 sections 中各 section 的 duration 之和必须等于正文的 duration（70）
3. sections 按PPT授课顺序排列，标题层级规范：
   - 一级标题（section title）：按授课顺序，不含重难点标记
   - 二级标题（subsection title）：标注※重点或△难点
   - 三级标题（Stage 2 展开时使用）：1. 2. 3.
   - 四级标题（Stage 2 展开时使用）：(1)、(2)、(3)（半角括号+顿号，不加粗）
   - 五级标题（Stage 2 展开时使用）：a.、b.、c.（字母+顿号，按需使用，不加粗）
   - 不使用任何 markdown 标记（不用 **、*、# 等）
4. related_slides 必须与PPT实际页码对应，若不确定可留空数组
5. ideological_point 只记录思政切入方向，具体内容在 Stage 2 展开
"""
    raw = _call_api(provider, api_key, prompt, max_tokens=4096)
    return _extract_json(raw)


# ─────────────────────────────────────────────
# Stage 2：逐节丰富内容
# ─────────────────────────────────────────────

def _expand_non_main_phases(
    provider: str, api_key: str,
    course_name: str, title: str,
    ppt_text_short: str,
    outline_items: list,
    key_points: str, difficult_points: str
) -> list:
    """
    Stage 2 第一次调用：导课 + 小结 + 课后布置，合并一次生成
    返回这三个 phase 的详细内容列表
    """
    outline_str = json.dumps(outline_items, ensure_ascii=False, indent=2)

    prompt = f"""你是一位医学院校药学专业教师，请为教案的【导课】【小结】【课后布置】三个环节
生成详细内容。

## 课程信息
- 课程：{course_name}，章节：{title}

## 本节重难点
{key_points}
{difficult_points}

## PPT要点（仅作结构参考）
{ppt_text_short}

## 需要展开的大纲
{outline_str}

---

要求：
- content（左栏内容架构）：具体的知识点或任务描述
- activity（右栏教学活动）格式规范：
  * 第一行写"时间：X min"，只写一次，时间行后不需要关键词行
  * 【】模块按左栏内容顺序排列，但不需要每个环节都有模块——只对有特色教学设计的环节写模块
  * 每个模块以【模块名称】单独一行开始，紧跟一句简短说明（说明该环节对应哪部分内容及教学意图，如：对应复习旧知识，通过提问激活记忆），内容结束后写 "---" 再空两行
  * 模块内只用 1. 2. 3. 编号，不写括号时间注（如"（2min）"）
  * 常用模块：【雨课堂签到】【复习提问】【导入新课】【课堂小结】【雨课堂测验】【布置作业】等

请严格按照以下JSON数组格式返回（3个对象，顺序：导课、小结、课后布置），不要输出JSON以外的内容：

[
  {{
    "phase": "导课",
    "duration": 5,
    "content": "（具体导课内容，包括复习什么、用什么方式引入本节）",
    "activity": "时间：5 min\\n\\n【雨课堂签到】\\n完成签到，呈现本节学习目标。\\n---\\n\\n【复习提问】\\n回顾上节课核心知识，自然引入本节。\\n1. 问：...\\n   预期答：...\\n---\\n\\n【导入新课】\\n通过...引出本节主题。\\n---\\n\\n",
    "related_slides": [...]
  }},
  {{
    "phase": "小结",
    "duration": 10,
    "content": "（课堂小结内容：核心知识点回顾、重难点强调）",
    "activity": "时间：10 min\\n\\n【课堂小结】\\n师生共同梳理本节核心知识点。\\n1. ...\\n2. ...\\n---\\n\\n【雨课堂测验】\\n推送5题，覆盖本节重点。\\n---\\n\\n【布置预习】\\n布置下节课预习任务。\\n---\\n\\n",
    "related_slides": []
  }},
  {{
    "phase": "课后布置",
    "duration": 5,
    "content": "（课后任务：作业题目、自学内容）",
    "activity": "时间：5 min\\n\\n【布置作业】\\n1. ...\\n2. ...\\n---\\n\\n【提示自学资源】\\n学习通/MOOC相关资源推荐。\\n---\\n\\n【下节课预告】\\n简要说明下节课内容。\\n---\\n\\n",
    "related_slides": []
  }}
]
"""
    raw = _call_api(provider, api_key, prompt, max_tokens=3000)
    return _extract_json_array(raw)


# ─────────────────────────────────────────────
# Stage 1.5：专项课程思政内容生成
# ─────────────────────────────────────────────

def _generate_ideological_content(
    provider: str, api_key: str,
    course_name: str, title: str,
    ppt_text: str,
    sections: list,
) -> dict:
    """
    分析全量PPT，生成2~3个与本节课紧密相关的思政点，分配到具体section。
    返回 {section_id: content_string}，用于 Stage 2b 精确插入。
    """
    sections_info = "\n".join(
        f"- {s.get('section_id', '')}: {s.get('title', '')}" for s in sections
    )
    prompt = f"""你是一位医学院校课程思政设计专家。请仔细阅读以下PPT全文，为本节课设计2~3个课程思政内容，分配到不同的知识模块中。

## 基本信息
- 课程名称：{course_name}
- 授课章节：{title}

## PPT完整内容
{ppt_text[:8000]}

## 本节一级知识模块（从以下列表中为每个思政点选择section_id）
{sections_info}

---

要求：
1. 思政内容必须与本节讲授的具体药物或知识点紧密相关，优先选用：
   - 本节所讲药物的发现/研发历史（真实科学家贡献、具体细节）
   - 本节药物相关的历史用药事件或教训（必须真实，明确说明与本节药物的关联）
   - 国家医药行业最新进展、国家政策（与本节内容直接相关）
   - 本节领域医药工作者的职业精神与伦理
2. 共生成2~3个思政点，每个分配到不同的一级标题下（不重复使用同一section_id）
3. 绝对不使用与本节内容无关的通用事例（若本节不讲反应停则不提反应停，若不讲青蒿素则不提屠呦呦）
4. 每个思政点内容完整具体，可直接用于课堂讲述（3~5句话）：
   - 先交代背景事件（具体、真实）
   - 再写教师引导语（"同学们，……这正是……精神的体现。"）
   - 自然融入，不生硬

请以JSON数组格式返回，不要输出JSON以外的内容：
[
  {{
    "section_id": "S1",
    "topic": "XX的发现历史",
    "content": "同学们，……（具体事件）……这正是……精神的体现。"
  }},
  {{
    "section_id": "S2",
    "topic": "XX相关历史事件",
    "content": "……"
  }}
]
"""
    try:
        raw = _call_api(provider, api_key, prompt, max_tokens=2000)
        items = _extract_json_array(raw)
        return {item["section_id"]: item["content"] for item in items}
    except Exception:
        return {}


def _expand_one_section(
    provider: str, api_key: str,
    course_name: str, title: str,
    section: dict,
    ppt_slides_text: str,
    key_points: str, difficult_points: str,
    total_sections: int = 3,
    ideological_content: str = "",
) -> dict:
    """
    Stage 2 正文单子节调用：
    - 左栏（content）：以AI知识库为主，按一级→二级层次展开知识内容
    - 右栏（activity）：精准设计时间分配、启发提问、课程思政、形成性评价、教学手段
    思政内容在右栏，不在左栏。
    ideological_content：Stage 1.5 预生成的思政内容；若为空则本节不设思政模块。
    """
    subsections_str = json.dumps(section.get("subsections", []), ensure_ascii=False, indent=2)

    if ideological_content:
        ideological_block = f"""## 课程思政内容（已预先生成，请直接使用）
以下内容经过专项设计，请在右栏（activity）合适位置以【课程思政】模块形式插入，
内容原文如下（可调整语序，但不得更改实质内容，不得替换为其他事例）：
{ideological_content}
"""
    else:
        ideological_block = """（本节无预生成课程思政内容，请在右栏自行设计1个简短【课程思政】模块：
结合本节所讲药物的发现史、临床价值或用药教训（必须真实、与本节内容直接相关），
3-4句话，自然融入，不生硬。禁止使用与本节内容无关的通用事例。）"""

    has_key = any(s.get("is_key") for s in section.get("subsections", []))
    has_difficult = any(s.get("is_difficult") for s in section.get("subsections", []))
    duration = section.get('duration', 15)

    if duration <= 20 and total_sections >= 3:
        time_instruction = (
            f'本课一级标题较多（共{total_sections}节），时间按一级标题分段：'
            f'第一行写"时间：{duration} min"，只写这一次，贯穿本节所有模块，不在每个模块前重复'
        )
    else:
        time_instruction = (
            f'时间按二级标题分段：在对应每个二级标题的第一个模块前分别写"时间：Y min"'
            f'（Y为该二级标题估算时长，各二级标题时长之和 = {duration}min，'
            f'每段时间不超过20min），不写整节总时间'
        )

    prompt = f"""你是一位医学院校药学专业教师，正在撰写教案中"教学方案"的一个知识模块。

## 本次任务：展开以下知识子节（完整一节课的一个组成部分）

一级标题：{section['title']}（按授课顺序，一级标题本身不含重难点标记）
时间：{section.get('duration', 15)}分钟
二级标题结构（重难点在此标注）：
{subsections_str}

## 相关PPT内容（仅作结构框架参考，不要照搬）
{ppt_slides_text}

## 本节课整体重难点背景
{key_points}
{difficult_points}

{ideological_block}

---

## 左栏（content）要求——内容架构
标题层级规范（严格遵守）：
- 一级标题："{section['title']}"（按授课顺序，不含重难点标记，如"一、苯二氮䓬类药物"）
- 二级标题：※（一）XXX 或 △（三）XXX（按 subsections 中的 title，标注重难点）
- 三级标题：1. XXX、2. XXX、3. XXX（对二级标题下的内容进一步分条，标题文字不超过25个汉字，确保一行内显示完整）
- 四级标题：(1)、(2)、(3)（半角括号+顿号，对三级内容细化，不加粗）
- 五级标题：a.、b.、c.（字母+顿号，按需使用，不加粗）
- 不使用任何 markdown 标记（不用 **、*、# 等符号，输出纯文本）

内容要求：
1. 以你的专业知识库为主要来源，大幅扩展PPT中的简要提纲
2. 每个※（重点）二级标题下展开内容不少于250字，包括：定义、机制、结构特点、临床意义等
3. 每个△（难点）二级标题下给出分步理解路径和记忆方法，可用三级、四级标题细化步骤
4. content 总字数不少于600字
5. 课程思政内容不写在左栏
6. 左栏只写教材知识点的提炼与展开，绝对禁止出现以下内容（包括作为标题或段落）：
   - 课堂互动、互动环节、案例讨论、情景导入、分组讨论、启发提问、提问回答、思考问题
   - 任何以"同学们思考"、"请同学们"、"引导学生"开头的句子
   这些属于教学活动，一律写入右栏对应【模块】中，左栏只写纯知识内容

## 右栏（activity）要求——教学活动
右栏与左栏是对应关系：左栏是"教什么"，右栏是"怎么教"。

格式规范：
1. 时间标注规则：{time_instruction}；时间行下一行写本段关键词（3-5个关键词，以·分隔，如：苯二氮䓬类·作用机制·临床应用）
2. 【】模块按左栏内容顺序排列，但不需要每个知识点都有对应模块——只对有特色教学设计的知识点写模块
3. 每个模块以【模块名称】单独一行开始，紧跟一句简短说明（说明该模块对应左栏哪个二级标题或知识点及教学方式，如：对应※（一）XXX，通过提问引导学生推导...），内容结束后写 "---" 再空两行
4. 模块内只用 1. 2. 3. 编号，不写括号时间注（如"（5min）"）
5. 常用模块：【重点讲解】【启发式提问】【难点突破】【知识拓展】【课程思政】【雨课堂测验】【形成性评价】等
6. {'※重点内容若设计提问，写出完整问题原文和预期学生答案' if has_key else ''}
7. {'△难点内容若设计突破，给出具体方法（分步讲解、类比、口诀等）' if has_difficult else ''}
8. {'【课程思政】模块：使用上方"课程思政内容"原文插入右栏，不得自行替换或重新创作' if ideological_content else '【课程思政】模块：按上方要求自行设计1个，内容必须与本节所讲药物直接相关'}
9. 末尾酌情设计一个形成性评价模块（雨课堂测验或课堂讨论）

示例结构（以某节 20min、含两个二级标题为例，※（一）普通讲授无需模块，※（二）和△（三）值得特别设计）：
时间：20 min

【启发式提问】      ← 对应左栏 ※（二），用提问引导理解
问：...
预期答：...
---

【难点突破】        ← 对应左栏 △（三），有特色的分步解析
1. 第一步：...
2. 第二步：...
---

【形成性评价】      ← 本节末尾
雨课堂推送3题，覆盖以上重难点。
---

---

请严格按照以下JSON格式返回单个对象，不要输出JSON以外的内容：

{{
  "section_id": "{section['section_id']}",
  "title": "{section['title']}",
  "duration": {section.get('duration', 15)},
  "content": "（左栏内容，≥600字，一级→二级→详细内容的层次结构，课程思政不写在此处）",
  "activity": "时间：{duration} min\\n\\n【重点讲解】\\n对应左栏※（一）的内容讲授...\\n1. ...\\n---\\n\\n【启发式提问】\\n问：...\\n预期答：...\\n---\\n\\n【形成性评价】\\n雨课堂推送X题，覆盖本节重难点。\\n---\\n\\n",
  "related_slides": {json.dumps(section.get('related_slides', []))}
}}
"""
    raw = _call_api(provider, api_key, prompt, max_tokens=5000)
    return _extract_json(raw)


# ─────────────────────────────────────────────
# 组装最终 teaching_plan
# ─────────────────────────────────────────────

def _assemble_teaching_plan(
    non_main_results: list,
    section_results: list,
    main_outline: dict,
    full_outline: list
) -> list:
    """
    将 Stage 2 各次调用结果组装为最终 teaching_plan 列表
    """
    # 建立 phase → 非正文结果 的映射
    non_main_map = {item["phase"]: item for item in non_main_results}

    teaching_plan = []
    for outline_item in full_outline:
        phase = outline_item["phase"]
        if phase == "正文":
            teaching_plan.append({
                "phase": "正文",
                "duration": outline_item.get("duration", 70),
                "content": "",
                "activity": "",
                "related_slides": [],
                "sections": section_results
            })
        else:
            if phase in non_main_map:
                teaching_plan.append(non_main_map[phase])
            else:
                # 容错：未找到则用大纲数据填充
                teaching_plan.append({
                    "phase": phase,
                    "duration": outline_item.get("duration", 5),
                    "content": "、".join(outline_item.get("knowledge_points", [])),
                    "activity": f"时间：{outline_item.get('duration', 5)}min",
                    "related_slides": outline_item.get("related_slides", []),
                    "sections": None
                })

    return teaching_plan


# ─────────────────────────────────────────────
# Stage 3：AI 智能匹配幻灯片截图
# ─────────────────────────────────────────────

_L3_PAT = re.compile(r'^\d+[\.．]\s*\S')


def _extract_l3_titles(content: str) -> list:
    """从 section content 文本中提取所有三级标题（精确文字列表）"""
    titles = []
    for line in content.split("\n"):
        stripped = line.strip()
        if _L3_PAT.match(stripped):
            titles.append(stripped)
    return titles


def _select_slide_images(
    provider: str, api_key: str,
    teaching_plan: list,
    ppt_data: dict,
) -> list:
    """
    Stage 3：根据各 section 最终生成的知识内容，AI 智能选出最匹配的幻灯片截图，
    精确到三级标题粒度。更新每个 section 的 image_assignments 字段。
    一次 API 调用完成所有 section 的分配。
    """
    # 1. 构建幻灯片摘要（只纳入有实质内容或有截图的页）
    slide_summaries = []
    for slide in ppt_data.get("slides", []):
        text = slide.get("text", "").strip()
        has_img = slide.get("has_image", False)
        if len(text) > 30 or has_img:
            slide_summaries.append({
                "index": slide["index"],
                "title": slide.get("title", ""),
                "text_preview": text[:120],
                "has_screenshot": has_img
            })

    if not slide_summaries:
        return teaching_plan

    # 2. 收集所有正文 sections 的信息（含精确的三级标题列表）
    sections_info = []
    for item in teaching_plan:
        for sec in (item.get("sections") or []):
            l3_titles = _extract_l3_titles(sec.get("content", ""))
            if not l3_titles:
                continue
            sections_info.append({
                "section_id": sec.get("section_id", ""),
                "title": sec.get("title", ""),
                "l3_titles": l3_titles,          # 精确三级标题列表，AI 必须从中选择
                "content_preview": sec.get("content", "")[:200]
            })

    if not sections_info:
        return teaching_plan

    # 3. 单次 API 调用，精确到三级标题
    prompt = f"""你是教案编辑助手。请根据各知识章节的三级标题，从PPT幻灯片列表中选出最合适的截图，
精确指定插在哪个三级标题下。

## PPT幻灯片候选列表
{json.dumps(slide_summaries, ensure_ascii=False, indent=2)}

## 需要匹配的知识章节（含三级标题列表）
{json.dumps(sections_info, ensure_ascii=False, indent=2)}

要求：
1. 只选 has_screenshot=true 的幻灯片（才有实际截图）
2. 排除标题页、章节分隔页、感谢页等无实质知识内容的页
3. l3_title 必须从该 section 的 l3_titles 列表中原文选取，不得修改文字
4. 每个 section 最多分配 2 张图，并非每个三级标题都需要配图——只选内容有明显视觉辅助价值的
5. 若某 section 无合适截图，image_assignments 填空数组

请严格按以下 JSON 数组格式返回，不要输出 JSON 以外的内容：
[
  {{
    "section_id": "S1",
    "image_assignments": [
      {{"l3_title": "1. 化学结构特点", "slide_index": 3}},
      {{"l3_title": "3. 临床应用", "slide_index": 7}}
    ]
  }},
  {{
    "section_id": "S2",
    "image_assignments": []
  }}
]
"""
    try:
        raw = _call_api(provider, api_key, prompt, max_tokens=1500)
        assignments = _extract_json_array(raw)
        assign_map = {a["section_id"]: a.get("image_assignments", []) for a in assignments}

        # 4. 将 image_assignments 写入对应 section
        for item in teaching_plan:
            for sec in (item.get("sections") or []):
                sid = sec.get("section_id", "")
                if sid in assign_map:
                    sec["image_assignments"] = assign_map[sid]
    except Exception:
        pass  # 失败时 image_assignments 不存在，template_filler 自动降级

    return teaching_plan


# ─────────────────────────────────────────────
# Stage 2c：课后习题专项生成
# ─────────────────────────────────────────────

def _generate_homework(
    provider: str, api_key: str,
    course_name: str, title: str,
    section_results: list,
    key_points: str, difficult_points: str,
) -> str:
    """
    Stage 2b 完成后调用：基于各节实际生成内容，出针对性课后习题。
    替换 Stage 1 的 homework 字段。
    """
    sections_summary = "\n".join(
        f"【{s.get('title', '')}】\n{s.get('content', '')[:400]}"
        for s in section_results
    )
    prompt = f"""你是一位医学院校药学专业教师，请根据以下本次课的实际教学内容，设计课后习题。

## 课程信息
- 课程：{course_name}
- 章节：{title}

## 本次课实际讲授内容摘要
{sections_summary}

## 重点与难点
{key_points}
{difficult_points}

---

请设计以下题型，以纯文本格式返回（不使用JSON，直接输出题目内容）：

1.（单选题，考查※重点知识）题目内容
A. 选项  B. 选项  C. 选项  D. 选项
答案：X
解析：简短说明为何选此项

2.（单选题，考查※重点知识）题目内容
A. 选项  B. 选项  C. 选项  D. 选项
答案：X
解析：简短说明

3.（单选题，考查※重点知识）题目内容
A. 选项  B. 选项  C. 选项  D. 选项
答案：X
解析：简短说明

4.（思考题，考查△难点）题目内容（要求学生综合分析，不能直接从书上找到答案）
参考答案要点：
（1）……
（2）……

5.（案例分析题，联系临床实际）描述一个真实的临床用药场景（100字以内），然后提问……
参考答案要点：
（1）……
（2）……

要求：
- 题目必须与本节所讲药物/知识点直接相关，不出现本节未讲的内容
- 单选题选项设计合理，干扰项有一定迷惑性
- 案例题场景真实，体现药学专业特点
"""
    try:
        return _call_api(provider, api_key, prompt, max_tokens=2000)
    except Exception:
        return ""


# ─────────────────────────────────────────────
# Stage 2d：教学拓展专项生成
# ─────────────────────────────────────────────

def _generate_teaching_expansion(
    provider: str, api_key: str,
    course_name: str, title: str,
    ppt_text: str,
    key_points: str, difficult_points: str,
) -> dict:
    """
    Stage 1 完成后调用：
    - brief：简短版，填入教学计划表格的"教学拓展"栏（每点1-2句，约120字）
    - ideological_blocks：详细版，作为课程思政素材插入教学方案右侧栏（2-3个，每个3-5句）
    失败时返回空dict，调用方保留 Stage 1 原始内容。
    """
    prompt = f"""你是一位医学院校药学专业教师，请为以下课程内容生成"教学拓展与课程思政"素材。

## 课程信息
- 课程：{course_name}
- 章节：{title}

## PPT内容摘要
{ppt_text[:4000]}

## 本节重点与难点
{key_points}
{difficult_points}

---

请以 JSON 格式返回，不输出 JSON 以外的内容：

{{
  "brief": "教学计划表格用简短版（每个拓展点1-2句话，共4点，合计约120字）：\\n1. 学科前沿进展：...\\n2. 历史背景：...\\n3. 临床实践延伸：...\\n4. 新医科展望：...",
  "ideological_blocks": [
    {{
      "topic": "（话题名称，如：苯二氮䓬类药物的发现历史）",
      "detail": "同学们，...（3-5句具体内容：先交代真实历史背景或临床事件，再写教师引导语，自然融入，不生硬，可直接在课堂讲述）"
    }},
    {{
      "topic": "...",
      "detail": "..."
    }}
  ]
}}

要求：
1. brief 每点1-2句，高度概括，适合填入表格
2. ideological_blocks 共2-3个，内容必须与本节具体药物/知识点直接相关
3. 优先选用：本节药物发现史、用药教训、临床启示、国家医药政策、科学家精神
4. 绝对不使用与本节内容无关的通用事例
5. 历史事件和科学家信息必须真实准确
"""
    try:
        raw = _call_api(provider, api_key, prompt, max_tokens=2000)
        return _extract_json(raw)
    except Exception:
        return {}


# ─────────────────────────────────────────────
# Stage 2e：自主学习资源专项生成
# ─────────────────────────────────────────────

def _generate_self_study_resources(
    provider: str, api_key: str,
    course_name: str, title: str,
    section_results: list,
    key_points: str,
) -> str:
    """
    Stage 2b 完成后调用：生成针对本节的具体自主学习资源包。
    替换 Stage 1 的 self_study_resources 字段。
    """
    section_titles = "\n".join(
        f"- {s.get('title', '')}" for s in section_results
    )
    prompt = f"""你是一位医学院校药学专业教师，请为以下课程内容设计课后自主学习资源包。

## 课程信息
- 课程：{course_name}
- 章节：{title}

## 本节一级知识模块
{section_titles}

## 重点内容
{key_points}

---

请生成以下三个板块的自主学习资源，以纯文本格式返回（不使用JSON）：

【课前预习】
1. 教材：《{course_name}》第X章第X节（说明具体章节名称），重点预习……
2. 预习问题：
   （1）……
   （2）……

【课后巩固】
1. 中国大学MOOC推荐：搜索"XXX"课程（说明具体课程名称和讲授本节内容的章节），观看……
2. 推荐检索文献：关键词"XXX；XXX"（给出2-3个英文检索词），在PubMed或知网检索近5年综述，重点了解……

【拓展阅读】
1. 专业书目：《XXX》（作者/主编，出版社），第X章介绍……（适合有余力的学生）
2. 行业动态：关注"XXX"官方网站/公众号（如CFDA官网、丁香园等），了解……

要求：
- 教材章节信息与本节内容对应（可根据课程名称合理推断章节位置）
- MOOC课程名称尽量具体，优先推荐国内知名高校的药学相关MOOC
- 文献检索词使用英文，具体且有检索价值
- 所有推荐内容必须与本节讲授的具体知识点直接相关
"""
    try:
        return _call_api(provider, api_key, prompt, max_tokens=1500)
    except Exception:
        return ""


# ─────────────────────────────────────────────
# 主任批语生成
# ─────────────────────────────────────────────

def _generate_director_comment(
    provider: str, api_key: str,
    course_name: str, title: str,
    key_points: str, ideological_summary: str,
) -> str:
    """
    生成主任批语：≤50字，仿宋三号，内容简短肯定，提及思政或启发式教学，结论准予授课。
    """
    prompt = f"""你是一位医学院系主任，需要为以下教案写一段批语。

课程名称：{course_name}
授课章节：{title}
教学重点：{key_points[:200]}
思政要素：{ideological_summary[:100]}

要求：
- 严格控制在50字以内（含标点）
- 内容简短肯定，自然流畅
- 提及课程思政或启发式教学至少一处
- 最后结论为：准予授课
- 直接输出批语文字，不加任何前缀或说明

示例格式（仅供参考，内容须与本课相关）：
教案内容充实，重难点突出，注重课程思政融入，启发式教学设计合理，教学目标明确，准予授课。"""
    try:
        result = _call_api(provider, api_key, prompt, max_tokens=200)
        # 确保不超过50字
        if len(result) > 55:
            result = result[:50]
        return result
    except Exception:
        return f"教案内容充实，重难点突出，融入课程思政元素，教学设计合理，准予授课。"


# ─────────────────────────────────────────────
# 主入口
# ─────────────────────────────────────────────

def generate_lesson_plan(
    api_key: str,
    course_name: str,
    teacher_name: str,
    title: str,
    department: str,
    college: str,
    students: str,
    classroom: str,
    teaching_date: str,
    ppt_data: dict,
    extra_notes: str = "",
    provider: str = "anthropic",
    user_references: str = "",
    progress_callback=None,
) -> dict:
    """
    三阶段生成完整教案：
    Stage 1：全量PPT → 框架 + 大纲（含 related_slides、subsections）
    Stage 2a：导课 + 小结 + 课后（1次调用）
    Stage 2b：正文各子节（每节1次调用）
    progress_callback(step_key, *extra)：每完成一次API调用时触发
    """
    def _cb(step_key, *extra):
        if callable(progress_callback):
            progress_callback(step_key, *extra)

    ppt_text = ppt_data.get("full_text", "") if ppt_data else ""

    # Stage 1
    result = _generate_structure(
        provider, api_key,
        course_name, teacher_name, title,
        department, college, students, classroom, teaching_date,
        ppt_text[:10000],  # 上限1万字
        extra_notes,
        user_references
    )
    _cb("structure")

    outline = result.pop("teaching_plan_outline", [])
    main_outline = next((p for p in outline if p["phase"] == "正文"), None)
    non_main_outline = [p for p in outline if p["phase"] != "正文"]
    sections = main_outline.get("sections", []) if main_outline else []

    # 容错：若 Stage 1 未返回 sections，构造单节降级
    if not sections and main_outline:
        sections = [{
            "section_id": "S1",
            "title": f"一、{title}",
            "duration": main_outline.get("duration", 70),
            "subsections": [{"title": f"※（一）{kp}", "is_key": True, "is_difficult": False, "knowledge_points": [kp]}
                            for kp in main_outline.get("knowledge_points", [])[:3]],
            "related_slides": main_outline.get("related_slides", []),
            "ideological_point": ""
        }]

    # 通知前端更新灯泡总数（固定步骤6个 + 每节1个）
    _cb("_total", 6 + len(sections))

    key_points = result.get("key_points", "")
    difficult_points = result.get("difficult_points", "")

    # Stage 2d：教学拓展专项生成（Stage 1 完成后立即执行，不依赖 Stage 2b）
    expansion_ideo_map = {}  # 来自教学拓展的思政素材
    try:
        expansion_result = _generate_teaching_expansion(
            provider, api_key,
            course_name, title,
            ppt_text[:4000],
            key_points, difficult_points,
        )
        if expansion_result:
            if "brief" in expansion_result:
                result["teaching_expansion"] = expansion_result["brief"]
            # 将 ideological_blocks 按顺序分配给各 section
            blocks = expansion_result.get("ideological_blocks", [])
            for i, block in enumerate(blocks):
                if i < len(sections):
                    sec_id = sections[i]["section_id"]
                    expansion_ideo_map[sec_id] = block.get("detail", "")
        _cb("expansion")
    except Exception:
        pass

    # Stage 1.5：专项课程思政内容生成（全量PPT分析，精准匹配本节内容）
    try:
        stage15_map = _generate_ideological_content(
            provider, api_key,
            course_name, title,
            ppt_text[:8000],
            sections,
        )
        _cb("ideological")
    except Exception:
        stage15_map = {}

    # 合并：Stage 2d（教学拓展衍生）优先，Stage 1.5 补充空缺
    ideological_map = {**stage15_map, **expansion_ideo_map}

    # Stage 2a：导课 + 小结 + 课后
    try:
        non_main_results = _expand_non_main_phases(
            provider, api_key,
            course_name, title,
            ppt_text[:1500],
            non_main_outline,
            key_points, difficult_points
        )
        _cb("non_main")
    except Exception:
        non_main_results = []

    # Stage 2b：正文各子节
    section_results = []
    total_sections = len(sections)
    for section in sections:
        try:
            slides_text = _extract_slides_text(ppt_data, section.get("related_slides", []))
            expanded = _expand_one_section(
                provider, api_key,
                course_name, title,
                section,
                slides_text,
                key_points, difficult_points,
                total_sections=total_sections,
                ideological_content=ideological_map.get(section.get("section_id", ""), ""),
            )
            # 确保 content 第一行是一级标题（AI 有时会漏写）
            sec_title = section.get("title", "")
            content = expanded.get("content", "")
            if sec_title and content and not content.lstrip().startswith(sec_title[:4]):
                expanded["content"] = sec_title + "\n" + content
            section_results.append(expanded)
            _cb("section", sec_title[:16])
        except Exception:
            # 容错：某节失败，填入占位文字
            section_results.append({
                "section_id": section.get("section_id", ""),
                "title": section.get("title", ""),
                "duration": section.get("duration", 15),
                "content": "[本节内容生成失败，请手动补充]",
                "activity": f"时间：{section.get('duration', 15)}min\n[本节活动设计生成失败，请手动补充]",
                "related_slides": section.get("related_slides", [])
            })

    # 组装 teaching_plan
    result["teaching_plan"] = _assemble_teaching_plan(
        non_main_results, section_results, main_outline, outline
    )

    # Stage 2c：课后习题专项生成（基于 Stage 2b 的实际内容出题）
    try:
        homework = _generate_homework(
            provider, api_key,
            course_name, title,
            section_results,
            key_points, difficult_points,
        )
        if homework:
            result["homework"] = homework
        _cb("homework")
    except Exception:
        pass

    # Stage 2e：自主学习资源专项生成（基于 Stage 2b 的实际模块）
    try:
        resources = _generate_self_study_resources(
            provider, api_key,
            course_name, title,
            section_results,
            key_points,
        )
        if resources:
            result["self_study_resources"] = resources
        _cb("resources")
    except Exception:
        pass

    # Stage 3：AI 智能匹配截图位置（在正文内容生成完毕后执行，匹配更准确）
    if ppt_data:
        result["teaching_plan"] = _select_slide_images(
            provider, api_key,
            result["teaching_plan"],
            ppt_data
        )
        _cb("images")

    # 主任批语：基于重难点和思政要素，生成≤50字批语
    try:
        ideological_summary = "; ".join([
            sec.get("ideological_content", "")[:50]
            for sec in result.get("teaching_plan", [])
            if sec.get("ideological_content")
        ])
        director_comment = _generate_director_comment(
            provider, api_key,
            course_name, title,
            result.get("key_points", ""),
            ideological_summary,
        )
        if director_comment:
            result["director_comment"] = director_comment
    except Exception:
        pass

    return result
