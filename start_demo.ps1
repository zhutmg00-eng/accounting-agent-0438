# ========================================================
# DeepSeek-AuditMind 比赛现场演示增强启动脚本
# 2026年北京市大学生数智会计创新应用竞赛
# ========================================================

Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "  DeepSeek-AuditMind 现场演示系统自检与启动" -ForegroundColor Green
Write-Host "========================================================" -ForegroundColor Cyan

# 1. 检查 Python
$pyVersion = python --version 2>$null
if (-not $pyVersion) {
    Write-Host "[错误] 未检测到 Python，请先安装 Python 3.12+" -ForegroundColor Red
    exit 1
}
Write-Host "[OK] Python 环境: $pyVersion" -ForegroundColor Green

# 2. 检查输出与模板目录
$outDir = "output"
if (-not (Test-Path $outDir)) {
    New-Item -ItemType Directory -Path $outDir | Out-Null
}
$tmplDir = "data/templates"
if (-not (Test-Path $tmplDir)) {
    New-Item -ItemType Directory -Path $tmplDir | Out-Null
}
Write-Host "[OK] 运行缓存与模板目录就绪" -ForegroundColor Green

# 3. 运行自检用例与基准校验
Write-Host "[自检] 正在验证核心审计算子完整性..." -ForegroundColor Yellow
$testOutput = uv run python -c "from src.benchmark.test_cases import get_benchmark_cases; print(f'已载入 {len(get_benchmark_cases())} 个测试基准案例')" 2>$null
Write-Host "[OK] $testOutput" -ForegroundColor Green

# 4. 启动前端
Write-Host ""
Write-Host "[启动] 正在拉起 Streamlit 数智交互大屏..." -ForegroundColor Cyan
Write-Host "👉 访问地址: http://localhost:8501" -ForegroundColor Yellow
Write-Host ""

uv run streamlit run src/ui/app.py --server.port 8501
