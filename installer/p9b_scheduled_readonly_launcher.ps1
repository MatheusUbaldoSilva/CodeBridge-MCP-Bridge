[CmdletBinding()]
param(
 [Parameter(Mandatory=$true)][string]$Stage,
 [Parameter(Mandatory=$true)][string]$Repository
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$taskName='CodeBridge_P9B_Cmdlet_ReadOnly'
$created=$false
$folder=$null
try {
 $stagePath=(Resolve-Path -LiteralPath $Stage).Path
 $repoPath=(Resolve-Path -LiteralPath $Repository).Path
 $identity=Join-Path $stagePath 'TRANSACTION_IDENTITY.json'
 $dependency=Join-Path $stagePath 'external_supervisor_lib\psutil\__init__.py'
 $installed=Join-Path $env:LOCALAPPDATA 'Programs\CodeBridge'
 $python=Join-Path $env:LOCALAPPDATA 'Programs\Python\Python313\python.exe'
 if (!(Test-Path -LiteralPath $identity -PathType Leaf) -or
     !(Test-Path -LiteralPath $dependency -PathType Leaf) -or
     !(Test-Path -LiteralPath $installed -PathType Container) -or
     !(Test-Path -LiteralPath $python -PathType Leaf)) {
   throw 'P9B_READONLY_PREREQUISITE_MISSING'
 }
 $manifest=Get-Content -LiteralPath $identity -Raw | ConvertFrom-Json
 $commit=[string]$manifest.source_commit
 if ($commit -notmatch '^[a-f0-9]{40}$') {throw 'P9B_COMMIT_INVALID'}
 $sha=(Get-FileHash -LiteralPath $identity -Algorithm SHA256).Hash.ToLowerInvariant()
 if (Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue) {
   throw 'P9B_REFUSE_PREEXISTING_TASK'
 }
 $folder=Join-Path $env:TEMP ('cb_p9b_sched_'+[guid]::NewGuid().ToString('N'))
 New-Item -ItemType Directory -Path $folder -ErrorAction Stop | Out-Null
 $worker=Join-Path $folder 'worker.py'
 $result=Join-Path $folder 'result.json'
 @{
   repo=$repoPath;stage=$stagePath;installed=$installed;identity=$identity
   identity_sha=$sha;commit=$commit
 } | ConvertTo-Json -Compress | Set-Content -LiteralPath (Join-Path $folder 'request.json') -Encoding UTF8
 $lines=@(
   'import json,sys'
   'from pathlib import Path'
   'folder=Path(__file__).resolve().parent'
   'req=json.loads((folder/"request.json").read_text(encoding="utf-8-sig"))'
   'sys.path[:0]=[str(Path(req["stage"])/"external_supervisor_lib"),req["repo"]]'
   'from installer.rag_p9b_scheduled_supervisor_readonly import main'
   'raise SystemExit(main(["--installed",req["installed"],"--stage",req["stage"],'
   ' "--identity",req["identity"],"--identity-sha",req["identity_sha"],'
   ' "--expected-commit",req["commit"],"--result",str(folder/"result.json")]))'
 )
 $lines | Set-Content -LiteralPath $worker -Encoding UTF8
 $action=New-ScheduledTaskAction -Execute $python -Argument ('"'+$worker+'"') -WorkingDirectory $folder
 $principal=New-ScheduledTaskPrincipal -UserId ([Security.Principal.WindowsIdentity]::GetCurrent().Name) -LogonType Interactive -RunLevel Limited
 Register-ScheduledTask -TaskName $taskName -Action $action -Principal $principal -ErrorAction Stop | Out-Null
 $created=$true
 Start-ScheduledTask -TaskName $taskName -ErrorAction Stop
 for($i=0;$i -lt 40 -and !(Test-Path -LiteralPath $result);$i++){
   Start-Sleep -Milliseconds 500
 }
 if (!(Test-Path -LiteralPath $result -PathType Leaf)) {
   throw 'P9B_SCHEDULED_ATTESTATION_MISSING'
 }
 $proof=Get-Content -LiteralPath $result -Raw | ConvertFrom-Json
 if ($proof.state -ne 'SCHEDULED_SUPERVISOR_READONLY_ATTESTED' -or
     $proof.external_runtime_verified -ne $true -or
     $proof.ancestry_verified -ne $true -or
     $proof.identity_verified -ne $true -or
     $proof.shutdown_plan_verified -ne $true -or
     $proof.authorized -ne $false -or
     $proof.installer_executed -ne $false -or
     $proof.shutdown_signals_sent -ne $false -or
     $proof.production_modified -ne $false) {
   throw 'P9B_SCHEDULED_ATTESTATION_REFUSED'
 }
 [pscustomobject]@{
   state='SCHEDULED_READONLY_LAUNCH_VERIFIED'
   authorized=$false;installer_executed=$false
   shutdown_signals_sent=$false;identity_sha256=$sha
   commit=$commit;read_only=$true
 } | ConvertTo-Json -Compress
} finally {
 if ($created) {
   Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction Stop
 }
 if ($folder -and (Test-Path -LiteralPath $folder)) {
   Remove-Item -LiteralPath $folder -Recurse -Force -ErrorAction Stop
 }
}
