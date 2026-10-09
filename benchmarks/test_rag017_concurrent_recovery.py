"""Concurrent recovery from a terminated experimental Jina Code process."""
import concurrent.futures,json,time
from pathlib import Path
from rag.runtime.resident_models import ResidentEmbeddingPool
pool=ResidentEmbeddingPool()
exe=Path(r"C:\llama\llama-server.exe")
result={}
try:
 pool.embed_code("Initial code query",exe)
 dead=pool.code_lifecycle._process
 result["terminated_pid"]=dead.pid
 dead.terminate()
 dead.wait(timeout=15)
 def ask(i):
  started=time.perf_counter()
  try:
   vector=pool.embed_code("Locate source component "+str(i),exe)
   return {"request":i,"ok":len(vector)==1536,"elapsed_ms":round((time.perf_counter()-started)*1000,2)}
  except Exception as error:
   return {"request":i,"ok":False,"error":type(error).__name__}
 with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
  result["simultaneous"]=list(executor.map(ask,range(3)))
 result["subsequent_ok"]=len(pool.embed_code("Following query",exe))==1536
 result["new_pid"]=pool.code_lifecycle._process.pid
finally:pool.close()
result["pass"]=result["subsequent_ok"] and result["new_pid"]!=result["terminated_pid"] and any(x["ok"] for x in result["simultaneous"])
result["gate"]="BLOCKED"
Path(__file__).with_name("rag017_concurrent_recovery.json").write_text(json.dumps(result,indent=2)+"\n",encoding="utf8")
print(json.dumps(result),flush=True)
if not result["pass"]:raise SystemExit(1)
