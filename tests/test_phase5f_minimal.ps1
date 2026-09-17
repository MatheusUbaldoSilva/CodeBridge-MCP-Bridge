$ErrorActionPreference='Stop'
$runtime=Get-Content "$env:LOCALAPPDATA\CodeBridge-MCP-Bridge\runtime.json" -Raw | ConvertFrom-Json
$base="http://$($runtime.host):$($runtime.port)"
$headers=@{Authorization="Bearer $($runtime.token)"}
$requestId='p5f_min_'+[guid]::NewGuid().ToString('N')
$command="1..2000 | ForEach-Object { Write-Output ('P5F_{0:D4}_{1}' -f `$_, ('X'*30)); if((`$_ % 100) -eq 0){ Start-Sleep -Milliseconds 50 } }"
$body=@{request_id=$requestId;command=$command}|ConvertTo-Json -Compress
$sw=[Diagnostics.Stopwatch]::StartNew()
$start=Invoke-RestMethod "$base/v1/phase5b/start" -Method Post -Headers $headers -ContentType 'application/json' -Body $body
$sw.Stop()
$id=$start.execution.execution_id
"START_MS=$($sw.ElapsedMilliseconds) ID=$id STATE=$($start.execution.state)"
$cursor=0
$pieces=New-Object System.Collections.Generic.List[string]
$reads=0
$sawRunning=$false
do {
  Start-Sleep -Milliseconds 120
  $chunk=Invoke-RestMethod "$base/v1/phase5f/executions/$id/output?cursor=$cursor&max_chars=4096" -Headers $headers
  $o=$chunk.output
  if($o.text){ [void]$pieces.Add([string]$o.text) }
  $cursor=[int]$o.next_cursor
  $reads++
  $st=Invoke-RestMethod "$base/v1/phase5c/executions/$id" -Headers $headers
  if($st.execution.state -eq 'RUNNING'){ $sawRunning=$true }
  if($reads -le 4){ "READ#$reads STATE=$($st.execution.state) CHARS=$($o.chars) CURSOR=$cursor MORE=$($o.has_more) EOF=$($o.eof)" }
} while(-not $st.execution.complete -or $o.has_more)
$all=[string]::Concat($pieces)
$expected=1..2000 | ForEach-Object { 'P5F_{0:D4}_{1}' -f $_, ('X'*30) }
$expectedText=([string]::Join("`n",$expected))+"`n"
"FINAL_STATE=$($st.execution.state) READS=$reads CURSOR=$cursor LEN=$($all.Length) EXPECTED=$($expectedText.Length) SAW_RUNNING=$sawRunning"
$result=Invoke-RestMethod "$base/v1/phase5c/executions/$id/result" -Headers $headers
$finalOutput=[string]$result.result.output
"RESULT_LEN=$($finalOutput.Length) EXIT=$($result.result.exit_code) READY=$($result.result.ready)"
$markerOk=$all.Contains('P5F_0001_') -and $all.Contains('P5F_2000_')
$fullOk=$finalOutput.Contains('P5F_0001_') -and $finalOutput.Contains('P5F_2000_')
$sizeOk=($all.Length -ge 70000 -and $all.Length -le 100000)
if(-not ($markerOk -and $fullOk -and $sizeOk -and $st.execution.state -eq 'FINISHED' -and $sawRunning)){ throw 'PHASE5F_MINIMAL_FAILED' }
"PHASE5F_MINIMAL=PASS"
