"""Repeated real-process failure recovery; isolated experimental model only."""
import json,time
from pathlib import Path
from rag.runtime.resident_models import ResidentEmbeddingPool

pool=ResidentEmbeddingPool()
exe=Path(r"C:\llama\llama-server.exe")
records=[]
try:
 for cycle in range(3):
  vector=pool.embed_code("Locate code search source",exe)
  old=pool.code_lifecycle
  pid=old._process.pid
  old._process.terminate()
  old._process.wait(timeout=15)
  detected=False
  try:pool.embed_code("Locate source files",exe)
  except Exception:detected=True
  cleared=pool.code_lifecycle is None
  recovered=pool.embed_code("Locate source files",exe)
  new_pid=pool.code_lifecycle._process.pid
  result={"cycle":cycle+1,"old_pid":pid,"new_pid":new_pid,"detected":detected,"cleared":cleared,"recovered":len(recovered)==1536 and new_pid!=pid}
  records.append(result)
  print("CYCLE",json.dumps(result),flush=True)
finally:pool.close()
passed=all(r["detected"] and r["cleared"] and r["recovered"] for r in records) and len(records)==3
Path(__file__).with_name("rag017_repeated_process_recovery.json").write_text(json.dumps({"cycles":records,"passed":passed,"gate":"BLOCKED"},indent=2)+"\n",encoding="utf8")
if not passed:raise SystemExit(1)
