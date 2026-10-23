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

def recover_externally(*,lab_root,nsis_snapshot,identity_file,identity_sha,
                        installed,identity_probe=verify_identity,
                        recoverer=recover_lab):
    result={"state":"EXTERNAL_RECOVERY_REFUSED","verified":False,
            "production_modified":False,"nsis_executed":False}
    root=Path(lab_root).resolve()
    live=Path(installed).resolve()
    if (root==live or root.is_relative_to(live)
            or not root.is_dir() or root.is_symlink()):
        return {**result,"reason":"LAB_PATH_INVALID"}
    try:
        marker=json.loads((root/"identity.json").read_text(encoding="utf-8"))
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
        return {**result,"state":"EXTERNAL_LAB_RECOVERY_VERIFIED",
                "verified":True,"old_files_checked":restored["old_files_checked"],
                "new_targets_removed":restored["new_targets_removed"],
                "shortcuts_checked":restored["shortcuts_checked"],
                "fake_registry_keys_checked":restored["fake_registry_keys_checked"]}
    except Exception:
        return {**result,"reason":"INDEPENDENT_RECOVERY_EXCEPTION"}
