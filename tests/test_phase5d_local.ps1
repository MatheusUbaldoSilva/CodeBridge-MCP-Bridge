$ErrorActionPreference='Stop'
$r=Get-Content "$env:LOCALAPPDATA\CodeBridge-MCP-Bridge\runtime.json" -Raw|ConvertFrom-Json
$base="http://$($r.host):$($r.port)"
$h=@{Authorization="Bearer $($r.token)"}
function PostJson($path,$body){
  Invoke-RestMethod -Method Post -Headers $h -ContentType 'application/json' -Uri ($base+$path) -Body ($body|ConvertTo-Json -Compress)
}
function GetExec($id){
  (Invoke-RestMethod -Headers $h -Uri ($base+"/v1/phase5c/executions/$id")).execution
}
function WaitState($id,$wanted,$seconds=8){
  $until=(Get-Date).AddSeconds($seconds)
  do { $x=GetExec $id; if($wanted -contains $x.state){return $x}; Start-Sleep -Milliseconds 100 } while((Get-Date)-lt$until)
  throw "timeout waiting $($wanted -join ',') current=$($x.state)"
}
$tag=[DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()
$quick=PostJson '/v1/phase5b/start' @{request_id="phase5d_guard_$tag";command="Write-Output 'P5D_GUARD'; Start-Sleep -Milliseconds 300"}
$qid=$quick.execution.execution_id
WaitState $qid @('FINISHED') 5 | Out-Null
Write-Output "GUARD_FINISHED=$qid"
$long=PostJson '/v1/phase5b/start' @{request_id="phase5d_long_$tag";command="Write-Output 'P5D_LONG_START'; Start-Sleep -Seconds 20; Write-Output 'P5D_LONG_END'"}
$eid=$long.execution.execution_id
$r1=WaitState $eid @('RUNNING') 5
Write-Output "LONG_RUNNING=$eid"
$wrong=PostJson "/v1/phase5d/executions/$qid/stop" @{}
Write-Output "STOP_FINISHED cancelled=$($wrong.stop.cancelled) reason=$($wrong.stop.reason)"
Start-Sleep -Milliseconds 250
$still=GetExec $eid
Write-Output "AFTER_WRONG_STATE=$($still.state)"
if($still.state -ne 'RUNNING'){throw 'wrong execution_id interfered with active execution'}
try {
  PostJson "/v1/phase5d/executions/exec_missing_$tag/stop" @{} | Out-Null
  throw 'missing execution_id unexpectedly accepted'
} catch {
  $code=[int]$_.Exception.Response.StatusCode
  Write-Output "MISSING_STATUS=$code"
  if($code -ne 404){throw}
}
$still2=GetExec $eid
if($still2.state -ne 'RUNNING'){throw '404 stop interfered with active execution'}
$stop=PostJson "/v1/phase5d/executions/$eid/stop" @{}
Write-Output "STOP_CORRECT cancelled=$($stop.stop.cancelled) reason=$($stop.stop.reason)"
if(-not $stop.stop.cancelled){throw 'correct stop was not accepted'}
$final=WaitState $eid @('CANCELLED') 5
$res=(Invoke-RestMethod -Headers $h -Uri ($base+"/v1/phase5c/executions/$eid/result")).result
Write-Output "FINAL=$($final.state) READY=$($res.ready) ERROR=$($res.error_type)"
$flat=($res.output -replace "`r",'' -replace "`n",'|')
Write-Output "OUTPUT=$flat"
if($res.output -notmatch 'P5D_LONG_START'){throw 'start output missing'}
if($res.output -match 'P5D_LONG_END'){throw 'end output should not exist after cancel'}
$again=PostJson "/v1/phase5d/executions/$eid/stop" @{}
Write-Output "STOP_AGAIN cancelled=$($again.stop.cancelled) reason=$($again.stop.reason) state=$($again.stop.state)"
if($again.stop.cancelled -or $again.stop.reason -ne 'already_terminal'){throw 'terminal replay stop is not idempotent'}
$s=(Invoke-RestMethod -Headers $h -Uri ($base+'/v1/status')).status
Write-Output "PS_EXEC=$($s.terminals.powershell.executing) ACTIVE=$($s.terminals.active_target) PREP=$($s.terminals.prepared_target)"
if($s.terminals.powershell.executing){throw 'PowerShell still executing'}
Write-Output 'PHASE5D_LOCAL=PASS'
