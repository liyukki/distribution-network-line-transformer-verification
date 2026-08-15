# 一键运行默认 30 天完整流水线。从脚本位置解析仓库根目录。
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot
$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    Write-Error "未找到虚拟环境: $Python。请先按 README 的快速开始安装依赖。"
    exit 1
}
& $Python -m ltverify run-all --config configs/default.yaml
exit $LASTEXITCODE
