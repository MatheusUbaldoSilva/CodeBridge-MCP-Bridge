"""Read-only snapshot of disposable Windows installer test environment."""
import argparse,hashlib,json,os
from pathlib import Path
def fingerprint(root:Path):
 return {str(x.relative_to(root)).replace("\\","/"):hashlib.sha256(x.read_bytes()).hexdigest() for x in root.rglob("*") if x.is_file()}
def capture(root:Path,out:Path):
 root=root.resolve();out=out.resolve()
 if "CodeBridge-RAG017-VMTest-" not in root.name:raise ValueError("not a dedicated test directory")
 if not root.is_dir():raise FileNotFoundError(root)
 if out.exists():raise FileExistsError(out)
 result={"root":str(root),"files":fingerprint(root),"registry_snapshot_verified":False,"shortcuts_snapshot_verified":False,"services_snapshot_verified":False,"vm_snapshot_verified":False}
 out.write_text(json.dumps(result,indent=2,sort_keys=True),encoding="utf-8")
 return result
if __name__=="__main__":
 p=argparse.ArgumentParser();p.add_argument("--root",required=True,type=Path);p.add_argument("--out",required=True,type=Path);a=p.parse_args()
 print(json.dumps({"captured_files":len(capture(a.root,a.out)["files"]),"full_rollback_verified":False}))
