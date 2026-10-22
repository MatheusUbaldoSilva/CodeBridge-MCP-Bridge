"""Read-only classification of post-install file rollback against approved NSIS.

Never restores or deletes installed files. A rollback is *not* approved if any
target changed to content other than the old backup or vetted installer bytes.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
import subprocess
from tempfile import TemporaryDirectory
from zipfile import ZipFile

from installer.rag_p9b_installer_rollback_scope import (
    payload_file_list, verify_installer_rollback_snapshot,
)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def classify_rollback_targets(installed: Path, old_manifest: dict,
                              installer_hashes: dict[str, str]) -> dict:
    result = {
        "state": "ROLLBACK_CLASSIFICATION_BLOCKED",
        "restorable": False, "changes_applied": False,
        "rollback_execution_authorized": False,
        "real_restore_rehearsed": False,
        "restore_candidates": 0, "remove_candidates": 0,
        "unchanged_targets": 0, "unrecognized_targets": [],
    }
    root = Path(installed).resolve()
    target_names = old_manifest.get("targets")
    existing = old_manifest.get("existing")
    if (not isinstance(target_names, list)
            or not isinstance(existing, dict)
            or len(target_names) != len(set(target_names))
            or set(installer_hashes) != set(target_names)
            or not set(existing).issubset(target_names)):
        return result
    unknown = []
    restore = remove = unchanged = 0
    for relative in target_names:
        if (not isinstance(relative, str) or not relative
                or PurePosixPath(relative).is_absolute()
                or ".." in PurePosixPath(relative).parts
                or "\\" in relative or ":" in relative):
            return result
        destination = root.joinpath(*PurePosixPath(relative).parts)
        if (destination.is_symlink()
                or any(parent.is_symlink() for parent in destination.parents
                       if parent == root or root in parent.parents)):
            unknown.append(relative)
            continue
        before = existing.get(relative, {}).get("sha256")
        after = installer_hashes.get(relative)
        if (not isinstance(after, str) or len(after) != 64
                or before is not None and
                (not isinstance(before, str) or len(before) != 64)):
            return result
        if not destination.exists():
            if before is not None:
                unknown.append(relative)
            else:
                unchanged += 1
            continue
        if not destination.is_file():
            unknown.append(relative)
            continue
        current = _sha(destination.read_bytes())
        if before is not None and current == before:
            unchanged += 1
        elif current == after:
            if before is not None:
                restore += 1
            else:
                remove += 1
        else:
            unknown.append(relative)
    result.update(restore_candidates=restore, remove_candidates=remove,
                  unchanged_targets=unchanged, unrecognized_targets=unknown[:20],
                  unrecognized_count=len(unknown))
    if unknown:
        result["state"] = "ROLLBACK_UNRECOGNIZED_INSTALLED_CONTENT"
    else:
        result["state"] = ("ROLLBACK_BASELINE_ALREADY_MATCHES" if restore+remove == 0
                           else "ROLLBACK_CANDIDATES_OBSERVED_ONLY")
        result["restorable"] = True
    return result


def inspect_nsis_rollback_candidates(snapshot: Path, installer: Path,
                                     installed: Path, seven_zip: Path) -> dict:
    blocked = {
        "state": "ROLLBACK_PREVIEW_UNAVAILABLE", "restorable": False,
        "installed_modified": False, "restore_performed": False,
        "rollback_execution_authorized": False,
        "real_restore_rehearsed": False,
        "installer_executed": False,
    }
    verified = verify_installer_rollback_snapshot(snapshot, installed)
    if not verified["verified"]:
        return {**blocked, "reason": "PREUPDATE_SNAPSHOT_UNVERIFIED"}
    executable = Path(installer)
    if (not executable.is_file() or executable.is_symlink()
            or _sha(executable.read_bytes()) != verified["installer_sha256"]):
        return {**blocked, "reason": "INSTALLER_IDENTITY_CHANGED"}
    try:
        targets = payload_file_list(executable, Path(seven_zip))
        with ZipFile(snapshot) as before_zip:
            baseline = json.loads(before_zip.read("manifest.json"))
        if set(targets) != set(baseline["targets"]):
            return {**blocked, "reason": "SNAPSHOT_AND_INSTALLER_SCOPE_DIFFER"}
        with TemporaryDirectory(prefix="codebridge_p9b_rollback_inspection_") as scratch:
            unpack = subprocess.run(
                [str(seven_zip), "x", "-y", "-o" + str(scratch),
                 str(executable)],
                capture_output=True, text=True, timeout=100, check=False,
            )
            if unpack.returncode != 0:
                return {**blocked, "reason": "UNABLE_TO_READ_INSTALLER_PAYLOAD"}
            hashes = {}
            for name in targets:
                file = Path(scratch).joinpath(*PurePosixPath(name).parts)
                if not file.is_file() or file.is_symlink():
                    return {**blocked, "reason": "UNTRUSTED_INSTALLER_MEMBER",
                            "file": name}
                hashes[name] = _sha(file.read_bytes())
            classified = classify_rollback_targets(installed, baseline, hashes)
        return {**blocked, **classified}
    except (OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired):
        return {**blocked, "reason": "ROLLBACK_INSPECTION_FAILED"}



def main(argv=None) -> int:
    """Read-only command line for supervised post-update recovery triage."""
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", required=True, type=Path)
    parser.add_argument("--installer", required=True, type=Path)
    parser.add_argument("--install-root", required=True, type=Path)
    parser.add_argument("--seven-zip", required=True, type=Path)
    args = parser.parse_args(argv)
    result = inspect_nsis_rollback_candidates(
        args.snapshot, args.installer, args.install_root, args.seven_zip,
    )
    print(json.dumps(result, sort_keys=True))
    return 0 if result["restorable"] and not result["changes_applied"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
