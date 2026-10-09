"""Sample total GPU memory while Code-only model is loaded."""
import json,subprocess,time
from pathlib import Path
from rag.runtime.resident_models import resident_pool
EXE=Path(r"C:\llama\llama-server.exe")
def gpu():
 raw=subprocess.check_output(["nvidia-smi","--query-gpu=memory.used","--format=csv,noheader,nounits"],text=True)
 return int(raw.strip().splitlines()[0])
before=gpu()
try:
 resident_pool.embed_code("How does RAG validate source paths?",EXE)
 loaded=gpu()
 for _ in range(3):resident_pool.embed_code("Where are Git changes detected?",EXE)
 active=gpu()
finally:
 resident_pool.close()
after=gpu()
report={"before_mib":before,"loaded_mib":loaded,"after_queries_mib":active,"after_unload_mib":after,"capacity_mib":6144,"production_gate":"BLOCKED"}
Path(__file__).with_name("rag017_code_only_gpu_snapshot.json").write_text(json.dumps(report,indent=2)+"\n")
print(json.dumps(report),flush=True)
