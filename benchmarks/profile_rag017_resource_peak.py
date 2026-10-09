"""Windows-native resource sampling during experimental code-only searches."""
import ctypes,ctypes.wintypes as w
import concurrent.futures,json,subprocess,threading,time
from pathlib import Path
from rag.runtime.resident_models import ResidentEmbeddingPool
pool=ResidentEmbeddingPool()
exe=Path(r"C:\llama\llama-server.exe")
kernel=ctypes.windll.kernel32
class PMC(ctypes.Structure):
 _fields_=[("cb",w.DWORD),("PageFaultCount",w.DWORD),("PeakWorkingSetSize",ctypes.c_size_t),("WorkingSetSize",ctypes.c_size_t),("QuotaPeakPagedPoolUsage",ctypes.c_size_t),("QuotaPagedPoolUsage",ctypes.c_size_t),("QuotaPeakNonPagedPoolUsage",ctypes.c_size_t),("QuotaNonPagedPoolUsage",ctypes.c_size_t),("PagefileUsage",ctypes.c_size_t),("PeakPagefileUsage",ctypes.c_size_t)]
psapi=ctypes.windll.psapi
def rss(pid):
 handle=kernel.OpenProcess(0x1000,False,pid)
 if not handle:return None
 try:
  info=PMC();info.cb=ctypes.sizeof(info)
  return round(info.WorkingSetSize/1048576,2) if psapi.GetProcessMemoryInfo(handle,ctypes.byref(info),info.cb) else None
 finally:kernel.CloseHandle(handle)
samples=[]
stop=threading.Event()
def sample():
 while not stop.is_set():
  try:
   raw=subprocess.check_output(["nvidia-smi","--query-gpu=memory.used","--format=csv,noheader,nounits"],text=True,timeout=4)
   gpu=int(raw.strip().splitlines()[0])
   model=pool.code_lifecycle
   pid=model._process.pid if model is not None and model._process is not None else None
   samples.append({"gpu_mib":gpu,"code_pid":pid,"code_rss_mib":rss(pid) if pid else None})
  except Exception as e:samples.append({"error":str(e)})
  stop.wait(.10)
t=threading.Thread(target=sample,daemon=True);t.start()
times=[]
def query(i):
 start=time.perf_counter()
 v=pool.embed_code("Locate indexing and Git source "+str(i),exe)
 return {"ms":round((time.perf_counter()-start)*1000,2),"dims":len(v)}
try:
 times.append(query(0))
 with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
  times.extend(executor.map(query,range(1,13)))
finally:
 pool.close();stop.set();t.join(timeout=5)
good=[a for a in samples if "gpu_mib" in a]
rss_values=[a["code_rss_mib"] for a in good if a["code_rss_mib"] is not None]
result={"requests":times,"samples":len(good),"sampling_errors":[a["error"] for a in samples if "error" in a][:3],"peak_gpu_used_mib":max((a["gpu_mib"] for a in good),default=None),"peak_code_rss_mib":max(rss_values,default=None),"production_gate":"BLOCKED","note":"periodic sampled GPU device usage and resident code process working set; not total RAM of system or guaranteed transient peaks"}
Path(__file__).with_name("rag017_code_only_resource_peak.json").write_text(json.dumps(result,indent=2)+"\n",encoding="utf8")
print("RESULT",json.dumps({k:v for k,v in result.items() if k!="requests"}),flush=True)
