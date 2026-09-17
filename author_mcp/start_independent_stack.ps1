$ErrorActionPreference='Stop'
$root='C:\Users\Matheus\CodeBridge-MCP-Bridge'
$author=Join-Path $root 'author_mcp'
$py=Join-Path $author '.venv\Scripts\python.exe'
$ngrok='C:\Users\Matheus\CodeBridge_MCP_Teste\ngrok\ngrok.exe'
$stateFile=Join-Path $author 'stack_state.json'
$log=Join-Path $author 'stack_start.log'
"START $(Get-Date -Format o)" | Set-Content $log

# Limpeza forte: remove adapters/MCP antigos, inclusive launchers sem porta aberta.
$procs=@(Get-CimInstance Win32_Process | Where-Object {
  $_.Name -match '^python(w)?\.exe$' -and $_.CommandLine -and
  $_.CommandLine -match '(adapter_server\.py|mcp_server\.py)'
})
foreach($p in $procs){
  try { taskkill.exe /PID $p.ProcessId /T /F 2>&1 | Add-Content $log } catch {}
}

# Um unico ngrok para esta stack.
$ngroks=@(Get-CimInstance Win32_Process | Where-Object {$_.Name -eq 'ngrok.exe'})
foreach($p in $ngroks){
  try { Stop-Process -Id $p.ProcessId -Force -ErrorAction Stop; "STOP_NGROK PID=$($p.ProcessId)"|Add-Content $log } catch {}
}
Start-Sleep -Milliseconds 800

# Remove bytecode para garantir que a nova fonte seja carregada.
Get-ChildItem -Path $author -Directory -Filter '__pycache__' -Recurse -ErrorAction SilentlyContinue |
  Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

foreach($port in 8765,8766,4040){
  $busy=@(Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue)
  if($busy){ throw "porta $port ainda ocupada por PID(s): $($busy.OwningProcess -join ',')" }
}

$adapter=Start-Process -FilePath $py -ArgumentList @('-B','adapter_server.py') -WorkingDirectory $author -WindowStyle Hidden -PassThru
"ADAPTER_LAUNCH_PID=$($adapter.Id)"|Add-Content $log
$deadline=(Get-Date).AddSeconds(10)
do {
  Start-Sleep -Milliseconds 200
  try { $health=Invoke-RestMethod 'http://127.0.0.1:8766/health' -TimeoutSec 2 } catch { $health=$null }
} until($health -or (Get-Date)-ge $deadline)
if(-not $health){ throw 'adapter nao abriu porta 8766' }
if(-not (($health.operations -contains 'EXECUTION_V2_START') -and ($health.operations -contains 'EXECUTION_V2_OUTPUT'))){ throw 'adapter subiu sem operacoes V2/5F' }
"ADAPTER_HEALTH_OK ops=$($health.operations -join ',')"|Add-Content $log
$nglog=Join-Path $author 'ngrok_independent.log'
Remove-Item $nglog -Force -ErrorAction SilentlyContinue
$ng=Start-Process -FilePath $ngrok -ArgumentList @('http','8765','--log',$nglog,'--log-format','json') -WorkingDirectory $author -WindowStyle Hidden -PassThru
"NGROK_LAUNCH_PID=$($ng.Id)"|Add-Content $log
$public=$null
$deadline=(Get-Date).AddSeconds(15)
while((Get-Date)-lt $deadline){
  Start-Sleep -Milliseconds 300
  try {
    $t=Invoke-RestMethod 'http://127.0.0.1:4040/api/tunnels' -TimeoutSec 2
    $public=($t.tunnels|Select-Object -First 1).public_url
    if($public){break}
  } catch {}
}
if(-not $public){ throw 'ngrok nao abriu tunnel' }
$hostName=([uri]$public).Host
"PUBLIC=$public"|Add-Content $log
$mcp=Start-Process -FilePath $py -ArgumentList @('-B','mcp_server.py','--public-host',$hostName) -WorkingDirectory $author -WindowStyle Hidden -PassThru
"MCP_LAUNCH_PID=$($mcp.Id)"|Add-Content $log
Start-Sleep -Seconds 2
$mcpListen=@(Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue)
if(-not $mcpListen){ throw 'MCP nao abriu porta 8765' }
$state=[ordered]@{
  started_at=(Get-Date -Format o)
  public_url=$public
  mcp_url=($public+'/mcp')
  adapter_launch_pid=$adapter.Id
  adapter_listener_pid=(@(Get-NetTCPConnection -LocalPort 8766 -State Listen)[0].OwningProcess)
  ngrok_launch_pid=$ng.Id
  mcp_launch_pid=$mcp.Id
  mcp_listener_pid=$mcpListen[0].OwningProcess
  adapter_operations=$health.operations
}
$state|ConvertTo-Json -Depth 4|Set-Content $stateFile -Encoding UTF8
"END $(Get-Date -Format o)"|Add-Content $log
$state | ConvertTo-Json -Depth 4

