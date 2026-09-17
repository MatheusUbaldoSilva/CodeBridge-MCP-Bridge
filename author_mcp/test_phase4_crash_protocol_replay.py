from pathlib import Path
from http_client import ProtocolHTTPClient

rid='phase4_crash_restart_20260916_1725'
ev=Path(r'C:\Users\Matheus\CodeBridge-MCP-Bridge\tests\phase4_crash_evidence.txt')
cmd=f"$p='{ev}'; Add-Content -Path $p -Value 'RUN'; Write-Output 'CRASH_TEST_STARTED'; Start-Sleep -Seconds 30; Add-Content -Path $p -Value 'END'"
payload={'target':'POWERSHELL5.1','command':cmd}
c=ProtocolHTTPClient(timeout=5)
a=c.exchange('DISPATCH', payload, request_id=rid)
b=c.exchange('DISPATCH', payload, request_id=rid)
lines=ev.read_text(encoding='utf-8').splitlines()
assert a['payload']['operation_ok'] is False
assert b['payload']['operation_ok'] is False
assert a['request_ack']['acked_at']==b['request_ack']['acked_at']
assert a['response_syn']['response_id']==b['response_syn']['response_id']
assert a['response_ack']['acked_at']==b['response_ack']['acked_at']
assert lines.count('RUN')==1 and lines.count('END')==0
print('PHASE4_PROTOCOL_CRASH_REPLAY=PASS')
print('RESPONSE_ID='+a['response_syn']['response_id'])
print('RUN_COUNT=1 END_COUNT=0')
