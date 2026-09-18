param(
    [Parameter(Mandatory=$true)]
    [string]$InstallRoot
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

$PythonVersion = '3.13.15'
$PythonZip = "python-$PythonVersion-embed-amd64.zip"
$PythonUrl = "https://www.python.org/ftp/python/$PythonVersion/$PythonZip"
$PythonSha256 = 'd1f04d990aee1253d8569e8e5104e30fa9f5fa830899f14843448872d936a2cf'
$GetPipUrl = 'https://bootstrap.pypa.io/get-pip.py'

$RuntimeDir = Join-Path $InstallRoot 'runtime\python'
$PythonExe = Join-Path $RuntimeDir 'python.exe'
$TempDir = Join-Path $env:TEMP 'CodeBridge-Installer'
$LogDir = Join-Path $env:LOCALAPPDATA 'CodeBridge-MCP-Bridge'
$LogFile = Join-Path $LogDir 'installer.log'

New-Item -ItemType Directory -Force -Path $TempDir, $LogDir | Out-Null

function Write-Log {
    param([string]$Message)
    $line = "$(Get-Date -Format o) $Message"
    $line | Tee-Object -FilePath $LogFile -Append | Write-Output
}

function Download-File {
    param([string]$Url, [string]$Destination)
    Write-Log "Download: $Url"
    Invoke-WebRequest -Uri $Url -OutFile $Destination -UseBasicParsing
}

try {
    Write-Log "CodeBridge bootstrap started at $InstallRoot"

    if (-not (Test-Path $PythonExe)) {
        New-Item -ItemType Directory -Force -Path $RuntimeDir | Out-Null
        $zipPath = Join-Path $TempDir $PythonZip
        Download-File $PythonUrl $zipPath

        $actualHash = (Get-FileHash $zipPath -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($actualHash -ne $PythonSha256) {
            throw "Invalid Python runtime SHA-256: $actualHash"
        }

        Expand-Archive -LiteralPath $zipPath -DestinationPath $RuntimeDir -Force
        $pth = Get-ChildItem $RuntimeDir -Filter 'python*._pth' | Select-Object -First 1
        if (-not $pth) {
            throw 'python*._pth was not found in embedded runtime.'
        }

        @(
            "python313.zip",
            ".",
            "Lib\site-packages",
            "import site"
        ) | Set-Content -LiteralPath $pth.FullName -Encoding ASCII

        New-Item -ItemType Directory -Force -Path (Join-Path $RuntimeDir 'Lib\site-packages') | Out-Null
    }

    $pipPackage = Join-Path $RuntimeDir 'Lib\site-packages\pip'
    if (-not (Test-Path $pipPackage)) {
        $getPip = Join-Path $TempDir 'get-pip.py'
        Download-File $GetPipUrl $getPip
        & $PythonExe $getPip --disable-pip-version-check
        if ($LASTEXITCODE -ne 0) {
            throw "get-pip failed with exit code $LASTEXITCODE"
        }
    }

    Write-Log 'Installing CodeBridge Python dependencies...'
    & $PythonExe -m pip install --disable-pip-version-check --upgrade pip
    if ($LASTEXITCODE -ne 0) {
        throw "pip upgrade failed with exit code $LASTEXITCODE"
    }

    $pipArgs = @(
        '-m', 'pip', 'install',
        '--disable-pip-version-check',
        '--only-binary=:all:',
        '-r', (Join-Path $InstallRoot 'requirements.txt'),
        '-r', (Join-Path $InstallRoot 'author_mcp\requirements.txt')
    )
    & $PythonExe @pipArgs
    if ($LASTEXITCODE -ne 0) {
        throw "pip install failed with exit code $LASTEXITCODE"
    }

    Write-Log 'Validating runtime...'
    & $PythonExe -c "import PySide6,paramiko,psutil,mcp,pydantic; print('RUNTIME_OK')"
    if ($LASTEXITCODE -ne 0) {
        throw "Runtime validation failed with exit code $LASTEXITCODE"
    }

    Write-Log 'Bootstrap completed successfully.'
    exit 0
}
catch {
    Write-Log ("ERROR: " + $_.Exception.Message)
    Write-Error $_
    exit 1
}
