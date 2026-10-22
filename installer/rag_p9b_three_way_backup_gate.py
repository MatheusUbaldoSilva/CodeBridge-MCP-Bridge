"""Read-only consistency gate for NSIS, file rollback and shell rollback."""
from __future__ import annotations

import hashlib
from pathlib import Path
from installer.rag_p9b_artifact_pair_gate import assess_artifact_pair
from installer.rag_p9b_shell_postverify import verify_restored_shell


def verify_three_way(installer, file_snapshot, shell_snapshot, installed, *,
                     installer_hash, file_snapshot_hash, shell_snapshot_hash,
                     source_commit, appdata, desktop, pair_probe=None,
                     shell_probe=None):
    result=dict(state="THREE_WAY_BACKUP_UNVERIFIED",
                verified=False,read_only=True,nsis_executed=False,
                installed_modified=False,authorized=False)
    pair_probe=pair_probe or assess_artifact_pair
    shell_probe=shell_probe or verify_restored_shell
    pair=pair_probe(installer,file_snapshot,installed,
                    expected_installer_sha256=installer_hash,
                    expected_snapshot_sha256=file_snapshot_hash,
                    expected_source_commit=source_commit)
    if pair.get("paired") is not True:
        return {**result,"reason":"FILE_ROLLBACK_PAIR_INVALID"}
    digest=str(shell_snapshot_hash).lower()
    file=Path(shell_snapshot)
    if (len(digest)!=64 or any(c not in "0123456789abcdef" for c in digest)
            or not file.is_file() or file.is_symlink()
            or hashlib.sha256(file.read_bytes()).hexdigest()!=digest):
        return {**result,"reason":"SHELL_SNAPSHOT_DIGEST_INVALID"}
    shell=shell_probe(file,appdata=appdata,desktop=desktop)
    if shell.get("verified") is not True:
        return {**result,"reason":"SHELL_BASELINE_CHANGED",
                "shell_reason":shell.get("reason")}
    return {**result,"state":"THREE_WAY_BACKUP_OBSERVED_ONLY",
            "verified":True,"requires_live_process_shutdown":True,
            "requires_live_nsis_guard":True,
            "requires_full_rollback_executor":True}
