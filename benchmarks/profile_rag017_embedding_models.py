"""Diagnostic: warm model embedding latency and GPU occupancy, without index writes."""
import json,time,subprocess
from pathlib import Path
from rag.runtime.resident_models import resident_pool
EXE=Path(r"C:\llama\llama-server.exe")
queries=("Where is the git branch obtained?","How do files get indexed?","What happens if a chunk cannot be found?","How does a document carry provenance?","How are source paths validated?")
def gpu():
 try:
  out=subprocess.check_output(["nvidia-smi","--query-gpu=memory.used,utilization.gpu","--format=csv,noheader,nounits"],text=True,timeout=5)
  return tuple(int(n.strip()) for n in out.splitlines()[0].split(","))
 except Exception:return None
results=[]
try:
 for i,q in enumerate(queries,1):
  steps={}
  for label,func in (("text",resident_pool.embed_text),("code",resident_pool.embed_code)):
   start=time.perf_counter()
   vector=func(q,EXE)
   steps[label]={"ms":round((time.perf_counter()-start)*1000,3),"dimensions":len(vector)}
  results.append({"iteration":i,"steps":steps,"gpu_memory_mib_and_util_percent":gpu()})
  print("PROFILE",json.dumps(results[-1]),flush=True)
finally:
 resident_pool.close()
report={"note":"experimental process-local pool; measurements include sequential inference, not qdrant or full response","results":results,"production_gate":"BLOCKED"}
Path(__file__).with_name("rag017_embedding_model_profile.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
