"""Integration smoke: simulate unexpected exit of the owned Jina Code process."""
import json,time
from pathlib import Path
from rag.runtime.resident_models import ResidentEmbeddingPool

pool=ResidentEmbeddingPool()
exe=Path(r"C:\llama\llama-server.exe")
evidence={"first_ok":False,"failure_detected":False,"cleared":False,"recovered":False}
try:
 first=pool.embed_code("Where is Git branch resolved?",exe)
 old=pool.code_lifecycle
 pid=old._process.pid
 evidence["first_ok"]=len(first)==1536
 evidence["first_pid"]=pid
 old._process.terminate()
 old._process.wait(timeout=15)
 try:
  pool.embed_code("Find indexing source code",exe)
 except Exception as e:
  evidence["failure_detected"]=True
  evidence["failure_type"]=type(e).__name__
 evidence["cleared"]=pool.code_lifecycle is None
 second=pool.embed_code("Find indexing source code",exe)
 evidence["recovered"]=len(second)==1536 and pool.code_lifecycle is not old
 evidence["second_pid"]=pool.code_lifecycle._process.pid
finally:
 pool.close()
evidence["pass"]=all(evidence[k] for k in ("first_ok","failure_detected","cleared","recovered"))
Path(__file__).with_name("rag017_actual_process_recovery.json").write_text(json.dumps(evidence,indent=2)+"\n",encoding="utf8")
print(json.dumps(evidence),flush=True)
if not evidence["pass"]:raise SystemExit(1)
