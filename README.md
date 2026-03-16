# 教案生成器

基于 AI 的教案自动生成工具，一键生成符合医大规范的 Word 格式教案。

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

### 第四步：填写配置

1. 找到文件夹里的 `user_config.example.json`
2. 复制一份，重命名为 `user_config.json`（去掉 `.example`）
3. 用记事本打开，按格式填入教师信息和 API 密钥
4. 保存文件

### 第五步：启动程序

双击文件夹里的 **`app.py`**

稍等几秒，浏览器会自动打开，看到网页界面就说明成功了。

---

## 常见问题

**pip 命令提示"不是内部命令"**
Python 安装时没有勾选 "Add Python to PATH"，重新安装一遍，注意勾选那个选项。

**网页没有自动打开**
手动在浏览器地址栏输入 `http://127.0.0.1:7861`

---

## 配置说明

`user_config.json` 字段说明：

| 字段 | 说明 |
|------|------|
| `provider` | AI 提供商，填 `deepseek` 或 `anthropic` |
| `api_key` | 对应提供商的 API 密钥 |
| `teacher_name` | 授课教师姓名 |
| `professional_title` | 职称（如：副教授） |
| `department` | 教研室名称 |
| `college` | 学院名称 |
| `course_name` | 课程名称 |
| `textbook_name` | 教材名称 |
| `textbook_edition` | 版次（如：第6版） |
| `textbook_editor` | 主编姓名 |
| `textbook_publisher` | 出版社 |
| `textbook_year` | 出版年月 |
| `textbook_series` | 教材系列（如：规划教材） |
| `students` | 授课对象（如：2024级药物制剂本科1~3班） |
| `classroom` | 教室 |
