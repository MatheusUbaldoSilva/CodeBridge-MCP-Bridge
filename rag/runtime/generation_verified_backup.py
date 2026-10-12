"""Immutable, verified test-generation backup; never touches production paths."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import shutil

from rag.runtime.generation_process_lock import generation_lock
from rag.runtime.incremental_bundle_validate import validate_incremental_bundle


class VerifiedBackupError(RuntimeError):
    pass


def _root(value):
    root = Path(value).resolve()
    if root.name.casefold() != "codebridge-rag-generation-test":
        raise VerifiedBackupError("backup restricted to isolated test roots")
    return root


def _hashes(folder):
    result = {}
    for file in sorted(folder.rglob("*")):
        if file.is_symlink():
            raise VerifiedBackupError("symlink forbidden in immutable backup")
        if file.is_file():
            result[file.relative_to(folder).as_posix()] = hashlib.sha256(file.read_bytes()).hexdigest()
    return result


def backup_generation(test_root, generation, backup_name):
    root = _root(test_root)
    if not isinstance(backup_name, str) or not backup_name.isidentifier():
        raise VerifiedBackupError("invalid backup name")
    if not isinstance(generation, str) or not generation.isidentifier():
        raise VerifiedBackupError("invalid generation")
    origin = (root / "generations" / generation).resolve()
    if origin.parent != (root / "generations").resolve() or not origin.is_dir():
        raise VerifiedBackupError("generation unavailable")
    destination = root / "backups" / backup_name
    if destination.exists():
        raise VerifiedBackupError("backup already exists; never overwrite")
    with generation_lock(root, generation):
        validate_incremental_bundle(origin)
        before = _hashes(origin)
        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copytree(origin, destination)
            copied = _hashes(destination)
            if copied != before:
                raise VerifiedBackupError("backup hashes differ from original")
            verified = validate_incremental_bundle(destination)
            manifest = root / "backups" / (backup_name + ".sha256.json")
            manifest.write_text(json.dumps(before, indent=2, sort_keys=True), encoding="utf-8")
            return {"state": "VERIFIED_TEST_BACKUP", "path": str(destination),
                    "files": len(before), "report": verified}
        except BaseException:
            shutil.rmtree(destination, ignore_errors=True)
            raise


def verify_generation_backup(test_root, backup_name):
    root = _root(test_root)
    if not isinstance(backup_name, str) or not backup_name.isidentifier():
        raise VerifiedBackupError("invalid backup name")
    folder = root / "backups" / backup_name
    manifest = root / "backups" / (backup_name + ".sha256.json")
    if not folder.is_dir() or not manifest.is_file():
        raise VerifiedBackupError("backup or manifest missing")
    expected = json.loads(manifest.read_text(encoding="utf-8"))
    if _hashes(folder) != expected:
        raise VerifiedBackupError("backup hash mismatch")
    return validate_incremental_bundle(folder)
