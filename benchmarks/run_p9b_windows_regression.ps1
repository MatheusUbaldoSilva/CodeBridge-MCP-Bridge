[CmdletBinding()]
param()
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$python = (Get-Command python.exe -ErrorAction Stop).Source
$site = Join-Path $env:LOCALAPPDATA 'Programs\CodeBridge\runtime\python\Lib\site-packages'
if (!(Test-Path -LiteralPath (Join-Path $site 'psutil') -PathType Container)) {
    throw 'P9B_PSUTIL_DEPENDENCY_UNAVAILABLE'
}
$before = [Environment]::GetEnvironmentVariable('PYTHONPATH','Process')
try {
    $parts = @($repo,(Join-Path $repo 'tests'),$site)
    if ($before) { $parts += $before }
    $env:PYTHONPATH = $parts -join [IO.Path]::PathSeparator
    & $python -c 'import psutil; print(psutil.__version__)'
    if ($LASTEXITCODE -ne 0) { throw 'P9B_PSUTIL_IMPORT_FAILED' }
    Push-Location -LiteralPath $repo
    try {
        & $python -m unittest discover -s tests -p 'test_rag_p9b_*.py' -q
        if ($LASTEXITCODE -ne 0) { throw 'P9B_REGRESSION_FAILED' }
    } finally {
        Pop-Location
    }
} finally {
    [Environment]::SetEnvironmentVariable('PYTHONPATH',$before,'Process')
}