param(
    [ValidateSet('backend','frontend','share')][string]$Service='backend',
    [ValidateRange(1,65535)][int]$Port=8765,
    [switch]$SkipBuild,
    [switch]$PrepareOnly
)
$taskRoot = Split-Path -Parent $PSScriptRoot
if ($Service -eq 'share') {
    $taskPython = Join-Path $taskRoot 'backend\.venv\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $taskPython)) { throw 'Run the uv sync command in README first.' }
    $taskShareArgs = @((Join-Path $PSScriptRoot 'share.py'), '--port', "$Port")
    if ($SkipBuild) { $taskShareArgs += '--skip-build' }
    if ($PrepareOnly) { $taskShareArgs += '--prepare-only' }
    & $taskPython @taskShareArgs
    if ($LASTEXITCODE -ne 0) { throw "Sharing failed (exit code $LASTEXITCODE)." }
} elseif ($Service -eq 'backend') {
    $taskPython = Join-Path $taskRoot 'backend\.venv\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $taskPython)) { throw 'READMEのuv syncを先に実行してください' }
    Push-Location (Join-Path $taskRoot 'backend')
    try { & $taskPython -m app } finally { Pop-Location }
} else {
    Push-Location (Join-Path $taskRoot 'frontend')
    try { npm.cmd run dev } finally { Pop-Location }
}
