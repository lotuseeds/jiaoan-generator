@echo off
cd /d %~dp0
echo 正在从 GitHub 拉取最新代码...
git -c http.proxy=http://127.0.0.1:10808 pull
if %errorlevel% == 0 (
    echo.
    echo 更新成功！
) else (
    echo.
    echo 更新失败，请检查网络或代理是否开启。
)
pause
