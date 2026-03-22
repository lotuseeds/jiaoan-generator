@echo off
cd /d %~dp0
echo 正在从 GitHub 获取最新代码...
git pull
if %errorlevel% == 0 (
    echo.
    echo 更新成功！
) else (
    echo.
    echo 更新失败，请检查网络连接是否正常
)
pause
