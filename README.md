# 教案生成器

基于 AI 的教案自动生成工具，一键生成符合哈尔滨医科大学规范的 Word 格式教案。

**主要功能：**
- 上传 PPT（.pptx / .pdf），AI 自动解析并生成完整教案
- 多阶段 AI 生成：教学目标、学情分析、重难点、详细教学方案、课后习题、自主学习资源、主任批语
- 支持 Anthropic Claude 和 DeepSeek 两种 AI 提供商
- 授课节次可视化选择（点选当天第几节课，自动生成时间段）
- 生成过程中随机展示毛泽东语录

---

## 安装教程（Windows 傻瓜版）

### 第一步：安装 Python

1. 打开浏览器，访问 https://www.python.org/downloads/
2. 点击黄色大按钮 **"Download Python 3.x.x"**
3. 下载完成后双击安装包
4. ⚠️ **安装界面第一页，务必勾选底部的 "Add Python to PATH"**
5. 点击 **"Install Now"**，等待完成

### 第二步：下载项目代码

1. 点击本页右上角绿色按钮 **"Code"**，选择 **"Download ZIP"**
2. 下载完成后，右键 ZIP 文件 → 解压到你想放的位置

### 第三步：安装依赖

1. 进入解压出来的文件夹（里面能看到 `app.py` 等文件）
2. 在文件夹空白处，按住 **Shift + 右键** → 点击 **"在此处打开 PowerShell 窗口"**
3. 输入以下命令，回车：
   ```
   pip install -r requirements.txt
   ```
4. 等待安装完成（需要几分钟，最后出现 `Successfully installed` 即可）

### 第四步：配置 API Key

1. 在文件夹里新建一个文件，命名为 `server_config.json`
2. 用记事本打开，填入以下内容（选择你使用的 AI 提供商）：

   使用 Claude：
   ```json
   { "provider": "Anthropic (Claude)", "api_key": "sk-ant-..." }
   ```
   使用 DeepSeek：
   ```json
   { "provider": "DeepSeek", "api_key": "sk-..." }
   ```
3. 保存文件

### 第五步：启动程序

双击文件夹里的 **`app.py`**

稍等几秒，浏览器会自动打开，看到网页界面就说明成功了。

> 💡 **教师信息无需提前配置。** 在网页界面填写后，每次生成完成会自动保存到 `user_configs/<姓名>.json`，下次填写姓名后自动恢复。

---

## 常见问题

**pip 命令提示"不是内部命令"**
Python 安装时没有勾选 "Add Python to PATH"，重新安装一遍，注意勾选那个选项。

**网页没有自动打开**
手动在浏览器地址栏输入 `http://127.0.0.1:7861`

**局域网内其他电脑访问**
在同一 Wi-Fi 下，其他电脑浏览器输入运行本程序电脑的 IP 地址加端口，例如 `http://192.168.1.x:7861`

**DeepSeek 连接失败（WinError 10054）**
网络或防火墙问题，非程序 bug，配置代理后重试。

---

## server_config.json 字段说明

| 字段 | 说明 |
|------|------|
| `provider` | AI 提供商：`"Anthropic (Claude)"` 或 `"DeepSeek"` |
| `api_key` | 对应提供商的 API 密钥 |
