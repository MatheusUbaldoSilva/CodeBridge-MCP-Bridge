"""Native Windows process working set sampling for CODE-only workload."""
import ctypes,os,subprocess,threading,time,json,concurrent.futures
from pathlib import Path
from rag.runtime.resident_models import ResidentEmbeddingPool
class Mem(ctypes.Structure):
 _fields_=[("size",ctypes.c_ulong),("faults",ctypes.c_ulong),("peak_ws",ctypes.c_size_t),("ws",ctypes.c_size_t),("qpp",ctypes.c_size_t),("pp",ctypes.c_size_t),("qpnp",ctypes.c_size_t),("pnp",ctypes.c_size_t),("page",ctypes.c_size_t),("peak_page",ctypes.c_size_t)]
k=ctypes.windll.kernel32
def rss(pid):
 h=k.OpenProcess(0x1000,False,pid)
 if not h:return 0
 try:
  m=Mem();m.size=ctypes.sizeof(m)
  return m.ws/1048576 if ctypes.windll.psapi.GetProcessMemoryInfo(h,ctypes.byref(m),m.size) else 0
 finally:k.CloseHandle(h)
pool=ResidentEmbeddingPool()
exe=Path(r"C:\llama\llama-server.exe")
stop=threading.Event()
samples=[]
def sample():
 while not stop.is_set():
  try:
   inst=pool.code_lifecycle
   code=inst._process.pid if inst is not None and inst._process is not None else None
   samples.append({"parent_mib":round(rss(os.getpid()),2),"model_mib":round(rss(code),2) if code else 0})
  except Exception:pass
  stop.wait(.015)
t=threading.Thread(target=sample,daemon=True);t.start()
try:
 def embed(i):
  vec=pool.embed_code("Where is Git provenance resolved request "+str(i),exe)
  return len(vec)
 with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
  dims=list(executor.map(embed,range(40)))
finally:
 pool.close();stop.set();t.join(timeout=5)
v=[x["parent_mib"]+x["model_mib"] for x in samples]
report={"sample_count":len(v),"peak_combined_parent_plus_model_rss_mib":round(max(v),2) if v else None,"all_embeddings_1536":all(x==1536 for x in dims),"gate":"BLOCKED","caveat":"sampled combined parent Python and owned model working sets; does not include other system processes, GPU memory or one-off transient peaks"}
Path(__file__).with_name("rag017_code_only_aggregate_rss.json").write_text(json.dumps(report,indent=2)+"\n")
print(json.dumps(report),flush=True)
