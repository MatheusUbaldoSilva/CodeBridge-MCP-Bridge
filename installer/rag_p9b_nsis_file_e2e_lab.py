"""NSIS file-scope interruption/recovery laboratory. No installed writes.

Uses an attested rollback ZIP, but all mutation is under a fresh,
caller-chosen disposable root. Exact 236 previous files and 22 new
targets are checked after artificial failed update and recovery.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path, PurePosixPath
from zipfile import ZipFile
from installer.rag_p9b_installer_rollback_scope import verify_installer_rollback_snapshot

_MARKER=b"P9B_LAB_INSTALLER_CREATED_V1"

def run_file_scope_lab(snapshot, installed, lab):
    refused={"state":"NSIS_FILE_LAB_REFUSED","verified":False,
             "production_modified":False,"nsis_executed":False}
    root=Path(lab).absolute()
    prod=Path(installed).resolve()
    if (root.exists() or root.is_symlink() or not root.parent.is_dir()
            or root.is_relative_to(prod)):
        return {**refused,"reason":"LAB_PATH_INVALID"}
    if not verify_installer_rollback_snapshot(snapshot,installed).get("verified"):
        return {**refused,"reason":"SNAPSHOT_UNVERIFIED"}
    try:
        with ZipFile(snapshot) as archive:
            manifest=json.loads(archive.read("manifest.json"))
            old=manifest["existing"]
            targets=manifest["targets"]
            if len(set(targets))!=len(targets):return {**refused,"reason":"DUPLICATE_TARGET"}
            root.mkdir()
            for rel,meta in old.items():
                p=root.joinpath(*PurePosixPath(rel).parts)
                p.parent.mkdir(parents=True,exist_ok=True)
                data=archive.read("old/"+rel)
                if hashlib.sha256(data).hexdigest()!=meta["sha256"]:
                    return {**refused,"reason":"OLD_CONTENT_CHANGED"}
                p.write_bytes(data)
            fresh=[x for x in targets if x not in old]
            # Simulate an interrupted NSIS file phase.
            changed=next(iter(old))
            root.joinpath(*PurePosixPath(changed).parts).write_bytes(b"P9B_MUTATED_BY_TEST")
            for rel in fresh:
                p=root.joinpath(*PurePosixPath(rel).parts)
                p.parent.mkdir(parents=True,exist_ok=True)
                p.write_bytes(_MARKER)
            if not fresh:return {**refused,"reason":"NO_CREATED_TARGETS"}
            # Independently recover from the persisted ZIP, never from
            # the initial in-memory file content.
            for rel,meta in old.items():
                p=root.joinpath(*PurePosixPath(rel).parts)
                p.write_bytes(archive.read("old/"+rel))
            for rel in fresh:
                p=root.joinpath(*PurePosixPath(rel).parts)
                if p.read_bytes()!=_MARKER:
                    return {**refused,"reason":"UNKNOWN_CREATED_TARGET_CONTENT"}
                p.unlink()
            good=all(
                hashlib.sha256(root.joinpath(*PurePosixPath(rel).parts).read_bytes()).hexdigest()==meta["sha256"]
                for rel,meta in old.items())
            good=good and all(not root.joinpath(*PurePosixPath(rel).parts).exists() for rel in fresh)
            return {**refused,"state":"NSIS_FILE_SCOPE_LAB_RECOVERED" if good else "NSIS_FILE_SCOPE_LAB_FAILED",
                    "verified":good,"old_files_restored":len(old),
                    "new_targets_removed":len(fresh),"used_real_snapshot":True}
    except (OSError,KeyError,TypeError,ValueError):
        return {**refused,"reason":"LAB_EXECUTION_FAILED"}
