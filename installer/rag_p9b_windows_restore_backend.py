"""Bounded shell restore backend using an explicit injected registry interface.

Production use must be approved by an independent coordinator. Provides
compensation on partial failures; never promises filesystem/registry atomicity.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from zipfile import ZipFile

from installer.rag_p9b_shell_snapshot import verify_shell_snapshot
from installer.p9b_update_process_guard import inspect_update_processes
from installer.rag_p9b_windows_shell_scope import APP_KEYS,MENU_LINKS,DESKTOP_LINK


def restore_shell(*, snapshot, expected_sha256, appdata, desktop, registry, installed,
                  stopped=False, external=False, execute=False, journal=None,
                  process_guard=inspect_update_processes):
    base={"state":"SHELL_BACKEND_REFUSED","verified":False,
          "rollback_attempted":False}
    if stopped is not True or external is not True or execute is not True or journal is None:
        return {**base,"reason":"EXPLICIT_INDEPENDENT_STOPPED_GATES_REQUIRED"}
    expected=str(expected_sha256).lower()
    file=Path(snapshot)
    if (len(expected)!=64 or any(c not in "0123456789abcdef" for c in expected)
            or not file.is_file() or file.is_symlink()
            or hashlib.sha256(file.read_bytes()).hexdigest()!=expected):
        return {**base,"reason":"SNAPSHOT_DIGEST_MISMATCH"}
    if not verify_shell_snapshot(snapshot).get("verified"):
        return {**base,"reason":"SNAPSHOT_UNVERIFIED"}
    try:
        guard=process_guard(installed)
    except Exception:
        return {**base,"reason":"PROCESS_GUARD_UNAVAILABLE"}
    if not isinstance(guard,dict) or guard.get("state")!="NO_RUNNING_CODEBRIDGE":
        return {**base,"reason":"CODEBRIDGE_PROCESS_STILL_ACTIVE"}
    targets=[Path(appdata)/"Microsoft"/"Windows"/"Start Menu"/"Programs"/"CodeBridge"/n
             for n in MENU_LINKS]+[Path(desktop)/DESKTOP_LINK]
    prior={}
    old_registry={}
    registry_touched=[]
    try:
        # Pre-read every target and HKCU key before writing the first byte.
        for t in targets:
            if t.is_symlink() or (t.exists() and not t.is_file()):
                return {**base,"reason":"UNTRUSTED_DESTINATION"}
            prior[t]=t.read_bytes() if t.is_file() else None
        for key in APP_KEYS:
            old_registry[key]=registry.read_key(key)
        with ZipFile(snapshot) as z:
            m=json.loads(z.read("manifest.json"))
            desired=[z.read(f"links/{i}.bin") if item["exists"] else None
                     for i,item in enumerate(m["shortcuts"])]
            wanted_registry=m["registry"]
        journal("SHELL_BACKEND_ARMED",{"files":len(targets),"keys":len(APP_KEYS)})
        affected=[]
        try:
            for t,data in zip(targets,desired):
                t.parent.mkdir(parents=True,exist_ok=True)
                # Treat a failing write as potentially modifying the target.
                affected.append(t)
                if data is None:
                    t.unlink(missing_ok=True)
                else:
                    t.write_bytes(data)
            for key in APP_KEYS:
                registry_touched.append(key)
                registry.replace_key(key,wanted_registry[key])
            journal("SHELL_BACKEND_WRITTEN",{})
            return {"state":"SHELL_BACKEND_APPLIED_POSTVERIFY_REQUIRED",
                    "verified":False,"rollback_attempted":False}
        except Exception as exc:
            journal("SHELL_BACKEND_PARTIAL_FAILURE",{"exception":type(exc).__name__})
            compensation_errors=[]
            for key in reversed(registry_touched):
                try:registry.replace_key(key,old_registry[key])
                except Exception:compensation_errors.append("REGISTRY")
            for t in reversed(affected):
                try:
                    if prior[t] is None:t.unlink(missing_ok=True)
                    else:t.write_bytes(prior[t])
                except Exception:compensation_errors.append("SHORTCUT")
            try:
                for key in registry_touched:
                    if registry.read_key(key)!=old_registry[key]:
                        compensation_errors.append("REGISTRY_POSTVERIFY")
                for t in affected:
                    previous=prior[t]
                    actual=t.read_bytes() if t.is_file() else None
                    if actual!=previous:
                        compensation_errors.append("SHORTCUT_POSTVERIFY")
            except Exception:
                compensation_errors.append("POSTVERIFY_EXCEPTION")
            return {"state":"SHELL_BACKEND_RECOVERY_REVIEW_REQUIRED",
                    "verified":False,"rollback_attempted":True,
                    "compensation_verified":not compensation_errors,
                    "compensation_errors":sorted(set(compensation_errors))}
    except Exception as exc:
        return {**base,"reason":"PREFLIGHT_OR_JOURNAL_FAILED",
                "exception":type(exc).__name__}
