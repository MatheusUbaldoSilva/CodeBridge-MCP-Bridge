"""P9-B interrupted transaction E2E in a disposable filesystem laboratory.

Two independent Python processes execute 'crash' and 'rescue'. The crash
process intentionally exits with os._exit(83) *after* fsync'ing an ARMED
journal and changing one fake shortcut. Rescue refuses any production
path and replays preimage only into the lab workspace. Never touches HKCU.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
from zipfile import ZipFile
from installer.rag_p9b_crash_preimage import create_crash_preimage,verify_crash_preimage
from installer.rag_p9b_rollback_journal import RollbackJournal,read_journal
from installer.rag_p9b_windows_shell_scope import MENU_LINKS,DESKTOP_LINK

class LabRegistry:
    def read_key(self,key):return {"exists":True,"values":{}}

def setup(root):
    root=Path(root).resolve()
    if root.exists():raise ValueError("LAB_EXISTS")
    if not root.parent.is_dir():raise ValueError("LAB_PARENT_INVALID")
    menu=root/"roaming"/"Microsoft"/"Windows"/"Start Menu"/"Programs"/"CodeBridge"
    menu.mkdir(parents=True)
    desktop=root/"desktop";desktop.mkdir()
    paths=[menu/name for name in MENU_LINKS]+[desktop/DESKTOP_LINK]
    for i,path in enumerate(paths):path.write_bytes(f"baseline-{i}".encode())
    preimage=root/"preimage.zip"
    r=create_crash_preimage(appdata=root/"roaming",desktop=desktop,
                            registry=LabRegistry(),output=preimage)
    if not r["created"]:raise RuntimeError(r)
    (root/"identity.json").write_text(json.dumps({"sha256":r["sha256"]}),encoding="utf-8")
    return {"state":"LAB_SETUP","files":len(paths),"preimage_verified":True}

def crash(root):
    root=Path(root).resolve()
    identity=json.loads((root/"identity.json").read_text(encoding="utf-8"))
    if not verify_crash_preimage(root/"preimage.zip",identity["sha256"])["verified"]:
        raise ValueError("PREIMAGE_INVALID")
    journal=RollbackJournal(root/"crash.journal.jsonl")
    journal("SHELL_BACKEND_ARMED",{"files":5,"keys":2})
    link=root/"roaming"/"Microsoft"/"Windows"/"Start Menu"/"Programs"/"CodeBridge"/MENU_LINKS[0]
    link.write_bytes(b"PARTIALLY_UPDATED_BY_CRASHED_CHILD")
    with link.open("rb+") as f:os.fsync(f.fileno())
    # Lab-only registry state is intentionally non-production JSON.
    (root/"fake_registry_state.json").write_text(
        json.dumps({"state":"PARTIALLY_INSTALLED","changed":True}),encoding="utf-8")
    os._exit(83)

def rescue(root):
    root=Path(root).resolve()
    identity=json.loads((root/"identity.json").read_text(encoding="utf-8"))
    preimage=root/"preimage.zip"
    if not verify_crash_preimage(preimage,identity["sha256"])["verified"]:
        return {"state":"LAB_RESCUE_REFUSED","reason":"PREIMAGE_INVALID"}
    journal=read_journal(root/"crash.journal.jsonl")
    if (journal.get("state")!="JOURNAL_OBSERVED_ONLY"
            or journal.get("last_state")!="SHELL_BACKEND_ARMED"):
        return {"state":"LAB_RESCUE_REFUSED","reason":"JOURNAL_INVALID"}
    menu=root/"roaming"/"Microsoft"/"Windows"/"Start Menu"/"Programs"/"CodeBridge"
    paths=[menu/name for name in MENU_LINKS]+[root/"desktop"/DESKTOP_LINK]
    with ZipFile(preimage) as z:
        meta=json.loads(z.read("manifest.json"))
        for i,item in enumerate(meta["links"]):
            target=paths[i]
            if target.is_symlink() or not target.is_file():
                return {"state":"LAB_RESCUE_REFUSED","reason":"TARGET_INVALID"}
        # Do not touch live CodeBridge. These paths must reside in this
        # explicitly created disposable test folder and carry lab baselines.
        for i,item in enumerate(meta["links"]):
            if item["exists"]:
                paths[i].write_bytes(z.read(f"links/{i}.bin"))
            else:
                paths[i].unlink(missing_ok=True)
        matched=all(
            (paths[i].is_file()==item["exists"] and
            (not item["exists"] or hashlib.sha256(paths[i].read_bytes()).hexdigest()==item["sha256"]))
            for i,item in enumerate(meta["links"]))
    fake_registry=root/"fake_registry_state.json"
    fake_registry.write_text(json.dumps(meta["registry"],sort_keys=True),encoding="utf-8")
    registry_ok=json.loads(fake_registry.read_text(encoding="utf-8"))==meta["registry"]
    return {"state":"LAB_E2E_RECOVERED" if matched and registry_ok else "LAB_POSTVERIFY_FAILED",
            "restored":matched and registry_ok,"files_checked":len(paths),
            "fake_registry_keys_checked":len(meta["registry"]),
            "registry_modified":False,"production_modified":False}

def main():
    a=argparse.ArgumentParser()
    a.add_argument("operation",choices=["setup","crash","rescue"])
    a.add_argument("root")
    args=a.parse_args()
    result=globals()[args.operation](args.root)
    print(json.dumps(result,sort_keys=True))
    if args.operation=="rescue" and not result.get("restored",False):return 2
    return 0

if __name__=="__main__":
    raise SystemExit(main())
