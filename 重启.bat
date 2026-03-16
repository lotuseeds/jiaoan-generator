@echo off
echo 正在关闭旧进程...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":7861 "') do (
    taskkill /f /pid %%a
)
timeout /t 2 >nul
echo 正在启动...
cd /d %~dp0
python app.py
pause
