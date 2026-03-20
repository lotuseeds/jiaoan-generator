@echo off
cd /d %~dp0
echo ���ڴ� GitHub ��ȡ���´���...
git pull
if %errorlevel% == 0 (
    echo.
    echo ���³ɹ���
) else (
    echo.
    echo ����ʧ�ܣ��������������Ƿ�����
)
pause
