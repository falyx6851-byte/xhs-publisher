@echo off
cd /d "%~dp0"
echo ================================================
echo   小红书发布工具 — 手机 APP 后端启动
echo ================================================
echo.
call .venv\Scripts\activate
python api\server.py
pause
