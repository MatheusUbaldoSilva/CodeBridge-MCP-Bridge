$ErrorActionPreference='Stop'
$root='C:\Users\Matheus\CodeBridge-MCP-Bridge'
$data=Join-Path $env:LOCALAPPDATA 'CodeBridge-MCP-Bridge'
$runtimeFile=Join-Path $data 'runtime.json'
$log=Join-Path $root 'tests\phase4_crash_restart_result.log'
$evidence=Join-Path $root 'tests\phase4_crash_evidence.txt'
$requestId='phase4_crash_restart_20260916_1725'
$command="`$p='$evidence'; Add-Content -Path `$p -Value 'RUN'; Write-Output 'CRASH_TEST_STARTED'; Start-Sleep -Seconds 30; Add-Content -Path `$p -Value 'END'"
Remove-Item $evidence -Force -ErrorAction SilentlyContinue
"START $(Get-Date -Format o)" | Set-Content $log
function Get-Runtime { Get-Content $runtimeFile -Raw | ConvertFrom-Json }
function Invoke-CB([string]$path,[hashtable]$body,[object]$r) {
  $h=@{Authorization="Bearer $($r.token)"}
  Invoke-RestMethod -Method Post -Uri "http://$($r.host):$($r.port)$path" -Headers $h -ContentType 'application/json' -Body ($body|ConvertTo-Json -Compress) -TimeoutSec 10
}
$r=Get-Runtime
Invoke-CB '/v1/settings/auto' @{enabled=$true} $r | Out-String | Add-Content $log
$payload=@{request_id=$requestId;target='POWERSHELL5.1';command=$command}|ConvertTo-Json -Compress
$client=Join-Path $root 'tests\phase4_crash_first_call.ps1'
@"
`$ErrorActionPreference='Continue'
`$h=@{Authorization='Bearer $($r.token)'}
try { Invoke-RestMethod -Method Post -Uri 'http://$($r.host):$($r.port)/v1/terminal/dispatch' -Headers `$h -ContentType 'application/json' -Body '$($payload.Replace("'","''"))' -TimeoutSec 60 | ConvertTo-Json -Depth 8 } catch { 'FIRST_CALL_ERROR '+`$_.Exception.Message }
"@ | Set-Content $client -Encoding UTF8
$firstOut=Join-Path $root 'tests\phase4_crash_first_call.out'
$p=Start-Process powershell.exe -PassThru -WindowStyle Hidden -ArgumentList @('-NoProfile','-ExecutionPolicy','Bypass','-File',$client) -RedirectStandardOutput $firstOut
$deadline=(Get-Date).AddSeconds(12)
while((Get-Date)-lt $deadline -and -not (Test-Path $evidence)){ Start-Sleep -Milliseconds 100 }
if(-not (Test-Path $evidence)){ throw 'Comando nao iniciou antes do timeout' }
"EVIDENCE_BEFORE_CRASH=$(Get-Content $evidence -Raw)" | Add-Content $log
$oldPid=[int]$r.pid
$app=Get-CimInstance Win32_Process -Filter "ProcessId=$oldPid"
$rootPid=$oldPid
while($app -and $app.ParentProcessId){
  $parent=Get-CimInstance Win32_Process -Filter "ProcessId=$($app.ParentProcessId)" -ErrorAction SilentlyContinue
  if($parent -and $parent.CommandLine -match 'app_rewrite\\main.py'){ $rootPid=[int]$parent.ProcessId; $app=$parent } else { break }
}
"KILL_ROOT=$rootPid RUNTIME_PID=$oldPid" | Add-Content $log
& taskkill.exe /PID $rootPid /T /F 2>&1 | Add-Content $log
Start-Sleep -Seconds 3
$pyw=Join-Path $root 'app\.venv\Scripts\pythonw.exe'
$main=Join-Path $root 'app_rewrite\main.py'
Start-Process -FilePath $pyw -ArgumentList @($main,'--no-elevate') -WorkingDirectory (Join-Path $root 'app_rewrite')
$new=$null
$deadline=(Get-Date).AddSeconds(20)
while((Get-Date)-lt $deadline){
  Start-Sleep -Milliseconds 250
  try { $candidate=Get-Runtime } catch { continue }
  if([int]$candidate.pid -ne $oldPid){
    try {
      $h=@{Authorization="Bearer $($candidate.token)"}
      $s=Invoke-RestMethod -Uri "http://$($candidate.host):$($candidate.port)/v1/status" -Headers $h -TimeoutSec 2
      if($s.ok){ $new=$candidate; break }
    } catch {}
  }
}
if(-not $new){ throw 'CodeBridge nao voltou apos crash' }
"RESTARTED PID=$($new.pid) PORT=$($new.port)" | Add-Content $log
try {
  $retry=Invoke-CB '/v1/terminal/dispatch' @{request_id=$requestId;target='POWERSHELL5.1';command=$command} $new
  "RETRY_UNEXPECTED_SUCCESS="+($retry|ConvertTo-Json -Depth 8 -Compress) | Add-Content $log
} catch {
  "RETRY_REJECTED=$($_.Exception.Message)" | Add-Content $log
}
Start-Sleep -Seconds 2
$lines=@(Get-Content $evidence -ErrorAction SilentlyContinue)
"EVIDENCE_AFTER_RETRY="+($lines -join '|') | Add-Content $log
"RUN_COUNT="+(@($lines|Where-Object {$_ -eq 'RUN'}).Count) | Add-Content $log
"END_COUNT="+(@($lines|Where-Object {$_ -eq 'END'}).Count) | Add-Content $log
Invoke-CB '/v1/settings/auto' @{enabled=$false} $new | Out-Null
"AUTO_RESTORED_OFF" | Add-Content $log
$db=Join-Path $data 'author_executions.db'
$py=Join-Path $root 'app\.venv\Scripts\python.exe'
$q="import sqlite3,json; p=r'$db'; c=sqlite3.connect(p); c.row_factory=sqlite3.Row; r=c.execute('select execution_request_id,prepared_request_id,state,started_at,finished_at,error_type,error_message from external_executions where prepared_request_id=?',('$requestId',)).fetchone(); print(json.dumps(dict(r) if r else None))"
$dbState=& $py -c $q
"DB_STATE=$dbState" | Add-Content $log
if((@($lines|Where-Object {$_ -eq 'RUN'}).Count -eq 1) -and (@($lines|Where-Object {$_ -eq 'END'}).Count -eq 0)){
  'PHASE4_CRASH_RESTART=PASS' | Add-Content $log
} else {
  'PHASE4_CRASH_RESTART=FAIL' | Add-Content $log
}
"END $(Get-Date -Format o)" | Add-Content $log
