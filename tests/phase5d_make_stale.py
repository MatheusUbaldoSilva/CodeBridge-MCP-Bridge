import hashlib, sys
from pathlib import Path
sys.path.insert(0, r"C:\Users\Matheus\CodeBridge-MCP-Bridge\app_rewrite")
from constants import DATA_DIR
from execution_ledger import ExecutionLedger

execution_id = sys.argv[1]
request_id = sys.argv[2]
ledger = ExecutionLedger(DATA_DIR / "executions_v2.db")
digest = hashlib.sha256(b"PHASE5D_STALE_FAKE").hexdigest()
row, _ = ledger.create(execution_id, request_id, "POWERSHELL5.1", digest, "stale_runtime")
row = ledger.transition(execution_id, "RUNNING", runtime_instance="stale_runtime")
print(row["execution_id"], row["state"], row["runtime_instance"])
