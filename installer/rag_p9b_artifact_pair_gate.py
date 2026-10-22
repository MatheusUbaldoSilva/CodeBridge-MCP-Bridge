"""Read-only identity gate for a P9-B NSIS installer/rollback pair.

Never approves installer execution. Exact artifact identity matters more
than any release directory label or previous, cached process observation.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from zipfile import ZipFile, BadZipFile

from installer.rag_p9b_installer_rollback_scope import (
    verify_installer_rollback_snapshot, inspect_installer_snapshot_baseline,
)


def assess_artifact_pair(installer, snapshot, installed, *,
                         expected_installer_sha256, expected_snapshot_sha256,
                         expected_source_commit):
    result={"state":"ARTIFACT_PAIR_REFUSED","paired":False,
            "read_only":True,"installer_executed":False,
            "operator_execution_authorized":False,
            "installed_modified":False}
    installer=Path(installer)
    snapshot=Path(snapshot)
    installed=Path(installed)
    expected_installer_sha256=str(expected_installer_sha256).lower()
    expected_snapshot_sha256=str(expected_snapshot_sha256).lower()
    source=str(expected_source_commit).lower()
    hashes=(expected_installer_sha256, expected_snapshot_sha256, source)
    if (any(len(v) != n or any(c not in "0123456789abcdef" for c in v)
            for v,n in zip(hashes,(64,64,40)))
            or not installer.is_file() or installer.is_symlink()
            or not snapshot.is_file() or snapshot.is_symlink()):
        return {**result,"reason":"ARTIFACT_IDENTITY_UNVERIFIED"}
    try:
        exe_hash=hashlib.sha256(installer.read_bytes()).hexdigest()
        zip_hash=hashlib.sha256(snapshot.read_bytes()).hexdigest()
        if exe_hash!=expected_installer_sha256 or zip_hash!=expected_snapshot_sha256:
            return {**result,"reason":"ARTIFACT_HASH_MISMATCH"}
        with ZipFile(snapshot) as z:
            metadata=json.loads(z.read("manifest.json"))
        if metadata.get("installer_sha256") != exe_hash:
            return {**result,"reason":"BACKUP_INSTALLER_BINDING_MISMATCH"}
        proof=verify_installer_rollback_snapshot(snapshot,installed)
        if not proof.get("verified"):
            return {**result,"reason":"ROLLBACK_MANIFEST_UNVERIFIED"}
        baseline=inspect_installer_snapshot_baseline(snapshot,installed)
        if not baseline.get("matches"):
            return {**result,"reason":"INSTALLED_BASELINE_CHANGED"}
        return {**result, "state":"ARTIFACT_PAIR_VERIFIED_ONLY",
                "paired":True,"installer_sha256":exe_hash,
                "snapshot_sha256":zip_hash,
                "source_commit":source,
                "installed_files_checked":baseline.get("files_checked"),
                "requires_stopped_processes":True}
    except (OSError,ValueError,KeyError,BadZipFile,TypeError):
        return {**result,"reason":"ARTIFACT_READ_UNVERIFIED"}
