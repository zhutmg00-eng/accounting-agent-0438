@echo off
chcp 65001 > nul
title DeepSeek-AuditMind 2026数智会计创新应用竞赛一键启动器

echo ========================================================
echo   2026年北京市大学生数智会计创新应用竞赛 参赛作品
echo   DeepSeek-AuditMind: 复杂业财融合与数智舞弊穿透智能体
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
if not exist "data\templates" mkdir "data\templates"

:: 3. 启动 Streamlit 可视化大屏
echo [启动中] 正在启动数智审计穿透大屏 (端口 8501)...
echo [提示] 浏览器将自动打开 http://localhost:8501
echo.

where uv >nul 2>nul
if %errorlevel% equ 0 (
    uv run streamlit run src/ui/app.py --server.port 8501
) else (
    python -m streamlit run src/ui/app.py --server.port 8501
)

pause
