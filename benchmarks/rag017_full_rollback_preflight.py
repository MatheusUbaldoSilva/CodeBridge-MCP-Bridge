"""Fail-closed preflight for RAG-017 full-NSIS rollback testing."""
import argparse,json,re,shutil
from pathlib import Path

SIDE_EFFECTS=("WriteRegStr","WriteRegDWORD","CreateShortcut","nsExec::Exec","WriteUninstaller","ExecWait")

def inspect(nsis:Path, vm_verified:bool=False):
 text=nsis.read_text(encoding="utf-8-sig")
 observed={name:bool(re.search(r"\b"+re.escape(name)+r"\b",text,re.I)) for name in SIDE_EFFECTS}
 effects=any(observed.values())
 return {"installer":str(nsis),"global_side_effects":observed,
         "side_effects_present":effects,"disposable_vm_verified":bool(vm_verified),
         "host_execution_allowed":False,
         "rollback_full_test_allowed":bool(vm_verified),
         "rollback_full_verified":False}

if __name__=="__main__":
 ap=argparse.ArgumentParser();ap.add_argument("--nsis",type=Path,required=True);args=ap.parse_args()
 out=inspect(args.nsis)
 print(json.dumps(out,indent=2))
 raise SystemExit(0 if out["rollback_full_test_allowed"] else 2)
