"""Validate embedded Python prerequisites without modifying the installation."""
import argparse,importlib.util,json,sys
from pathlib import Path

REQUIRED=("mcp","pydantic","psutil","numpy","qdrant_client","rag")

def inspect_runtime(lookup=None):
 lookup=lookup or (lambda name:importlib.util.find_spec(name) is not None)
 available={name:bool(lookup(name)) for name in REQUIRED}
 return {"python":sys.version.split()[0],"dependencies":available,
         "missing":[name for name,present in available.items() if not present],
         "ready_for_rag":all(available.values()),"production_approved":False}

if __name__=="__main__":
 parser=argparse.ArgumentParser()
 parser.add_argument("--report",type=Path)
 args=parser.parse_args()
 data=inspect_runtime()
 output=json.dumps(data,indent=2)
 if args.report:
  if args.report.exists():raise FileExistsError("refuse to overwrite existing report")
  args.report.write_text(output+"\n",encoding="utf-8")
 print(output)
 raise SystemExit(0 if data["ready_for_rag"] else 2)
