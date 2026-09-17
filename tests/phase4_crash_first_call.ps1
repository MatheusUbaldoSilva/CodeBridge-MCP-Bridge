$ErrorActionPreference='Continue'
$token = $env:CODEBRIDGE_MCP_TOKEN
if([string]::IsNullOrWhiteSpace($token)){ throw 'CODEBRIDGE_MCP_TOKEN not set' }
$h=@{Authorization="Bearer $token"}
try { Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:49614/v1/terminal/dispatch' -Headers $h -ContentType 'application/json' -Body '{"request_id":"phase4_crash_restart_20260916_1725","command":"$p=\u0027C:\\Users\\Matheus\\CodeBridge-MCP-Bridge\\tests\\phase4_crash_evidence.txt\u0027; Add-Content -Path $p -Value \u0027RUN\u0027; Write-Output \u0027CRASH_TEST_STARTED\u0027; Start-Sleep -Seconds 30; Add-Content -Path $p -Value \u0027END\u0027","target":"POWERSHELL5.1"}' -TimeoutSec 60 | ConvertTo-Json -Depth 8 } catch { 'FIRST_CALL_ERROR '+$_.Exception.Message }
