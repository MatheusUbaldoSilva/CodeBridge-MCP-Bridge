"""Probe isolated RAG payload using installed embedded Python, no mutation."""
import argparse,importlib.util,json,sys
from pathlib import Path
p=argparse.ArgumentParser()
p.add_argument("--payload",type=Path,required=True)
a=p.parse_args()
sys.path.insert(0,str(a.payload.resolve()))
names=("rag","numpy","qdrant_client","mcp","pydantic")
available={x:importlib.util.find_spec(x) is not None for x in names}
result={"python":sys.version.split()[0],"payload":str(a.payload),"available":available,"isolated_import_ok":False,"deployment_ready":False}
try:
 import rag.contracts,rag.runtime.production_search,rag.runtime.status
 result["isolated_import_ok"]=True
except Exception as exc:
 result["import_error"]=f"{type(exc).__name__}: {exc}"
result["deployment_ready"]=result["isolated_import_ok"] and all(available.values())
print(json.dumps(result,indent=2))
raise SystemExit(0 if result["deployment_ready"] else 2)
