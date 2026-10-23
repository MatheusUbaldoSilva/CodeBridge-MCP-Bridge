"""Single-process-crash, second-process recovery of P9-B file+shell scope.

Entirely disposable lab; real NSIS snapshot is read-only input.
No production Windows registry, installed paths or NSIS execution.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path,PurePosixPath
from zipfile import ZipFile
from installer.rag_p9b_crash_preimage import create_crash_preimage,verify_crash_preimage
from installer.rag_p9b_rollback_journal import RollbackJournal,read_journal
from installer.rag_p9b_installer_rollback_scope import verify_installer_rollback_snapshot
from installer.rag_p9b_windows_shell_scope import MENU_LINKS,DESKTOP_LINK

MARK=b"LAB_NSIS_CREATED_ONLY"
class LabRegistry:
    def read_key(self,key):return {"exists":True,"values":{}}

def prepare(root,zip_path,installed):
    root=Path(root).resolve()
    if root.exists() or not root.parent.is_dir() or root.is_relative_to(Path(installed).resolve()):
        raise ValueError("UNSAFE_LAB")
    if not verify_installer_rollback_snapshot(zip_path,installed).get("verified"):
        raise ValueError("NSIS_BACKUP_UNVERIFIED")
    menu=root/"roaming"/"Microsoft"/"Windows"/"Start Menu"/"Programs"/"CodeBridge"
    menu.mkdir(parents=True)
    (root/"desktop").mkdir()
    for i,name in enumerate([*MENU_LINKS,DESKTOP_LINK]):
        target=(menu/name) if i<4 else (root/"desktop"/name)
        target.write_bytes(f"shell-original-{i}".encode())
    preimage=root/"preimage.zip"
    proof=create_crash_preimage(appdata=root/"roaming",desktop=root/"desktop",
                                registry=LabRegistry(),output=preimage)
    if not proof["created"]:raise ValueError("SHELL_PREIMAGE_FAILED")
    with ZipFile(zip_path) as archive:
        manifest=json.loads(archive.read("manifest.json"))
        for rel,meta in manifest["existing"].items():
            target=root/"installed"/Path(*PurePosixPath(rel).parts)
            target.parent.mkdir(parents=True,exist_ok=True)
            blob=archive.read("old/"+rel)
            if hashlib.sha256(blob).hexdigest()!=meta["sha256"]:
                raise ValueError("BACKUP_FILE_INVALID")
            target.write_bytes(blob)
    (root/"identity.json").write_text(json.dumps({"schema":1,
        "purpose":"P9B_DISPOSABLE_UNIFIED_LAB",
        "shell_sha":proof["sha256"],
        "file_sha":hashlib.sha256(Path(zip_path).read_bytes()).hexdigest()}),encoding="utf-8")
    return {"state":"UNIFIED_LAB_READY","baseline_files":len(manifest["existing"])}

def interrupt(root,zip_path):
    root=Path(root).resolve()
    identity=json.loads((root/"identity.json").read_text(encoding="utf-8"))
    if identity.get("purpose")!="P9B_DISPOSABLE_UNIFIED_LAB" or identity.get("schema")!=1:
        raise ValueError("NOT_DISPOSABLE_LAB")
    if not verify_crash_preimage(root/"preimage.zip",identity["shell_sha"])["verified"]:
        raise ValueError("SHELL_INVALID")
    if hashlib.sha256(Path(zip_path).read_bytes()).hexdigest()!=identity["file_sha"]:
        raise ValueError("FILE_ZIP_CHANGED")
    RollbackJournal(root/"interrupted.journal.jsonl")("SHELL_BACKEND_ARMED",{"files":5,"keys":2})
    with ZipFile(zip_path) as z:
        manifest=json.loads(z.read("manifest.json"))
    old=next(iter(manifest["existing"]))
    (root/"installed"/Path(*PurePosixPath(old).parts)).write_bytes(b"INTERRUPTED_UPDATE")
    for rel in (r for r in manifest["targets"] if r not in manifest["existing"]):
        target=root/"installed"/Path(*PurePosixPath(rel).parts)
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes(MARK)
    menu=root/"roaming"/"Microsoft"/"Windows"/"Start Menu"/"Programs"/"CodeBridge"
    (menu/MENU_LINKS[0]).write_bytes(b"INTERRUPTED_SHORTCUT")
    (root/"fake_registry.json").write_text('{"installed":true}',encoding="utf-8")
    os._exit(83)

def recover(root,zip_path):
    base={"state":"UNIFIED_LAB_REFUSED","recovered":False,"production_modified":False}
    root=Path(root).resolve()
    identity=json.loads((root/"identity.json").read_text(encoding="utf-8"))
    if identity.get("purpose")!="P9B_DISPOSABLE_UNIFIED_LAB" or identity.get("schema")!=1:
        return {**base,"reason":"NOT_DISPOSABLE_LAB"}
    if (not verify_crash_preimage(root/"preimage.zip",identity["shell_sha"])["verified"]
            or hashlib.sha256(Path(zip_path).read_bytes()).hexdigest()!=identity["file_sha"]):
        return {**base,"reason":"BACKUP_CHANGED"}
    journal=read_journal(root/"interrupted.journal.jsonl")
    if journal.get("last_state")!="SHELL_BACKEND_ARMED" or journal.get("count")!=1:
        return {**base,"reason":"JOURNAL_INVALID"}
    with ZipFile(zip_path) as z,ZipFile(root/"preimage.zip") as shell:
        m=json.loads(z.read("manifest.json")); sm=json.loads(shell.read("manifest.json"))
        new=[name for name in m["targets"] if name not in m["existing"]]
        # Validate all new targets BEFORE modifying any existing baseline.
        for rel in new:
            target=root/"installed"/Path(*PurePosixPath(rel).parts)
            if not target.is_file() or target.is_symlink() or target.read_bytes()!=MARK:
                return {**base,"reason":"UNKNOWN_CREATED_FILE"}
        menu=root/"roaming"/"Microsoft"/"Windows"/"Start Menu"/"Programs"/"CodeBridge"
        shell_paths=[menu/name for name in MENU_LINKS]+[root/"desktop"/DESKTOP_LINK]
        # Preflight every writable path before the first restoration write.
        if any(path.is_symlink() for path in shell_paths):
            return {**base,"reason":"SHELL_SYMLINK"}
        if any((root/"installed"/Path(*PurePosixPath(rel).parts)).is_symlink()
               for rel in m["existing"]):
            return {**base,"reason":"LINKED_BASELINE"}
        for rel,meta in m["existing"].items():
            target=root/"installed"/Path(*PurePosixPath(rel).parts)
            target.write_bytes(z.read("old/"+rel))
        for rel in new:
            (root/"installed"/Path(*PurePosixPath(rel).parts)).unlink()
        for i,item in enumerate(sm["links"]):
            if item["exists"]:shell_paths[i].write_bytes(shell.read(f"links/{i}.bin"))
            else:shell_paths[i].unlink(missing_ok=True)
        (root/"fake_registry.json").write_text(json.dumps(sm["registry"],sort_keys=True),encoding="utf-8")
        files_ok=all(
            hashlib.sha256((root/"installed"/Path(*PurePosixPath(rel).parts)).read_bytes()).hexdigest()==meta["sha256"]
            for rel,meta in m["existing"].items())
        files_ok=files_ok and all(not (root/"installed"/Path(*PurePosixPath(rel).parts)).exists() for rel in new)
        shell_ok=all(hashlib.sha256(shell_paths[i].read_bytes()).hexdigest()==item["sha256"]
                     for i,item in enumerate(sm["links"]) if item["exists"])
        registry_ok=json.loads((root/"fake_registry.json").read_text(encoding="utf-8"))==sm["registry"]
    verified=files_ok and shell_ok and registry_ok
    return {**base,"state":"UNIFIED_LAB_RECOVERED" if verified else "UNIFIED_LAB_POSTVERIFY_FAILED",
            "recovered":verified,"old_files_checked":len(m["existing"]),
            "new_targets_removed":len(new),"shortcuts_checked":len(sm["links"]),
            "fake_registry_keys_checked":len(sm["registry"])}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("action",choices=["prepare","interrupt","recover"])
    ap.add_argument("root")
    ap.add_argument("snapshot")
    ap.add_argument("installed")
    a=ap.parse_args()
    fn={"prepare":prepare,"interrupt":interrupt,"recover":recover}[a.action]
    result=fn(a.root,a.snapshot,a.installed) if a.action=="prepare" else fn(a.root,a.snapshot)
    print(json.dumps(result,sort_keys=True))
    return 0 if a.action!="recover" or result.get("recovered") else 2

if __name__=="__main__":
    raise SystemExit(main())
