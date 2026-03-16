---
name: 教案生成器项目状态
description: 教案生成器项目的架构、已实现功能、文件结构、设计规范和注意事项
type: project
---

# 教案生成器项目

**项目路径：** `{OneDrive}\_My Projects\jiaoan-generator`
**Why:** 廉明明老师需要一键生成符合哈医大规范的 Word 格式教案，AI 内容质量需达到"能直接用"的水平。

---

## 文件结构

| 文件 | 职责 |
|------|------|
| `app.py` | Gradio Web 界面，流式进度显示，配置持久化 |
| `ai_generator.py` | 多阶段 AI 生成教案内容，返回完整 ai_content dict |
| `template_filler.py` | 将 ai_content 填入 Word 模板，输出 .docx |
| `ppt_parser.py` | 解析 .pptx / .pdf，返回 ppt_data |
| `template.docx` | 哈医大教案模板（6个表格） |
| `启动.bat` | 双击启动，GBK 编码 |
| `重启.bat` | 杀掉 7861 端口进程后重启，GBK 编码 |
| `outputs/` | 生成的教案文件存放目录 |
| `user_config.json` | 教师/教材信息持久化配置（含API密钥，已加入.gitignore，不上传） |
| `user_config.example.json` | 配置模板（无敏感信息，纳入版本库） |
| `README.md` | 傻瓜安装教程，显示在 GitHub 项目主页 |

当前总代码量约 **2335 行**（ai_generator 1056 + template_filler 651 + app 423 + ppt_parser 205）

---

## AI 生成阶段（ai_generator.py）

```
Stage 1:   _generate_structure()                → 1次（全局框架+教学大纲）
Stage 1.5: _generate_ideological_content()      → 1次（课程思政专项，分配到各节）
Stage 2d:  _generate_teaching_expansion()       → 1次（教学拓展：返回 brief + ideological_blocks）
Stage 2a:  _expand_non_main_phases()            → 1次（导课+小结+课后布置）
Stage 2b:  _expand_one_section() × N            → N次（每节正文详细展开）
Stage 2c:  _generate_homework()                 → 1次（课后习题，基于 Stage 2b 实际内容）
Stage 2e:  _generate_self_study_resources()     → 1次（自主学习资源包）
Stage 3:   _select_slide_images()               → 1次（AI 匹配截图位置）
主任批语:  _generate_director_comment()         → 1次（≤50字，结尾"准予授课"）

合计（N=4节）：约 11 次 API 调用
```

**progress_callback 机制：** 每次 API 调用完成后触发，app.py 通过 `queue.Queue` + `timeout=0.5` 每半秒刷新一次前端进度。

---

## Word 模板表格映射

| 变量 | 表格 | 内容 |
|------|------|------|
| t1 | tables[0] | 封面基本信息（楷体/小三15pt/水平+垂直居中） |
| t3 | tables[2] | 教学计划（教学目标、学情分析、重难点、教学拓展等） |
| t4 | tables[3] | 教学方案（两栏：左=内容架构+图片，右=教学活动） |
| t5 | tables[4] | 主板书设计 + 课后习题 |
| t6 | tables[5] | 自主学习资源 + 主任批语 |

- 课后习题：`t5.cell(1, 1)` — 使用 `_write_markdown_to_cell`
- 自主学习资源：`t6.cell(0, 2)` — 使用 `_write_markdown_to_cell`
- 主任批语：`tables[5].cell(1, 0)` — 仿宋/三号(16pt)/1.5倍行距/首行缩进32pt，写后自动删除多余空行保持结构：[0]标题/[1]批语/[2]空行/[3]签名

---

## 两栏结构规范（教学方案 t4）

| | 左栏（内容架构） | 右栏（教学活动） |
|---|---|---|
| 课程思政 | **绝对不出现** | 在右栏，与知识点融合 |
| 课堂互动 | **绝对不出现** | 在右栏 |
| 图片 | 紧跟对应小节文字后插入 | — |

---

## 标题层级规范（左栏）

| 级别 | 格式 | 加粗 | 样式 |
|------|------|------|------|
| 一级 | 一、二、三、或【导课】等阶段标题 | ✅ | 顶格，阶段标题加下划线 |
| 二级 | ※（一）/ △（二） | ✅ | 顶格 |
| 三级（标题模式，≤25字，正文节） | 1. 2. 3. | ✅ | 顶格+灰色底纹(D9D9D9) |
| 三级（段落模式，>25字或导课/小结/课后） | 1. 2. 3. | ❌ | 无底纹，普通正文 |
| 四级及以下 | (1)、(2)... | ❌ | 首行缩进2个全角字符 |

---

## 右栏格式规范

- `时间：X min` → 小四(12pt) + 加粗 + 斜体 + 下划线，只写一次
- 时间行下一行 → 关键词行（3-5个·分隔），斜体
- `【模块名称】` → 加粗，不加下划线
- 【模块名称】后第一段描述 → 斜体
- `---` → 渲染为横线

---

## Gradio UI（app.py）

- **配置持久化：** `user_config.json` 保存教师+教材信息，下次启动自动填入
- **进度显示（`gr.HTML`，每0.5s刷新）：**
  - 进度条：12min=100%，完成前最高99%，完成后跳绿色100%；右上角显示 MM:SS
  - 15个固定灯泡（26px），每次API调用亮一盏：灰→橙闪→绿
- **状态动画（`gr.HTML`）：** 生成中显示3个彩色跳跃方块（蓝圆角/橙圆形/绿圆角，节奏错位）；完成后显示绿色成功文字
- **支持的 AI 提供商：** `anthropic`（claude-opus-4-6）、`deepseek`（deepseek-chat）

---

## 中文字体设置要点

需同时设置两处，否则中文不生效：
```python
run.font.name = "仿宋"
_set_east_asia_font(run, "仿宋")   # 通过 XML rFonts 设置东亚字体
```

---

## 版本控制

- **GitHub 仓库：** https://github.com/lotuseeds/jiaoan-generator（公开）
- **当前稳定版本：** `v1.0.0`（2026-03-16 打标签）
- **分支：** `master`
- **git 代理配置：** `http://127.0.0.1:10808`（用户本地代理端口）
- **回退方式：** `git checkout v1.0.0`
- **新版本发布：** `git tag -a v1.x.x -m "描述"` + `git push --tags`

---

## 注意事项

- `重启.bat` 必须以 **GBK 编码**保存，否则 Windows 命令行乱码
- Claude Code hook 会把 `>nul` 改为 `>/dev/null`，bat 文件避免使用 `>nul`
- `_generate_teaching_expansion()` 返回 dict：`brief`（填教学计划表）+ `ideological_blocks`（分配到各节右栏思政内容）
- `_generate_director_comment()` 有降级：API失败时返回固定模板文字
- `pywin32` 是必须依赖（`win32com`/`pythoncom`），已补入 `requirements.txt`
- 启动方式：双击 `app.py` 最可靠（`启动.bat` 在未装依赖时一闪而过）
