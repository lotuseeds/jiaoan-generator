"""
教案生成器 - Web 界面
运行方式：python app.py
"""
import os
import json
import queue
import time
import threading
import gradio as gr
from datetime import datetime

from ppt_parser import parse_file
from ai_generator import generate_lesson_plan
from template_filler import fill_template

TEMPLATE_PATH = os.path.join(os.path.dirname(__file__), "template.docx")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "outputs")
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "user_config.json")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ── 配置持久化 ──
_SAVE_KEYS = [
    "provider", "api_key",
    "teacher_name", "professional_title", "department", "college", "course_name",
    "textbook_name", "textbook_edition", "textbook_editor",
    "textbook_publisher", "textbook_year", "textbook_series",
    "students", "classroom",
]

def _load_config() -> dict:
    try:
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}

def _save_config(data: dict):
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump({k: data[k] for k in _SAVE_KEYS if k in data}, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

_cfg = _load_config()

# ── 进度灯泡显示 ──
_STEP_LABELS = {
    "ppt_parse":   "📂 解析PPT文件内容",
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

_TOTAL_SECONDS = 720  # 12分钟 = 100%


_LIGHTS_TOTAL = 15   # 固定显示15个灯泡，始终排满一行

_STATUS_RUNNING_HTML = """
<style>
@keyframes blk-a {
  0%,100% { transform: translateY(0px)   rotate(0deg);   }
  20%      { transform: translateY(-14px) rotate(-8deg);  }
  40%      { transform: translateY(0px)   rotate(0deg);   }
  60%      { transform: translateY(-6px)  rotate(4deg);   }
  80%      { transform: translateY(0px)   rotate(0deg);   }
}
@keyframes blk-b {
  0%,100% { transform: translateY(0px)   rotate(0deg);   }
  15%      { transform: translateY(-8px)  rotate(6deg);   }
  35%      { transform: translateY(0px)   rotate(0deg);   }
  55%      { transform: translateY(-16px) rotate(-5deg);  }
  75%      { transform: translateY(0px)   rotate(0deg);   }
}
@keyframes blk-c {
  0%,100% { transform: translateY(0px)   rotate(0deg);   }
  25%      { transform: translateY(-18px) rotate(10deg);  }
  45%      { transform: translateY(0px)   rotate(0deg);   }
  65%      { transform: translateY(-7px)  rotate(-6deg);  }
  85%      { transform: translateY(0px)   rotate(0deg);   }
}
@keyframes col-a {
  0%,100% { background: #1677ff; }
  50%      { background: #40a9ff; }
}
@keyframes col-b {
  0%,100% { background: #fa8c16; }
  50%      { background: #ffc53d; }
}
@keyframes col-c {
  0%,100% { background: #52c41a; }
  50%      { background: #95de64; }
}
</style>
<div style="display:flex;align-items:flex-end;gap:8px;padding:8px 0 4px 0;">
  <span style="display:inline-block;width:20px;height:20px;border-radius:3px;
        animation:blk-a 1.1s ease-in-out infinite, col-a 1.1s ease-in-out infinite;"></span>
  <span style="display:inline-block;width:22px;height:22px;border-radius:50%;
        animation:blk-b 1.3s ease-in-out 0.15s infinite, col-b 1.3s ease-in-out 0.15s infinite;"></span>
  <span style="display:inline-block;width:18px;height:18px;border-radius:6px;
        animation:blk-c 0.95s ease-in-out 0.3s infinite, col-c 0.95s ease-in-out 0.3s infinite;"></span>
  <span style="font-size:13px;color:#595959;margin-left:6px;padding-bottom:3px;">AI 正在生成教案，请稍候…</span>
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
    provider, api_key, course_name, teacher_name, professional_title,
    department, college, students, classroom, teaching_date,
    title, textbook_name, textbook_edition, textbook_editor,
    textbook_publisher, textbook_year, textbook_series,
    extra_notes, user_references, ppt_file,
    progress_callback=None,
):
    def _cb(msg, *extra):
        if callable(progress_callback):
            progress_callback(msg, *extra)

    if not api_key.strip():
        raise ValueError("请填写 API Key")
    if not course_name.strip() or not title.strip():
        raise ValueError("课程名称和授课章节为必填项")

    # 解析PPT
    ppt_data = {}
    if ppt_file is not None:
        _cb("ppt_parse")
        ppt_data = parse_file(ppt_file)

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

    # 保存配置
    _save_config({
        "provider": provider,
        "api_key": api_key.strip(),
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


# ── Gradio 流式生成器 ──
def generate_streaming(provider_label, api_key, *args):
    provider_map = {"Anthropic (Claude)": "anthropic", "DeepSeek": "deepseek"}
    provider = provider_map.get(provider_label, "anthropic")

    q = queue.Queue()
    state = {
        "completed": 0,
        "total": 11,          # 初始估计，Stage 1 后更新
        "step_msg": "🚀 正在启动教案生成引擎...",
        "tip_idx": 0,
    }

    def progress_callback(step_key, *extra):
        if step_key == "_total":
            # Stage 1 完成后，已知正文节数，更新总数
            # 总数 = ppt_parse(1) + structure(1) + expansion(1) + ideological(1)
            #        + non_main(1) + sections(N) + homework(1) + resources(1) + images(1) = N+8
            # 但 _total 传入的是 ai_generator 内部的 6+N，再加上 ppt_parse 和 structure = 8+N
            state["total"] = extra[0] + 2  # +ppt_parse +structure（已完成）
            return
        label = _STEP_LABELS.get(step_key, step_key)
        if step_key == "section" and extra:
            label = f"📝 展开正文：{extra[0]}..."
        state["step_msg"] = label
        state["completed"] += 1
        state["tip_idx"] += 1
        q.put("progress")

    def run():
        try:
            out_path, msg = _run_generate(provider, api_key, *args,
                                          progress_callback=progress_callback)
            q.put(("done", out_path, msg))
        except Exception as e:
            q.put(("error", str(e)))

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    start_time = time.time()

    # 初始渲染
    display = _render_progress(0, state["total"], state["step_msg"], 0, 0)
    yield None, _STATUS_RUNNING_HTML, display

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
            yield None, _STATUS_RUNNING_HTML, display
            continue

        elapsed = time.time() - start_time
        if item == "progress":
            display = _render_progress(
                state["completed"], state["total"],
                state["step_msg"], state["tip_idx"], elapsed
            )
            yield None, _STATUS_RUNNING_HTML, display
        elif isinstance(item, tuple) and item[0] == "done":
            display = _render_progress(
                state["total"], state["total"],
                "✅ 所有步骤完成，教案已生成！", 0, elapsed, done=True
            )
            status_done = f'<div style="color:#52c41a;font-weight:600;font-size:14px;padding:4px 0;">✅ {item[2]}</div>'
            yield item[1], status_done, display
            break
        elif isinstance(item, tuple) and item[0] == "error":
            display = _render_progress(
                state["completed"], state["total"],
                f"❌ 生成失败：{item[1]}", 0, elapsed
            )
            status_err = f'<div style="color:#f5222d;font-weight:600;font-size:14px;padding:4px 0;">❌ 生成失败：{item[1]}</div>'
            yield None, status_err, display
            break


# ── 界面布局 ──
with gr.Blocks(title="智能教案生成器") as demo:

    gr.Markdown("""
    # 📚 智能教案生成器
    **哈尔滨医科大学** · 基于 Claude AI · 自动生成符合规范的教案 Word 文件
    ---
    """)

    with gr.Row():
        with gr.Column(scale=1):
            gr.Markdown("### 🔑 API 配置")
            provider = gr.Radio(
                choices=["Anthropic (Claude)", "DeepSeek"],
                value=_cfg.get("provider", "Anthropic (Claude)"),
                label="AI 提供商",
            )
            api_key = gr.Textbox(
                label="API Key",
                placeholder="sk-ant-api03-...",
                value=_cfg.get("api_key", ""),
                type="password",
            )

            def update_placeholder(choice):
                if choice == "DeepSeek":
                    return gr.Textbox(placeholder="sk-...")
                return gr.Textbox(placeholder="sk-ant-api03-...")

            provider.change(fn=update_placeholder, inputs=provider, outputs=api_key)

            gr.Markdown("### 👩‍🏫 教师信息（每位老师只需填一次）")
            teacher_name = gr.Textbox(label="任课教师姓名", placeholder="例：廉明明",
                                      value=_cfg.get("teacher_name", ""))
            professional_title = gr.Textbox(label="教学职称", placeholder="例：副教授",
                                            value=_cfg.get("professional_title", ""))
            department = gr.Textbox(label="教研室", placeholder="例：药物化学教研室",
                                    value=_cfg.get("department", ""))
            college = gr.Textbox(label="学院", placeholder="例：大庆校区 药学院",
                                 value=_cfg.get("college", ""))
            course_name = gr.Textbox(label="课程名称", placeholder="例：药物化学",
                                     value=_cfg.get("course_name", ""))

            gr.Markdown("### 📖 教材信息")
            textbook_name = gr.Textbox(label="教材名称", placeholder="例：药物化学",
                                       value=_cfg.get("textbook_name", ""))
            textbook_edition = gr.Textbox(label="版次", placeholder="例：第九版",
                                          value=_cfg.get("textbook_edition", ""))
            textbook_editor = gr.Textbox(label="主编", placeholder="例：徐云根",
                                         value=_cfg.get("textbook_editor", ""))
            textbook_publisher = gr.Textbox(label="出版社", placeholder="例：人民卫生出版社",
                                            value=_cfg.get("textbook_publisher", ""))
            textbook_year = gr.Textbox(label="出版时间", placeholder="例：2023年07月",
                                       value=_cfg.get("textbook_year", ""))
            textbook_series = gr.Textbox(label="教材系列", placeholder='例："十四五"规划',
                                         value=_cfg.get("textbook_series", ""))

        with gr.Column(scale=1):
            gr.Markdown("### 📅 本次授课信息")
            title = gr.Textbox(
                label="授课章节/主题 *",
                placeholder="例：第四章 第一节 镇静催眠药",
            )
            students = gr.Textbox(label="教学对象", placeholder="例：2024级药物分析本科1-2班",
                                  value=_cfg.get("students", ""))
            classroom = gr.Textbox(label="教学地点", placeholder="例：B402中教室",
                                   value=_cfg.get("classroom", ""))
            teaching_date = gr.Textbox(
                label="授课时间",
                placeholder="例：2025年11月4日 8:00-9:35",
            )

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
            status_html = gr.HTML(value="")
            lights_display = gr.HTML(value="")
            output_file = gr.File(label="📥 下载生成的教案")

    generate_btn.click(
        fn=generate_streaming,
        inputs=[
            provider, api_key, course_name, teacher_name, professional_title,
            department, college, students, classroom, teaching_date,
            title, textbook_name, textbook_edition, textbook_editor,
            textbook_publisher, textbook_year, textbook_series,
            extra_notes, user_references, ppt_file,
        ],
        outputs=[output_file, status_html, lights_display],
    )

    gr.Markdown("""
    ---
    > 💡 **提示**：教师信息、教材信息会在每次生成后自动保存，下次启动无需重填。每次只需填写授课章节和上传PPT即可。
    > 生成的教案文件保存在 `outputs/` 文件夹中，可直接用 Word 打开修改。
    """)


if __name__ == "__main__":
    demo.launch(
        server_name="0.0.0.0",
        server_port=7861,
        inbrowser=True,
        share=False,
        theme=gr.themes.Soft(),
    )
