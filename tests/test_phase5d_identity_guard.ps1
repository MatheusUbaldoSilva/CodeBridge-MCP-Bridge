$ErrorActionPreference='Stop'
$r=Get-Content "$env:LOCALAPPDATA\CodeBridge-MCP-Bridge\runtime.json" -Raw|ConvertFrom-Json
$base="http://$($r.host):$($r.port)"
$h=@{Authorization="Bearer $($r.token)"}
function PostJson($path,$body){Invoke-RestMethod -Method Post -Headers $h -ContentType 'application/json' -Uri ($base+$path) -Body ($body|ConvertTo-Json -Compress)}
function GetExec($id){(Invoke-RestMethod -Headers $h -Uri ($base+"/v1/phase5c/executions/$id")).execution}
$tag=[DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()
$stale="exec_stale_$tag"; $staleReq="req_stale_$tag"
$py='C:\Users\Matheus\CodeBridge-MCP-Bridge\app\.venv\Scripts\python.exe'
$mk='C:\Users\Matheus\CodeBridge-MCP-Bridge\tests\phase5d_make_stale.py'
& $py $mk $stale $staleReq | Write-Output
$long=PostJson '/v1/phase5b/start' @{request_id="phase5d_identity_$tag";command="Write-Output 'P5D_ID_START'; Start-Sleep -Seconds 12; Write-Output 'P5D_ID_END'"}
$eid=$long.execution.execution_id
$until=(Get-Date).AddSeconds(5); do{$cur=GetExec $eid; if($cur.state -eq 'RUNNING'){break}; Start-Sleep -Milliseconds 100}while((Get-Date)-lt$until)
if($cur.state -ne 'RUNNING'){throw 'real execution did not reach RUNNING'}
try {
  PostJson "/v1/phase5d/executions/$stale/stop" @{} | Out-Null
  throw 'stale RUNNING id unexpectedly cancelled something'
} catch {
  $code=[int]$_.Exception.Response.StatusCode
  Write-Output "STALE_STOP_STATUS=$code"
  if($code -ne 400){throw}
}
Start-Sleep -Milliseconds 250
$still=GetExec $eid
Write-Output "REAL_AFTER_STALE=$($still.state)"
if($still.state -ne 'RUNNING'){throw 'stale execution_id cancelled the real execution'}
$stop=PostJson "/v1/phase5d/executions/$eid/stop" @{}
Write-Output "REAL_STOP cancelled=$($stop.stop.cancelled) reason=$($stop.stop.reason)"
$until=(Get-Date).AddSeconds(5); do{$cur=GetExec $eid; if($cur.state -eq 'CANCELLED'){break}; Start-Sleep -Milliseconds 100}while((Get-Date)-lt$until)
if($cur.state -ne 'CANCELLED'){throw "real execution final state=$($cur.state)"}
Write-Output 'PHASE5D_IDENTITY_GUARD=PASS'
