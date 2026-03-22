# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 启动应用

```bash
python app.py
```

浏览器访问 `http://127.0.0.1:7861`。服务监听 `0.0.0.0:7861`，局域网内其他设备可访问。

## 安装依赖

```bash
pip install -r requirements.txt
```

核心依赖：`gradio`、`anthropic`、`openai`（用于 DeepSeek）、`python-docx`、`python-pptx`、`pymupdf`、`pywin32`（`win32com` 将 PPTX 导出为 PDF 截图所必需）。

## 配置文件

服务器配置保存在 `server_config.json`（不纳入版本库）：
```json
{ "provider": "Anthropic (Claude)", "api_key": "sk-..." }
```
支持的提供商：`"Anthropic (Claude)"`（映射到 `anthropic`）和 `"DeepSeek"`（映射到 `deepseek`）。

每位教师的个人配置在每次生成后自动保存到 `user_configs/<姓名>.json`。配置字段模板见 `user_config.example.json`。

## 整体架构

完整流程：上传 PPT → 解析 → 多阶段 AI 生成 → 填入 Word 模板 → 下载。

### 模块职责

| 文件 | 职责 |
|------|------|
| `app.py` | Gradio UI，通过 `queue.Queue` + 生成器实现流式进度，每位教师配置持久化 |
| `ai_generator.py` | 多阶段 AI 生成，返回 `ai_content` 字典 |
| `template_filler.py` | 将 `ai_content` 填入 `template.docx`（6 个表格），负责图片插入 |
| `ppt_parser.py` | 解析 `.pptx`/`.pdf`，返回含各页文字和图片的 `ppt_data` 字典 |
| `logger.py` | 每次运行在 `logs/` 目录下生成带时间戳的日志文件 |

### AI 生成阶段（`ai_generator.py`）

每个阶段为一次独立 API 调用，完成后触发 `progress_callback`：

1. **Stage 1** `_generate_structure()` — 输入完整 PPT 文本，输出包含全部教案字段和含幻灯片对应关系的大纲 JSON
2. **Stage 1.5** `_generate_ideological_content()` — 生成课程思政内容，分配到各节
3. **Stage 2d** `_generate_teaching_expansion()` — 返回 `{"brief": ..., "ideological_blocks": ...}`
4. **Stage 2a** `_expand_non_main_phases()` — 展开导课、小结、课后布置
5. **Stage 2b** `_expand_one_section()` x N — 逐节展开正文详细内容（N 次调用）
6. **Stage 2c** `_generate_homework()` — 基于 Stage 2b 实际内容生成课后习题
7. **Stage 2e** `_generate_self_study_resources()` — 生成自主学习资源包
8. **Stage 3** `_select_slide_images()` — AI 将 PPT 截图匹配到三级标题
9. `_generate_director_comment()` — 生成主任批语（≤50字，结尾"准予授课"）；API 失败时降级为固定模板文字

典型总计：4 节正文约 11 次 API 调用。

### Word 模板表格映射（`template_filler.py`）

`template.docx` 共 6 个表格，按索引访问：

| 变量 | 索引 | 内容 |
|------|------|------|
| t1 | `tables[0]` | 封面基本信息（楷体、15pt、水平+垂直居中） |
| t3 | `tables[2]` | 教学计划：目标、学情分析、重难点等 |
| t4 | `tables[3]` | 教学方案：两栏（左=内容+图片，右=教学活动） |
| t5 | `tables[4]` | 主板书设计 + 课后习题 |
| t6 | `tables[5]` | 自主学习资源 + 主任批语 |

具体 cell 地址：
- 课后习题：`t5.cell(1, 1)` — 使用 `_write_markdown_to_cell`
- 自主学习资源：`t6.cell(0, 2)` — 使用 `_write_markdown_to_cell`
- 主任批语：`tables[5].cell(1, 0)` — 仿宋/16pt/1.5倍行距/首行缩进32pt；写入后自动删多余空行，保持段落结构：[0]标题 / [1]批语 / [2]空行 / [3]签名

### 两栏内容约束（教学方案 t4）

| 内容类型 | 左栏（内容架构） | 右栏（教学活动） |
|---------|----------------|----------------|
| 课程思政 | **绝对不出现** | 与知识点融合写入 |
| 课堂互动 | **绝对不出现** | 写入 |
| PPT 截图 | 紧跟对应小节文字后插入 | — |

### PPT 解析策略（`ppt_parser.py`）

`.pptx`：优先通过 `win32com` + `fitz` 生成全页截图（需安装 PowerPoint）；失败则降级为提取内嵌图片（>200×200px）。

`.pdf`：直接用 `fitz` 以 150 DPI 渲染每页。

图片保存在源文件同目录下的 `_ppt_images/` 文件夹中。

### 左栏标题层级规范（`template_filler.py`）

| 级别 | 匹配模式 | 样式 |
|------|---------|------|
| 一级 | `【...】` 或 `一、二、三...` | 加粗、14pt、顶格 |
| 二级 | `※（一）` / `△（二）` | 加粗、14pt、顶格 |
| 三级（标题模式）| `1. 2. 3.` 且 ≤25 字，位于正文节 | 加粗、12pt、灰色底纹 D9D9D9 |
| 三级（段落模式）| `1. 2. 3.` 且 >25 字，或位于导课/小结/课后 | 不加粗、12pt、无底纹 |
| 四级及以下/正文 | 其余所有行 | 首行缩进2全角字符、12pt |

### 右栏格式规范

- `时间：X min` → 12pt 加粗斜体下划线
- 时间行的下一个非空行 → 关键词行（9pt 斜体）
- `【模块名称】` → 仅加粗，不加下划线
- `【模块名称】`后第一段描述 → 9pt 斜体
- `---` → 渲染为 `─` × 24

### 中文字体设置要点

必须同时设置西文字体名和东亚字体，否则中文不生效：
```python
run.font.name = "仿宋"
_set_east_asia_font(run, "仿宋")  # 通过 XML w:rFonts eastAsia 属性设置
```

### app.py 界面特性

#### 毛泽东语录（生成过程中滚动显示）

- `generate_mao_quotes(provider, api_key)` — 独立公开函数，在 `_run_generate` 中与本地 PPT 解析**并行**运行（`threading.Thread`）
- 生成 30 条语录，要求足够随机，避免高频引用，`max_tokens=3000`
- `state["quotes"]` 存储 API 返回的语录列表；未返回前使用 `_MAO_QUOTES` 硬编码备用列表（15 条）
- `_QUOTE_INTERVAL = 25`（秒/条）；`_current_quote_html()` 按时间戳轮换，渲染含 CSS `@keyframes quoteIn` 淡入动画
- 生成完成后通过 `while True: time.sleep(0.5); yield ...` 持续循环，语录继续滚动，下载按钮保持可见
- `_cb("_mao_quotes", quotes)` 特殊回调：存储语录 + 计入一个灯泡进度

#### 授课时间选择器

三个 Gradio 组件（列内顺序）：

| 组件 | 参数 | 作用 |
|------|------|------|
| `gr.Textbox` | `elem_id="jiaoan-date-input"`, label="授课日期" | 用户输入日期 |
| `gr.HTML(_PERIOD_SELECTOR_HTML)` | `label="授课节次（可多选）"` | 8 个可点击节次方块 |
| `gr.Textbox` | `elem_id="jiaoan-date-result"`, `interactive=False`, label="授课时间" | JS 自动填入结果 |

**JS 注入方式**：`demo.load(fn=None, js=_PERIOD_SELECTOR_JS)`（Gradio 6.x 会过滤 `gr.HTML` 内的 `<script>` 标签，必须用此方式）

**JS 核心逻辑**：
- 事件委托：`document.addEventListener('click', e => e.target.closest('.jiaoan-pb'))` — 不依赖初始化时机
- MutationObserver 监听"授课日期"输入框出现后绑定 `input` 事件
- 写入结果到 `#jiaoan-date-result textarea` 必须用 native setter：
  ```javascript
  Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,'value').set.call(el, val);
  el.dispatchEvent(new Event('input', {bubbles:true}));
  ```
- 节次时间表：1(8:00-8:45) 2(8:50-9:35) 3(9:55-10:40) 4(10:45-11:30) 5(13:30-14:15) 6(14:20-15:05) 7(15:25-16:10) 8(16:15-17:00)

## 关键约束

- `.bat` 文件必须以 **GBK 编码**保存，否则 Windows 命令行乱码
- `.bat` 文件中避免使用 `>nul`，Claude Code hook 会自动将其改为 `>/dev/null` 导致语法错误
- `demo.launch()` 中必须保留 `allowed_paths=[OUTPUT_DIR]`，否则 Gradio 6.x 安全检查会阻止文件下载
- `pywin32` 是硬性依赖，即使其导入在 try/except 内（PPTX 全页截图必须用到）
- DeepSeek API 报 `WinError 10054` 是网络/防火墙问题，不是代码 bug
- 进度条以 12 分钟 = 100% 校准；完成前最高显示 99%，完成后跳绿色 100%
- Gradio 6.x 会过滤 `gr.HTML` 内的 `<script>` 标签，自定义 JS 必须通过 `demo.load(fn=None, js=...)` 注入
- `gr.Blocks(css=...)` 在 Gradio 6.x 产生 UserWarning，CSS 应改传给 `demo.launch(css=...)`
- 生成结束后的 `while True` 循环每次 yield `gr.File` 必须带 `gr.update(value=out_path, visible=True)`，无参 `gr.update()` 会导致下载按钮消失
