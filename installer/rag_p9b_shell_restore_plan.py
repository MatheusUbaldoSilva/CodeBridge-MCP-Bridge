"""Fail-closed restoration manifest for CodeBridge-owned HKCU and links.

Produces a deterministic plan, not a live registry or filesystem restore.
The NSIS change-set and backup must be verified separately at apply time.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from zipfile import ZipFile, BadZipFile

from installer.rag_p9b_shell_snapshot import verify_shell_snapshot
from installer.rag_p9b_windows_shell_scope import APP_KEYS, MENU_LINKS, DESKTOP_LINK


def build_shell_restore_plan(snapshot, *, appdata, desktop,
                             expected_snapshot_sha256, installed_stopped=False):
    denied=dict(state="SHELL_RESTORE_PLAN_REFUSED", verified=False,
                registry_modified=False, shortcuts_modified=False,
                production_restore_authorized=False)
    source=Path(snapshot)
    digest=str(expected_snapshot_sha256).lower()
    if (len(digest)!=64 or any(c not in "0123456789abcdef" for c in digest)
            or not source.is_file() or source.is_symlink()):
        return {**denied,"reason":"SNAPSHOT_IDENTITY_INVALID"}
    if hashlib.sha256(source.read_bytes()).hexdigest()!=digest:
        return {**denied,"reason":"SNAPSHOT_HASH_MISMATCH"}
    if not verify_shell_snapshot(source).get("verified"):
        return {**denied,"reason":"SNAPSHOT_UNVERIFIED"}
    if installed_stopped is not True:
        return {**denied,"reason":"INSTALLATION_MUST_BE_STOPPED"}
    try:
        with ZipFile(source) as archive:
            manifest=json.loads(archive.read("manifest.json"))
            names=archive.namelist()
            if len(names)!=len(set(names)):
                return {**denied,"reason":"DUPLICATE_ZIP_MEMBERS"}
            links=manifest["shortcuts"]
            if len(links)!=5:
                return {**denied,"reason":"SHORTCUT_COUNT_CHANGED"}
            paths=[Path(appdata)/"Microsoft"/"Windows"/"Start Menu"/"Programs"/"CodeBridge"/n
                   for n in MENU_LINKS]+[Path(desktop)/DESKTOP_LINK]
            actions=[]
            expected_members={"manifest.json"}
            for idx,(item,target) in enumerate(zip(links,paths)):
                if item.get("slot")!=idx or item.get("name")!=target.name:
                    return {**denied,"reason":"SHORTCUT_IDENTITY_MISMATCH"}
                if target.is_symlink() or (target.exists() and not target.is_file()):
                    return {**denied,"reason":"TARGET_PATH_NOT_REGULAR"}
                if item.get("exists") is True:
                    member=f"links/{idx}.bin"
                    expected_members.add(member)
                    blob=archive.read(member)
                    if (not 0<len(blob)<=65536
                            or hashlib.sha256(blob).hexdigest()!=item.get("sha256")
                            or item.get("bytes")!=len(blob)):
                        return {**denied,"reason":"LINK_CONTENT_INVALID"}
                    action="RESTORE_PREVIOUS_FILE"
                elif item.get("exists") is False:
                    action="REMOVE_NSIS_CREATED_FILE_IF_PRESENT"
                else:
                    return {**denied,"reason":"LINK_EXISTENCE_UNVERIFIED"}
                actions.append({"slot":idx,"name":target.name,"action":action})
            if set(names)!=expected_members:
                return {**denied,"reason":"UNEXPECTED_SNAPSHOT_MEMBERS"}
            if set(manifest["registry"])!=set(APP_KEYS):
                return {**denied,"reason":"REGISTRY_SCOPE_CHANGED"}
            registry=[]
            for key in APP_KEYS:
                item=manifest["registry"][key]
                if not isinstance(item.get("exists"),bool) or not isinstance(item.get("values"),dict):
                    return {**denied,"reason":"REGISTRY_SCHEMA_UNVERIFIED"}
                registry.append({"key":key,
                                 "action":("RESTORE_PREVIOUS_VALUES" if item["exists"]
                                           else "REMOVE_ONLY_NSIS_CREATED_KEY")})
        return {**denied,"state":"SHELL_RESTORE_PLAN_ONLY",
                "verified":True,"snapshot_sha256":digest,
                "shortcut_actions":actions,"registry_actions":registry,
                "requires_fresh_nsis_guard":True,
                "requires_independent_execution":True}
    except (OSError,ValueError,KeyError,TypeError,BadZipFile):
        return {**denied,"reason":"SNAPSHOT_PARSE_FAILED"}
