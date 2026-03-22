---
name: 教案生成器项目状态
description: 教案生成器项目的背景目标、版本控制信息和运营注意事项（架构和格式规范见 CLAUDE.md）
type: project
---

# 教案生成器项目

**项目路径：** `{OneDrive}\_My Projects\jiaoan-generator`
**Why：** 廉明明老师需要一键生成符合哈医大规范的 Word 格式教案，AI 内容质量需达到"能直接用"的水平。

---

## 版本控制

- **GitHub 仓库：** https://github.com/lotuseeds/jiaoan-generator（公开）
- **当前稳定版本：** `v1.0.0`（2026-03-16 打标签）
- **最新提交：** `208892c`（2026-03-20）
- **分支：** `master`
- **git push 代理：** `http://127.0.0.1:10808`（push 时用 `-c http.proxy=...`）
- **更新.bat：** 直接 `git pull`，不带代理
- **回退方式：** `git checkout v1.0.0`
- **新版本发布：** `git tag -a v1.x.x -m "描述"` + `git push --tags`

---

## 当前代码量

约 **2445 行**（ai_generator 1076 + template_filler 651 + app 425 + ppt_parser 205 + logger 88）

---

## 运营注意事项

- 启动方式：双击 `app.py` 最可靠；`启动.bat` 在未装依赖时会一闪而过
- 配置持久化：`user_configs/<姓名>.json`（多用户，每位教师单独一个文件）；`server_config.json` 保存 API Key
- 其他电脑上 DeepSeek API 连接失败（`WinError 10054`）是网络/防火墙问题，非代码 bug，需配置代理
- 日志在 `logs/` 目录，记录每次 API 调用编号/耗时/堆栈，跨电脑排查问题时先看日志
