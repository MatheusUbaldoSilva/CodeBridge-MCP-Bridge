import time
from http_client import ProtocolHTTPClient

client = ProtocolHTTPClient(timeout=12)
request_id = "req_phase5e_replay_20260917_1147"
payload = {
    "target": "POWERSHELL5.1",
    "command": "Write-Output 'P5E_REPLAY_ONCE'; Start-Sleep -Seconds 1",
}
first = client.exchange("EXECUTION_V2_START", payload, request_id=request_id)
second = client.exchange("EXECUTION_V2_START", payload, request_id=request_id)
eid1 = first["payload"]["execution_id"]
eid2 = second["payload"]["execution_id"]
print("SAME_EXECUTION", eid1 == eid2)
print("SAME_RESPONSE", first["response_syn"]["response_id"] == second["response_syn"]["response_id"])
time.sleep(2)
result = client.exchange("EXECUTION_V2_RESULT", {"execution_id": eid1})["payload"]
print("FINAL", result["state"], "COUNT", result.get("output", "").count("P5E_REPLAY_ONCE"))
print("PHASE5E_REPLAY", "PASS" if eid1 == eid2 and result.get("output", "").count("P5E_REPLAY_ONCE") == 1 else "FAIL")
