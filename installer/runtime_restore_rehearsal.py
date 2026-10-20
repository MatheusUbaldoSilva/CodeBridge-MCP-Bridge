"""Rehearse Python runtime snapshot restoration into a disposable directory.

Never targets the installed CodeBridge tree, never writes RAG state.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from zipfile import ZipFile

from installer.runtime_full_snapshot import verify_offline_runtime_snapshot


def rehearse_runtime_restore(
    archive_path: Path, scratch_root: Path, install_root: Path,
    *, execute: bool = False,
) -> dict:
    target = Path(scratch_root).resolve(strict=False)
    installed = Path(install_root).resolve(strict=False)
    baseline = {"rehearsed": False, "installed_modified": False,
                "public_index_modified": False}
    if target == installed or target.is_relative_to(installed) or installed.is_relative_to(target):
        return {**baseline, "state": "RESTORE_TARGET_UNSAFE"}
    if not target.parent.is_dir() or target.exists():
        return {**baseline, "state": "RESTORE_TARGET_UNAVAILABLE"}
    validation = verify_offline_runtime_snapshot(archive_path)
    if not validation["verified"]:
        return {**baseline, "state": "SNAPSHOT_NOT_VERIFIED"}
    # Reject oversized archives before creating any directory.
    try:
        with ZipFile(archive_path) as check:
            members = check.infolist()
            total = sum(entry.file_size for entry in members)
            max_single = max(entry.file_size for entry in members)
        if total > 8 * 1024**3 or max_single > 4 * 1024**3:
            return {**baseline, "state": "RESTORE_SIZE_POLICY_REJECTED"}
    except Exception:
        return {**baseline, "state": "SNAPSHOT_NOT_VERIFIED"}
    if not execute:
        return {**baseline, "state": "RESTORE_REHEARSAL_DRY_RUN",
                "file_count": validation["file_count"]}
    # A distinct disposable directory is created only with explicit execution.
    owned = False
    try:
        target.mkdir()
        owned = True
        with ZipFile(archive_path) as zf:
            entries = json.loads(zf.read("RUNTIME_SHA256.json"))
            for name, expected in entries.items():
                # Revalidate zip paths independent of original verifier.
                parts = name.split("/")
                if (parts[:2] != ["runtime", "python"]
                        or any(part in ("", ".", "..") for part in parts)
                        or "\\" in name or ":" in name):
                    raise ValueError("Unsafe archive member")
                dest = target.joinpath(*parts)
                if not dest.resolve(strict=False).is_relative_to(target):
                    raise ValueError("Destination escape")
                dest.parent.mkdir(parents=True, exist_ok=True)
                digest = hashlib.sha256()
                size = 0
                with zf.open(name) as source, dest.open("xb") as sink:
                    for data in iter(lambda: source.read(1024 * 1024), b""):
                        size += len(data)
                        digest.update(data)
                        sink.write(data)
                if size != expected["bytes"] or digest.hexdigest() != expected["sha256"]:
                    raise ValueError("Restored hash mismatch")
        return {**baseline, "state": "ISOLATED_RUNTIME_RESTORE_REHEARSED",
                "rehearsed": True, "file_count": len(entries),
                "scratch_path": str(target)}
    except Exception:
        # Never delete automatically: preserve the scratch copy as failure evidence.
        return {**baseline, "state": "RESTORE_REHEARSAL_FAILED",
                "scratch_path": str(target) if owned else None}


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(
        description="Isolated CodeBridge Python snapshot restore rehearsal")
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--scratch-root", type=Path, required=True)
    parser.add_argument("--install-root", type=Path, required=True)
    parser.add_argument("--execute-in-scratch", action="store_true")
    args = parser.parse_args()
    result = rehearse_runtime_restore(
        args.archive, args.scratch_root, args.install_root,
        execute=args.execute_in_scratch,
    )
    print(json.dumps(result, sort_keys=True))
    return 0 if result["state"] in (
        "RESTORE_REHEARSAL_DRY_RUN", "ISOLATED_RUNTIME_RESTORE_REHEARSED"
    ) else 2


if __name__ == "__main__":
    raise SystemExit(main())
