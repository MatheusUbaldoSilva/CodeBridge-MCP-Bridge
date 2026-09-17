$ErrorActionPreference='Stop'
$runtimePath=Join-Path $env:LOCALAPPDATA 'CodeBridge-MCP-Bridge\runtime.json'
$r=Get-Content $runtimePath -Raw | ConvertFrom-Json
$headers=@{Authorization=('Bearer '+$r.token)}
$base="http://$($r.host):$($r.port)"
$requestId='phase5c_ps_'+[Guid]::NewGuid().ToString('N')
$body=@{
  request_id=$requestId
  command="Write-Output 'PHASE5C_START'; Start-Sleep -Seconds 4; Write-Output 'PHASE5C_END'"
} | ConvertTo-Json -Compress
$sw=[Diagnostics.Stopwatch]::StartNew()
$start=Invoke-RestMethod -Method Post -Headers $headers -ContentType 'application/json' -Uri "$base/v1/phase5b/start" -Body $body
$sw.Stop()
$id=$start.execution.execution_id
"START_MS=$($sw.ElapsedMilliseconds) ID=$id STATE=$($start.execution.state)"
$status0=Invoke-RestMethod -Headers $headers -Uri "$base/v1/phase5c/executions/$id"
$result0=Invoke-RestMethod -Headers $headers -Uri "$base/v1/phase5c/executions/$id/result"
"STATUS0=$($status0.execution.state) COMPLETE=$($status0.execution.complete) RESULT_READY=$($result0.result.ready)"
Start-Sleep -Seconds 1
$status1=Invoke-RestMethod -Headers $headers -Uri "$base/v1/phase5c/executions/$id"
$result1=Invoke-RestMethod -Headers $headers -Uri "$base/v1/phase5c/executions/$id/result"
"STATUS1=$($status1.execution.state) COMPLETE=$($status1.execution.complete) RESULT_READY=$($result1.result.ready)"
$deadline=(Get-Date).AddSeconds(10)
do {
  Start-Sleep -Milliseconds 300
  $statusF=Invoke-RestMethod -Headers $headers -Uri "$base/v1/phase5c/executions/$id"
} while(-not $statusF.execution.complete -and (Get-Date) -lt $deadline)
$resultF=Invoke-RestMethod -Headers $headers -Uri "$base/v1/phase5c/executions/$id/result"
"FINAL_STATE=$($statusF.execution.state) COMPLETE=$($statusF.execution.complete) READY=$($resultF.result.ready) EXIT=$($resultF.result.exit_code)"
"OUTPUT_BEGIN"
$resultF.result.output
"OUTPUT_END"
if($statusF.execution.state -ne 'FINISHED'){throw 'estado final inesperado'}
if(-not $resultF.result.ready){throw 'resultado final nao ficou pronto'}
if($resultF.result.output -notmatch 'PHASE5C_START' -or $resultF.result.output -notmatch 'PHASE5C_END'){throw 'saida final incompleta'}
Set-Content -Path 'C:\Users\Matheus\CodeBridge-MCP-Bridge\tests\phase5c_last_execution_id.txt' -Value $id -Encoding ascii
"PHASE5C_LOCAL=PASS"
