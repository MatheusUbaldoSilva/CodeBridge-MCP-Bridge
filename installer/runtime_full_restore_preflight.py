"""Read-only full rollback readiness inventory for supervised maintenance.

Does not copy/restore files or stop CodeBridge.
"""
from __future__ import annotations

import hashlib
import shutil
from pathlib import Path


def inspect_full_restore_readiness(
    install_root: Path, installer_path: Path, digest_path: Path,
    backup_destination: Path,
) -> dict:
    root = Path(install_root).resolve()
    installer = Path(installer_path).resolve()
    digest = Path(digest_path).resolve()
    backup = Path(backup_destination).absolute()
    runtime = root / "runtime" / "python"
    result = {
        "state": "FULL_RESTORE_NOT_VERIFIED",
        "verified": False,
        "writes_performed": False,
        "installation_modified": False,
        "independent_recovery_required": True,
        "backup_outside_installation": not backup.is_relative_to(root),
        "installer_checksum_matches": False,
        "runtime_bytes": None,
        "backup_free_bytes": None,
    }
    if backup.is_relative_to(root) or not backup.parent.is_dir():
        return result
    if not runtime.is_dir() or not installer.is_file() or not digest.is_file():
        return result
    # The checksum is a trust signal for the installer, not an assurance that
    # it contains every existing binary/package needed to restore a live runtime.
    checksum = digest.read_text(encoding="ascii").split()
    if not checksum or len(checksum[0]) != 64:
        return result
    actual = hashlib.sha256()
    with installer.open("rb") as handle:
        for part in iter(lambda: handle.read(1024 * 1024), b""):
            actual.update(part)
    result["installer_checksum_matches"] = (
        actual.hexdigest().lower() == checksum[0].lower())
    total = 0
    try:
        for file in runtime.rglob("*"):
            if file.is_file() and not file.is_symlink():
                total += file.stat().st_size
        free = shutil.disk_usage(backup.parent).free
    except OSError:
        return result
    result["runtime_bytes"] = total
    result["backup_free_bytes"] = free
    result["sufficient_space_for_runtime_copy"] = free >= total * 2
    # Still do not declare a real rollback verified: bytes/hash alone cannot
    # prove a rehearsed restoration with independent access to the computer.
    result["state"] = ("RESTORE_PREREQUISITES_PRESENT"
                       if result["installer_checksum_matches"]
                       and result["sufficient_space_for_runtime_copy"]
                       else "FULL_RESTORE_NOT_VERIFIED")
    return result
