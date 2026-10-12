"""Reconstruct a verified backup into a NEW isolated test generation.

No production paths, no pointer activation and no automatic deletion of
previous generations. Source bundles must already be fully offline.
"""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import tempfile

from rag.runtime.generation_activation import PUBLICATION_LOCK_NAME
from rag.runtime.generation_process_lock import generation_lock
from rag.runtime.generation_pointer import resolve_generation
from rag.runtime.generation_transition_journal import inspect_pending_transition
from rag.runtime.generation_verified_backup import (
    VerifiedBackupError, _hashes, verify_generation_backup)
from rag.runtime.incremental_bundle_validate import validate_incremental_bundle


class BackupRestoreCopyError(RuntimeError):
    pass


def restore_verified_backup_as_test_copy(root, backup_name, target_name,
                                         *, fail_after_copy=False):
    root = Path(root).resolve()
    if root.name.casefold() != "codebridge-rag-generation-test":
        raise BackupRestoreCopyError("isolated test root required")
    if any(not isinstance(x, str) or not x.isidentifier()
           or len(x) > 64 for x in (backup_name, target_name)):
        raise BackupRestoreCopyError("invalid backup or target name")
    backups = root / "backups"
    source = backups / backup_name
    digest_file = backups / (backup_name + ".sha256.json")
    generations = root / "generations"
    target = generations / target_name
    # A symlink in a parent or source may redirect an apparently isolated copy.
    if any(path.is_symlink() for path in
           (backups, source, digest_file, generations, target)):
        raise BackupRestoreCopyError("symlinks prohibited in backup or destination")

    with generation_lock(root, PUBLICATION_LOCK_NAME, exclusive=True):
        if inspect_pending_transition(root)["state"] != "NO_PENDING_TRANSITION":
            raise BackupRestoreCopyError("unresolved transition")
        if target.exists() or target.is_symlink():
            raise BackupRestoreCopyError("generation exists; overwrite refused")
        if not generations.is_dir() or not source.is_dir():
            raise BackupRestoreCopyError("generation directory or backup unavailable")
        try:
            reference = verify_generation_backup(root, backup_name)
            expected_hashes = _hashes(source)
        except Exception as exc:
            raise BackupRestoreCopyError("backup verification failed") from exc
        active_before = resolve_generation(root)
        selected_before = active_before.generation if active_before else None
        staging = Path(tempfile.mkdtemp(prefix=".restore-copy-", dir=generations))
        try:
            temporary = staging / "candidate"
            shutil.copytree(source, temporary, symlinks=False)
            if fail_after_copy:
                raise BackupRestoreCopyError("injected failure after copying")
            if _hashes(temporary) != expected_hashes:
                raise BackupRestoreCopyError("copied hashes differ")
            verified = validate_incremental_bundle(temporary)
            if verified != reference:
                raise BackupRestoreCopyError("cross-store report changed")
            if target.exists() or target.is_symlink():
                raise BackupRestoreCopyError("generation appeared during restore")
            os.rename(temporary, target)
            active_after = resolve_generation(root)
            if (active_after.generation if active_after else None) != selected_before:
                raise BackupRestoreCopyError("active pointer changed during restore")
            return {"state": "TEST_RESTORED_COPY_NOT_ACTIVATED",
                    "generation": target_name,
                    "active_generation": selected_before,
                    "report": verified}
        finally:
            shutil.rmtree(staging, ignore_errors=True)
