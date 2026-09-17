$ErrorActionPreference='Stop'
$root='C:\Users\Matheus\CodeBridge-MCP-Bridge'
$data=Join-Path $env:LOCALAPPDATA 'CodeBridge-MCP-Bridge'
$runtimeFile=Join-Path $data 'runtime.json'
$stackFile=Join-Path $root 'author_mcp\stack_state.json'
$py=Join-Path $root 'author_mcp\.venv\Scripts\python.exe'
$probe=Join-Path $root 'author_mcp\probe_public_status.py'
$log=Join-Path $root 'tests\phase4_public_stack_survival.log'
"START $(Get-Date -Format o)"|Set-Content $log
$stack=Get-Content $stackFile -Raw|ConvertFrom-Json
$url=$stack.mcp_url
"URL=$url"|Add-Content $log
$before=& $py $probe $url 2>&1
"BEFORE=$before"|Add-Content $log
$r=Get-Content $runtimeFile -Raw|ConvertFrom-Json
$oldPid=[int]$r.pid
$app=Get-CimInstance Win32_Process -Filter "ProcessId=$oldPid"
$rootPid=$oldPid
while($app -and $app.ParentProcessId){
  $parent=Get-CimInstance Win32_Process -Filter "ProcessId=$($app.ParentProcessId)" -ErrorAction SilentlyContinue
  if($parent -and $parent.CommandLine -match 'app_rewrite\\main.py'){ $rootPid=[int]$parent.ProcessId; $app=$parent } else { break }
}
"KILL_ROOT=$rootPid"|Add-Content $log
& taskkill.exe /PID $rootPid /T /F 2>&1|Add-Content $log
Start-Sleep -Seconds 3
$during=& $py $probe $url 2>&1
"DURING=$during"|Add-Content $log
$pyw=Join-Path $root 'app\.venv\Scripts\pythonw.exe'
$main=Join-Path $root 'app_rewrite\main.py'
Start-Process -FilePath $pyw -ArgumentList @($main,'--no-elevate') -WorkingDirectory (Join-Path $root 'app_rewrite')
$new=$null
$deadline=(Get-Date).AddSeconds(20)
while((Get-Date)-lt $deadline){
  Start-Sleep -Milliseconds 250
  try{$candidate=Get-Content $runtimeFile -Raw|ConvertFrom-Json}catch{continue}
  if([int]$candidate.pid -ne $oldPid){
    try{
      $h=@{Authorization="Bearer $($candidate.token)"}
      $s=Invoke-RestMethod -Uri "http://$($candidate.host):$($candidate.port)/v1/status" -Headers $h -TimeoutSec 2
      if($s.ok){$new=$candidate;break}
    }catch{}
  }
}
if(-not $new){throw 'CodeBridge nao voltou'}
"NEW_PID=$($new.pid)"|Add-Content $log
$after=& $py $probe $url 2>&1
"AFTER=$after"|Add-Content $log
$b=($before|Select-Object -Last 1)|ConvertFrom-Json
$d=($during|Select-Object -Last 1)|ConvertFrom-Json
$a=($after|Select-Object -Last 1)|ConvertFrom-Json
$ports=@(Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue|Where-Object {$_.LocalPort -in 4040,8765,8766}|Select-Object -ExpandProperty LocalPort)
"PORTS="+(($ports|Sort-Object)-join ',')|Add-Content $log
$h=@{Authorization="Bearer $($new.token)"}
Invoke-RestMethod -Method Post -Uri "http://$($new.host):$($new.port)/v1/settings/auto" -Headers $h -ContentType 'application/json' -Body '{"enabled":false}'|Out-Null
$pass=($b.operation_ok -eq $true -and $b.handshake_confirmed -eq $true -and $d.operation_ok -eq $false -and $d.handshake_confirmed -eq $true -and $a.operation_ok -eq $true -and $a.handshake_confirmed -eq $true -and ($ports -contains 4040) -and ($ports -contains 8765) -and ($ports -contains 8766))
if($pass){'PHASE4_PUBLIC_STACK_SURVIVAL=PASS'|Add-Content $log}else{'PHASE4_PUBLIC_STACK_SURVIVAL=FAIL'|Add-Content $log}
"END $(Get-Date -Format o)"|Add-Content $log
