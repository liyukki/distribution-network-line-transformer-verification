# 启动 Streamlit 看板。必须传入已完成运行的目录。
param(
    [Parameter(Mandatory = $true)]
    [string]$RunDir
)
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot
$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    Write-Error "未找到虚拟环境: $Python。请先按 README 的快速开始安装依赖。"
    exit 1
}
$AbsoluteRunDir = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($RunDir)
if (-not (Test-Path $AbsoluteRunDir)) {
    Write-Error "运行目录不存在: $AbsoluteRunDir"
    exit 1
}
$env:LTVERIFY_RUN_DIR = $AbsoluteRunDir
& $Python -m streamlit run app/streamlit_app.py
exit $LASTEXITCODE
