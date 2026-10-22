"""Bounded NSIS file rollback executor, disposable laboratory only.

Consumes a verified rollback ZIP and checks every target before writing.
Does not touch HKCU, installed CodeBridge or run the NSIS installer.
"""
from __future__ import annotations
import hashlib
import json
import os
from tempfile import NamedTemporaryFile
from pathlib import Path, PurePosixPath
from zipfile import ZipFile
from installer.rag_p9b_installer_rollback_scope import verify_installer_rollback_snapshot

def _replace_old_file_atomically(target, data):
    """Use same-directory fsync and replace; no half-written destination."""
    target=Path(target)
    if target.is_symlink() or not target.is_file() or target.parent.is_symlink():
        raise ValueError("LAB_TARGET_NOT_REGULAR_FILE")
    temp=None
    try:
        with NamedTemporaryFile(mode="wb",dir=target.parent,
                                prefix=".p9b-restore-",suffix=".tmp",delete=False) as stream:
            temp=Path(stream.name)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        if target.is_symlink() or not target.is_file():
            raise ValueError("LAB_DESTINATION_CHANGED")
        os.replace(temp,target)
        temp=None
    finally:
        if temp is not None:
            temp.unlink(missing_ok=True)


def restore_files_in_lab(*, snapshot, installed, lab_root, expected_sha256,
                         new_file_marker=b"P9B_LAB_INSTALLER_CREATED_V1",
                         snapshot_probe=verify_installer_rollback_snapshot):
    result={"state":"FILE_RESTORE_REFUSED","verified":False,
            "production_modified":False,"nsis_executed":False}
    root=Path(lab_root).absolute()
    actual=Path(installed).resolve()
    if (not root.is_dir() or root.is_symlink() or
            root==actual or root.is_relative_to(actual)):
        return {**result,"reason":"LAB_SCOPE_INVALID"}
    if hashlib.sha256(Path(snapshot).read_bytes()).hexdigest()!=str(expected_sha256).lower():
        return {**result,"reason":"SNAPSHOT_DIGEST_INVALID"}
    if snapshot_probe(snapshot,installed).get("verified") is not True:
        return {**result,"reason":"SNAPSHOT_SCOPE_INVALID"}
    try:
        with ZipFile(snapshot) as archive:
            manifest=json.loads(archive.read("manifest.json"))
            originals=manifest["existing"]
            fresh=[n for n in manifest["targets"] if n not in originals]
            # Scan the ENTIRE scope before making any changes.
            for rel in manifest["targets"]:
                relative=PurePosixPath(rel)
                if (relative.is_absolute() or not rel or ".." in relative.parts
                        or chr(92) in rel or ":" in rel):
                    return {**result,"reason":"TARGET_TRAVERSAL"}
                target=root.joinpath(*relative.parts)
                if target.is_symlink() or any(parent.is_symlink() for parent in target.parents if root in parent.parents):
                    return {**result,"reason":"TARGET_SYMLINK"}
                if rel in fresh and (not target.is_file() or target.read_bytes()!=new_file_marker):
                    return {**result,"reason":"UNRECOGNIZED_NEW_TARGET"}
                if rel in originals and not target.is_file():
                    return {**result,"reason":"ORIGINAL_TARGET_MISSING"}
            for rel,meta in originals.items():
                data=archive.read("old/"+rel)
                if hashlib.sha256(data).hexdigest()!=meta["sha256"]:
                    return {**result,"reason":"BACKUP_FILE_MISMATCH"}
            for rel in originals:
                _replace_old_file_atomically(root.joinpath(*PurePosixPath(rel).parts),
                                             archive.read("old/"+rel))
            for rel in fresh:
                root.joinpath(*PurePosixPath(rel).parts).unlink()
            verified=all(
                hashlib.sha256(root.joinpath(*PurePosixPath(rel).parts).read_bytes()).hexdigest()==meta["sha256"]
                for rel,meta in originals.items())
            verified=verified and all(not root.joinpath(*PurePosixPath(rel).parts).exists() for rel in fresh)
            return {**result,"state":"FILE_RESTORE_LAB_VERIFIED" if verified else "FILE_RESTORE_LAB_POSTVERIFY_FAILED",
                    "verified":verified,"old_files":len(originals),"new_files_removed":len(fresh)}
    except (OSError,KeyError,ValueError,TypeError):
        return {**result,"reason":"RESTORE_EXCEPTION"}
