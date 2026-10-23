"""Separate-process recovery executor for a disposable P9-B lab.

Uses the existing unified test transaction's durable disk artifacts.
Never launches NSIS or accesses production HKCU. The caller must supply
a fresh scratch identity; no implicit production fallback exists.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
from installer.rag_p9b_unified_e2e_lab import recover as recover_lab
from installer.rag_p9b_transaction_identity import verify_identity

def _unique_lab_identity_pairs(pairs):
    result={}
    for key,value in pairs:
        if key in result:
            raise ValueError("DUPLICATE_LAB_IDENTITY_KEY")
        result[key]=value
    return result


def recover_externally(*,lab_root,nsis_snapshot,identity_file,identity_sha,
                        installed,identity_probe=verify_identity,
                        recoverer=recover_lab):
    result={"state":"EXTERNAL_RECOVERY_REFUSED","verified":False,
            "production_modified":False,"nsis_executed":False}
    raw_root=Path(lab_root)
    root=raw_root.resolve()
    live=Path(installed).resolve()
    if (raw_root.is_symlink() or root==live or root.is_relative_to(live)
            or live.is_relative_to(root)
            or not root.is_dir() or root.is_symlink()):
        return {**result,"reason":"LAB_PATH_INVALID"}
    try:
        identity_path=root/"identity.json"
        if not identity_path.is_file() or identity_path.is_symlink():
            return {**result,"reason":"LAB_IDENTITY_INVALID"}
        marker=json.loads(identity_path.read_text(encoding="utf-8"),
                          object_pairs_hook=_unique_lab_identity_pairs)
        if (not isinstance(marker,dict)
                or marker.get("purpose")!="P9B_DISPOSABLE_UNIFIED_LAB"
                or type(marker.get("schema")) is not int
                or marker["schema"]!=1):
            return {**result,"reason":"LAB_IDENTITY_INVALID"}
        verified=identity_probe(identity_file,identity_sha)
        if verified.get("verified") is not True:
            return {**result,"reason":"TRANSACTION_IDENTITY_UNVERIFIED"}
        snap_hash=hashlib.sha256(Path(nsis_snapshot).read_bytes()).hexdigest()
        if snap_hash != marker.get("file_sha"):
            return {**result,"reason":"LAB_SNAPSHOT_MISMATCH"}
        restored=recoverer(root,nsis_snapshot)
        if restored.get("state")!="UNIFIED_LAB_RECOVERED" or restored.get("recovered") is not True:
            return {**result,"state":"EXTERNAL_RECOVERY_REVIEW_REQUIRED",
                    "reason":"INDEPENDENT_POSTVERIFY_FAILED"}
        counts=tuple(restored.get(key) for key in (
            "old_files_checked","new_targets_removed",
            "shortcuts_checked","fake_registry_keys_checked"))
        if (any(type(value) is not int for value in counts)
                or counts[0]<1 or counts[1]<0 or counts[2]!=5 or counts[3]!=2):
            return {**result,"state":"EXTERNAL_RECOVERY_REVIEW_REQUIRED",
                    "reason":"POSTVERIFY_COUNTS_INVALID"}
        return {**result,"state":"EXTERNAL_LAB_RECOVERY_VERIFIED",
                "verified":True,"old_files_checked":restored["old_files_checked"],
                "new_targets_removed":restored["new_targets_removed"],
                "shortcuts_checked":restored["shortcuts_checked"],
                "fake_registry_keys_checked":restored["fake_registry_keys_checked"]}
    except Exception:
        return {**result,"reason":"INDEPENDENT_RECOVERY_EXCEPTION"}
