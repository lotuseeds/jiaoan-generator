"""
教案生成器 - Web 界面（多用户版）
运行方式：python app.py
"""
import os
import json
import queue
import random
import time
import threading
import gradio as gr
from datetime import datetime

from ppt_parser import parse_file
from ai_generator import generate_lesson_plan, generate_mao_quotes
from template_filler import fill_template
from logger import logger, log_system_info

TEMPLATE_PATH = os.path.join(os.path.dirname(__file__), "template.docx")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "outputs")
SERVER_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "server_config.json")
USER_CONFIGS_DIR = os.path.join(os.path.dirname(__file__), "user_configs")
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(USER_CONFIGS_DIR, exist_ok=True)

# ── 配置 ──
_USER_SAVE_KEYS = [
    "teacher_name", "professional_title", "department", "college", "course_name",
    "textbook_name", "textbook_edition", "textbook_editor",
    "textbook_publisher", "textbook_year", "textbook_series",
    "students", "classroom",
]

def _load_server_config() -> dict:
    try:
        if os.path.exists(SERVER_CONFIG_PATH):
            with open(SERVER_CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}

def _load_user_config(teacher_name: str) -> list:
    """根据教师姓名加载个人配置，返回12个字段值供 Gradio outputs 使用"""
    empty = [""] * 12
    if not teacher_name or not teacher_name.strip():
        return empty
    safe_name = teacher_name.strip().replace("/", "_").replace("\\", "_")
    config_path = os.path.join(USER_CONFIGS_DIR, f"{safe_name}.json")
    try:
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return [data.get(k, "") for k in _USER_SAVE_KEYS[1:]]
    except Exception:
        pass
    return empty

def _save_user_config(teacher_name: str, data: dict):
    if not teacher_name or not teacher_name.strip():
        return
    safe_name = teacher_name.strip().replace("/", "_").replace("\\", "_")
    config_path = os.path.join(USER_CONFIGS_DIR, f"{safe_name}.json")
    try:
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump({k: data.get(k, "") for k in _USER_SAVE_KEYS}, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

_server_cfg = _load_server_config()

# ── 进度灯泡显示 ──
_STEP_LABELS = {
    "ppt_parse":   "📂 解析PPT文件内容",
    "_mao_quotes": "📜 生成毛泽东语录",
    "structure":   "🗂️  解析教案整体结构框架",
    "expansion":   "📚 生成教学拓展与前沿内容",
    "ideological": "🎓 精选课程思政案例",
    "non_main":    "✏️  设计导课、小结与课后布置",
    "section":     "📝 展开正文知识内容",
    "homework":    "🎯 设计针对性课后习题",
    "resources":   "🔗 整理自主学习资源包",
    "images":      "🖼️  智能匹配PPT截图位置",
}

_WAIT_TIPS = [
    "☕ 稍等片刻，AI 正在认真备课...",
    "📖 AI 正在查阅医学文献和知识库...",
    "🔬 正在深度分析PPT内容结构...",
    "🧠 知识库检索中，请耐心等待...",
    "✍️  AI 教师正在奋笔疾书...",
]

_MAO_QUOTES = [
    "学习的敌人是自己的满足，要认真学习一点东西，必须从不自满开始。",
    "虚心使人进步，骄傲使人落后。",
    "读书是学习，使用也是学习，而且是更重要的学习。",
    "没有调查，就没有发言权。",
    "世界是你们的，也是我们的，但是归根结底是你们的。你们青年人朝气蓬勃，正在兴旺时期，好像早晨八九点钟的太阳。",
    "人是要有一点精神的。",
    "一切真知都是从直接经验发源的。",
    "教学必须联系实际。",
    "我们的教育方针，应该使受教育者在德育、智育、体育几方面都得到发展。",
    "不打无准备之仗，不打无把握之仗。",
    "理论与实践的统一，是马克思主义的一个最基本的原则。",
    "学而不思则罔，思而不学则殆。",
    "不懂得把理论应用于实践，这种理论有什么用处？",
    "我们必须继承一切优秀的文学艺术遗产，批判地吸收其中一切有益的东西。",
    "教师是人类灵魂的工程师。",
]

_TOTAL_SECONDS = 720  # 12分钟 = 100%

_LIGHTS_TOTAL = 15   # 固定显示15个灯泡，始终排满一行



def _render_quote(quote: str, source: str = "", done: bool = False) -> str:
    """渲染毛泽东语录卡片（生成中）或生成成功提示（完成后）"""
    if done:
        return '<div style="color:#52c41a;font-weight:600;font-size:15px;padding:10px 4px;">✅ 生成成功</div>'
    if not quote:
        return ""
    source_line = f'<div style="font-size:11px;color:#8c8c8c;margin-top:4px;text-align:right;">—— 毛泽东·{source}</div>' if source else '<div style="font-size:11px;color:#8c8c8c;margin-top:4px;text-align:right;">—— 毛泽东</div>'
    return f"""
<style>
@keyframes quoteIn {{
  from {{ opacity: 0; transform: translateY(12px); }}
  to   {{ opacity: 1; transform: translateY(0);    }}
}}
</style>
<div style="animation:quoteIn 2s ease-out forwards;border-left:3px solid #cf1322;
     background:#fffbe6;border-radius:0 6px 6px 0;padding:10px 14px;margin-top:8px;">
  <div style="font-family:楷体,'KaiTi',serif;font-size:14px;color:#262626;line-height:1.8;">
    「{quote}」
  </div>
  {source_line}
</div>
"""


def _render_progress(completed: int, total: int, step_msg: str, tip_idx: int,
                     elapsed_sec: float, done: bool = False) -> str:
    # 进度百分数
    if done:
        pct = 100
    elif elapsed_sec >= _TOTAL_SECONDS:
        pct = 99
    else:
        pct = min(99, int(elapsed_sec / _TOTAL_SECONDS * 100))

    # 已用时间
    mins = int(elapsed_sec) // 60
    secs = int(elapsed_sec) % 60
    time_str = f"{mins:02d}:{secs:02d}"

    bar_color = "#52c41a" if done else "#1677ff"

    # 灯泡行：固定 _LIGHTS_TOTAL 个，始终排满
    circles = []
    for i in range(_LIGHTS_TOTAL):
        if i < completed:
            circles.append('<span style="color:#52c41a;font-size:26px;margin-right:3px;" title="已完成">●</span>')
        elif i == completed and not done:
            circles.append('<span class="ai-blink" style="color:#fa8c16;font-size:26px;margin-right:3px;" title="进行中">●</span>')
        else:
            circles.append('<span style="color:#d9d9d9;font-size:26px;margin-right:3px;" title="等待中">●</span>')
    lights_row = "".join(circles)

    tip = "" if done else f'<div style="color:#8c8c8c;font-size:12px;margin-top:4px;">{_WAIT_TIPS[tip_idx % len(_WAIT_TIPS)]}</div>'

    return f"""
<style>
@keyframes ai-blink {{ 0%,100%{{opacity:1}} 50%{{opacity:0.2}} }}
.ai-blink {{ animation: ai-blink 1s ease-in-out infinite; }}
</style>
<div style="padding:10px 4px;">
  <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:4px;">
    <span style="font-size:12px;color:#595959;font-weight:500;">生成进度</span>
    <span style="font-size:13px;color:#595959;font-weight:600;">{time_str}</span>
  </div>
  <div style="background:#f0f0f0;border-radius:6px;height:26px;overflow:hidden;margin-bottom:10px;">
    <div style="width:{pct}%;height:100%;background:{bar_color};border-radius:6px;transition:width 0.4s ease;display:flex;align-items:center;justify-content:center;min-width:36px;">
      <span style="color:white;font-size:13px;font-weight:700;">{pct}%</span>
    </div>
  </div>
  <div style="margin-bottom:6px;line-height:1.4;">{lights_row}</div>
  <div style="color:#262626;font-size:13px;font-weight:500;margin-bottom:2px;">{step_msg}</div>
  {tip}
</div>
"""


# ── 核心生成函数 ──
def _run_generate(
    course_name, teacher_name, professional_title,
    department, college, students, classroom, teaching_date,
    title, textbook_name, textbook_edition, textbook_editor,
    textbook_publisher, textbook_year, textbook_series,
    extra_notes, user_references, ppt_file,
    progress_callback=None,
):
    def _cb(msg, *extra):
        if callable(progress_callback):
            progress_callback(msg, *extra)

    provider_map = {"Anthropic (Claude)": "anthropic", "DeepSeek": "deepseek"}
    provider = provider_map.get(_server_cfg.get("provider", "Anthropic (Claude)"), "anthropic")
    api_key = _server_cfg.get("api_key", "")

    if not api_key.strip():
        raise ValueError("服务器 API Key 未配置，请联系管理员")
    if not course_name.strip() or not title.strip():
        raise ValueError("课程名称和授课章节为必填项")

    # 解析PPT 与 毛泽东语录 并行运行
    ppt_data = {}
    quotes_done = threading.Event()

    def _fetch_quotes():
        try:
            quotes = generate_mao_quotes(provider, api_key)
            _cb("_mao_quotes", quotes)
        except Exception:
            logger.error("毛泽东语录生成失败，跳过", exc_info=True)
        finally:
            quotes_done.set()

    threading.Thread(target=_fetch_quotes, daemon=True).start()

    if ppt_file is not None:
        _cb("ppt_parse")
        ppt_data = parse_file(ppt_file)

    quotes_done.wait()  # 确保语录完成后再进入 Stage 1

    # AI 生成内容
    ai_content = generate_lesson_plan(
        api_key=api_key.strip(),
        course_name=course_name,
        teacher_name=teacher_name,
        title=title,
        department=department,
        college=college,
        students=students,
        classroom=classroom,
        teaching_date=teaching_date,
        ppt_data=ppt_data,
        extra_notes=extra_notes,
        provider=provider,
        user_references=user_references,
        progress_callback=progress_callback,
    )

    # 填充 Word 模板
    basic_info = {
        "course_name": course_name,
        "teacher_name": teacher_name,
        "professional_title": professional_title,
        "department": department,
        "college": college,
        "students": students,
        "classroom": classroom,
        "teaching_date": teaching_date,
        "title": title,
        "textbook_name": textbook_name,
        "textbook_edition": textbook_edition,
        "textbook_editor": textbook_editor,
        "textbook_publisher": textbook_publisher,
        "textbook_year": textbook_year,
        "textbook_series": textbook_series,
    }
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_title = title.replace("/", "-").replace("\\", "-")[:20]
    output_filename = f"教案_{safe_title}_{timestamp}.docx"
    output_path = os.path.join(OUTPUT_DIR, output_filename)
    fill_template(
        template_path=TEMPLATE_PATH,
        output_path=output_path,
        basic_info=basic_info,
        ai_content=ai_content,
        ppt_data=ppt_data,
    )

    # 保存用户配置
    _save_user_config(teacher_name, {
        "teacher_name": teacher_name,
        "professional_title": professional_title,
        "department": department,
        "college": college,
        "course_name": course_name,
        "textbook_name": textbook_name,
        "textbook_edition": textbook_edition,
        "textbook_editor": textbook_editor,
        "textbook_publisher": textbook_publisher,
        "textbook_year": textbook_year,
        "textbook_series": textbook_series,
        "students": students,
        "classroom": classroom,
    })

    return output_path, f"✅ 生成成功！文件已保存为：{output_filename}"


_QUOTE_INTERVAL = 25  # 每隔多少秒切换一条语录


# ── Gradio 流式生成器 ──
def generate_streaming(*args):
    q = queue.Queue()
    state = {
        "completed": 0,
        "total": 11,          # 初始估计，Stage 1 后更新
        "step_msg": "🚀 正在启动教案生成引擎...",
        "tip_idx": 0,
        "quote_idx": random.randint(0, len(_MAO_QUOTES) - 1),
        "quote_last_switch": time.time(),
        "quotes": [],         # Stage 1 返回后填入 API 生成的语录
    }

    def _current_quote_html():
        elapsed_since_switch = time.time() - state["quote_last_switch"]
        pool = state["quotes"] if state["quotes"] else None
        if pool:
            if elapsed_since_switch >= _QUOTE_INTERVAL:
                state["quote_idx"] = (state["quote_idx"] + 1) % len(pool)
                state["quote_last_switch"] = time.time()
            q = pool[state["quote_idx"] % len(pool)]
            return _render_quote(q.get("quote", ""), q.get("source", ""))
        else:
            if elapsed_since_switch >= _QUOTE_INTERVAL:
                state["quote_idx"] = (state["quote_idx"] + 1) % len(_MAO_QUOTES)
                state["quote_last_switch"] = time.time()
            return _render_quote(_MAO_QUOTES[state["quote_idx"] % len(_MAO_QUOTES)])

    def progress_callback(step_key, *extra):
        if step_key == "_total":
            state["total"] = extra[0] + 2  # +ppt_parse +structure（已完成）
            return
        if step_key == "_mao_quotes":
            if extra and isinstance(extra[0], list) and extra[0]:
                state["quotes"] = extra[0]
                state["quote_idx"] = random.randint(0, len(extra[0]) - 1)
                state["quote_last_switch"] = time.time()
        label = _STEP_LABELS.get(step_key, step_key)
        if step_key == "section" and extra:
            label = f"📝 展开正文：{extra[0]}..."
        state["step_msg"] = label
        state["completed"] += 1
        state["tip_idx"] += 1
        q.put("progress")

    def run():
        try:
            out_path, msg = _run_generate(*args, progress_callback=progress_callback)
            q.put(("done", out_path, msg))
        except Exception as e:
            logger.error("生成教案时发生未捕获异常", exc_info=True)
            q.put(("error", str(e)))

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    start_time = time.time()

    # 初始渲染
    display = _render_progress(0, state["total"], state["step_msg"], 0, 0)
    yield gr.update(visible=False), "", display, gr.update(visible=False), _current_quote_html()

    while True:
        elapsed = time.time() - start_time
        try:
            item = q.get(timeout=0.5)   # 每0.5秒刷新一次时间
        except queue.Empty:
            # 没有新进度事件，只更新时间和进度条
            display = _render_progress(
                state["completed"], state["total"],
                state["step_msg"], state["tip_idx"], elapsed
            )
            yield gr.update(visible=False), "", display, gr.update(visible=False), _current_quote_html()
            continue

        elapsed = time.time() - start_time
        if item == "progress":
            display = _render_progress(
                state["completed"], state["total"],
                state["step_msg"], state["tip_idx"], elapsed
            )
            yield gr.update(visible=False), "", display, gr.update(visible=False), _current_quote_html()
        elif isinstance(item, tuple) and item[0] == "done":
            display = _render_progress(
                state["total"], state["total"],
                "✅ 所有步骤完成，教案已生成！", 0, elapsed, done=True
            )
            status_done = f'<div style="color:#52c41a;font-weight:600;font-size:14px;padding:4px 0;">✅ {item[2]}</div>'
            out_path = item[1]
            yield gr.update(value=out_path, visible=True), status_done, display, gr.update(visible=False), _current_quote_html()
            # 生成完成后继续滚动语录
            while True:
                time.sleep(0.5)
                yield gr.update(value=out_path, visible=True), gr.update(), gr.update(), gr.update(), _current_quote_html()
        elif isinstance(item, tuple) and item[0] == "error":
            display = _render_progress(
                state["completed"], state["total"],
                f"❌ 生成失败：{item[1]}", 0, elapsed
            )
            error_content = (
                f'<div style="border:1px solid #ffccc7;background:#fff2f0;border-radius:8px;'
                f'padding:16px;color:#cf1322;font-size:14px;line-height:1.6;">'
                f'❌ <strong>生成失败</strong><br>{item[1]}</div>'
            )
            yield gr.update(visible=False), "", display, gr.update(value=error_content, visible=True), ""
            break


# ── 课节选择器 ──
_PERIOD_SELECTOR_HTML = """
<style>
.jiaoan-pb {
  width:38px;height:38px;border:1.5px solid #d9d9d9;border-radius:6px;
  display:flex;align-items:center;justify-content:center;cursor:pointer;
  font-size:15px;font-weight:600;color:#595959;user-select:none;
  transition:background 0.15s,color 0.15s,border-color 0.15s;
}
.jiaoan-pb:hover { border-color:#1677ff;color:#1677ff; }
.jiaoan-pb.jiaoan-sel { background:#1677ff;color:#fff;border-color:#1677ff; }
</style>
<div style="display:flex;gap:6px;" id="jiaoan-period-blocks">
  <div class="jiaoan-pb" data-p="1" data-s="8:00"  data-e="8:45">1</div>
  <div class="jiaoan-pb" data-p="2" data-s="8:50"  data-e="9:35">2</div>
  <div class="jiaoan-pb" data-p="3" data-s="9:55"  data-e="10:40">3</div>
  <div class="jiaoan-pb" data-p="4" data-s="10:45" data-e="11:30">4</div>
  <div class="jiaoan-pb" data-p="5" data-s="13:30" data-e="14:15">5</div>
  <div class="jiaoan-pb" data-p="6" data-s="14:20" data-e="15:05">6</div>
  <div class="jiaoan-pb" data-p="7" data-s="15:25" data-e="16:10">7</div>
  <div class="jiaoan-pb" data-p="8" data-s="16:15" data-e="17:00">8</div>
</div>
"""

_PERIOD_SELECTOR_JS = """
() => {
  if (window._jiaoanPeriodInit) return [];
  window._jiaoanPeriodInit = true;

  var _sel = new Set();

  function _writeResult() {
    var sorted = Array.from(_sel).sort(function(a, b) { return a - b; });
    var result = '';
    if (sorted.length > 0) {
      var fb = document.querySelector('#jiaoan-period-blocks .jiaoan-pb[data-p="' + sorted[0] + '"]');
      var lb = document.querySelector('#jiaoan-period-blocks .jiaoan-pb[data-p="' + sorted[sorted.length - 1] + '"]');
      if (!fb || !lb) return;
      var pStr = sorted.length === 1
        ? '第' + sorted[0] + '节'
        : '第' + sorted[0] + '-' + sorted[sorted.length - 1] + '节';
      var tStr = fb.dataset.s + '-' + lb.dataset.e;
      var dayEl = document.querySelector('#jiaoan-date-input textarea');
      var day = (dayEl && dayEl.value.trim()) ? dayEl.value.trim() + ' ' : '';
      result = day + pStr + '（' + tStr + '）';
    }
    /* 写入隐藏 Gradio textbox 供 Python 读取 */
    var target = document.querySelector('#jiaoan-date-result textarea');
    if (target) {
      var setter = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value').set;
      setter.call(target, result);
      target.dispatchEvent(new Event('input', { bubbles: true }));
    }
  }

  document.addEventListener('click', function(e) {
    var b = e.target.closest ? e.target.closest('.jiaoan-pb') : null;
    if (!b) return;
    var p = parseInt(b.dataset.p);
    if (_sel.has(p)) _sel.delete(p); else _sel.add(p);
    document.querySelectorAll('.jiaoan-pb').forEach(function(x) {
      x.classList.toggle('jiaoan-sel', _sel.has(parseInt(x.dataset.p)));
    });
    _writeResult();
  });

  function _bindDateInput() {
    var el = document.querySelector('#jiaoan-date-input textarea');
    if (el && !el._jbDate) { el._jbDate = true; el.addEventListener('input', _writeResult); }
  }
  var _obs = new MutationObserver(_bindDateInput);
  _obs.observe(document.body, { childList: true, subtree: true });
  _bindDateInput();

  return [];
}
"""

# ── 界面布局 ──
with gr.Blocks(title="智能教案生成器") as demo:

    gr.Markdown("""
    # 📚 智能教案生成器
    **哈尔滨医科大学** · 基于 AI 大模型 · 自动生成符合规范的教案 Word 文件
    ---
    """)

    with gr.Row():
        with gr.Column(scale=1):
            gr.Markdown("### 👩‍🏫 教师信息（每位老师只需填一次）")
            teacher_name = gr.Textbox(label="任课教师姓名", placeholder="例：大油条")
            professional_title = gr.Textbox(label="教学职称", placeholder="例：助教")
            department = gr.Textbox(label="教研室", placeholder="例：药物化学教研室")
            college = gr.Textbox(label="学院", placeholder="例：药学院")
            course_name = gr.Textbox(label="课程名称", placeholder="例：药物化学")

            gr.Markdown("### 📖 教材信息")
            textbook_name = gr.Textbox(label="教材名称", placeholder="例：药物化学")
            textbook_edition = gr.Textbox(label="版次", placeholder="例：第九版")
            textbook_editor = gr.Textbox(label="主编", placeholder="例：徐云根")
            textbook_publisher = gr.Textbox(label="出版社", placeholder="例：人民卫生出版社")
            textbook_year = gr.Textbox(label="出版时间", placeholder="例：2023年07月")
            textbook_series = gr.Textbox(label="教材系列", placeholder='例："十四五"规划')

            gr.Markdown("### 📅 本次授课信息")
            title = gr.Textbox(
                label="授课章节/主题 *",
                placeholder="例：第四章 第一节 镇静催眠药",
            )
            students = gr.Textbox(label="教学对象", placeholder="例：2024级药物分析本科1-2班")
            classroom = gr.Textbox(label="教学地点", placeholder="例：B402中教室")
            teaching_date_day = gr.Textbox(
                label="授课日期",
                placeholder="例：2026年3月22日",
                elem_id="jiaoan-date-input",
            )
            gr.HTML(_PERIOD_SELECTOR_HTML, label="授课节次（可多选）")
            teaching_date = gr.Textbox(
                label="授课时间",
                elem_id="jiaoan-date-result",
                interactive=False,
                placeholder="选择日期和节次后自动生成",
            )

        with gr.Column(scale=1):
            gr.Markdown("### 📎 PPT 上传（推荐）")
            ppt_file = gr.File(
                label="上传本次授课PPT（.pptx 或 .pdf）",
                file_types=[".pptx", ".pdf"],
            )

            gr.Markdown("### 💬 补充说明（选填）")
            extra_notes = gr.Textbox(
                label="其他要求或说明",
                placeholder="例：本次课需要重点介绍地西泮的代谢路径，思政部分结合屠呦呦青蒿素研发故事",
                lines=3,
            )

            gr.Markdown("### 📚 参考文献（选填）")
            user_references = gr.Textbox(
                label="参考文献",
                placeholder="每行一条，可直接粘贴原始文献信息，AI将自动整理为标准格式。若不填写，AI将自动生成至少5条相关文献。",
                lines=5,
            )

            generate_btn = gr.Button("🚀 一键生成教案", variant="primary", size="lg")
            lights_display = gr.HTML(value="")
            quote_html = gr.HTML(value="")
            status_html = gr.HTML(value="")
            output_file = gr.File(label="📥 下载生成的教案", visible=False)
            error_html = gr.HTML(value="", visible=False)

    teacher_name.change(
        fn=_load_user_config,
        inputs=[teacher_name],
        outputs=[
            professional_title, department, college, course_name,
            textbook_name, textbook_edition, textbook_editor,
            textbook_publisher, textbook_year, textbook_series,
            students, classroom,
        ],
    )

    generate_btn.click(
        fn=generate_streaming,
        inputs=[
            course_name, teacher_name, professional_title,
            department, college, students, classroom, teaching_date,
            title, textbook_name, textbook_edition, textbook_editor,
            textbook_publisher, textbook_year, textbook_series,
            extra_notes, user_references, ppt_file,
        ],
        outputs=[output_file, status_html, lights_display, error_html, quote_html],
    )

    demo.load(fn=None, js=_PERIOD_SELECTOR_JS)

    gr.Markdown("""
    ---
    > 💡 **提示**：每位教师的信息会在生成后自动保存。下次使用时，填写姓名后会自动恢复上次的信息。
    > 生成的教案文件保存在 `outputs/` 文件夹中，可直接用 Word 打开修改。
    """)


if __name__ == "__main__":
    log_system_info()
    demo.queue(max_size=20, default_concurrency_limit=10)
    demo.launch(
        server_name="0.0.0.0",
        server_port=7861,
        inbrowser=False,
        share=False,
        theme=gr.themes.Soft(),
        allowed_paths=[OUTPUT_DIR],
    )
