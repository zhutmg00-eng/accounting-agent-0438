@echo off
chcp 65001 > nul
title DeepSeek-AuditMind 2026数智会计创新应用竞赛一键启动器

echo ========================================================
echo   2026年北京市大学生数智会计创新应用竞赛 参赛作品
echo   DeepSeek-AuditMind: 数智业财融合与舞弊穿透智能体全景指挥舱
echo ========================================================
echo.

:: 1. 检查 Python 环境
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [错误] 未检测到 Python，请先安装 Python 3.12+ 并将其加入 PATH 环境变量。
    pause
    exit /b 1
)

:: 2. 创建必要目录
if not exist "output" mkdir output
if not exist "output\excel" mkdir output\excel
if not exist "output\pdf" mkdir output\pdf
if not exist "output\json" mkdir output\json
if not exist "data\templates" mkdir "data\templates"

:: 3. 启动数智审计指挥舱大屏 (端口 8501)
echo [启动中] 正在启动数智审计全景指挥舱 (端口 8501)...
echo [提示] 浏览器将自动打开 http://127.0.0.1:8501
echo.

where uv >nul 2>nul
if %errorlevel% equ 0 (
    uv run python main.py
) else (
    python main.py
)

pause
