"""Guarded file-only rollback. No CLI and no default production approval.

The caller must be a separately audited external supervisor. Every action is
journaled, every original is restored from a previously verified ZIP, and
new targets are deleted only when their bytes match the expected candidate.
This module does not restore HKCU/shortcuts or run NSIS.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
from zipfile import ZipFile

from installer.rag_p9b_production_file_recovery_gate import assess_file_recovery
from installer.rag_p9b_poststop_verification import check_poststop
from installer.rag_p9b_file_restore_executor_lab import _replace_old_file_atomically


def restore_files_detached(*, snapshot, installed, expected_sha256,
                           expected_new_hashes, preimage, preimage_sha256,
                           journal_path, journal, external=False, execute=False,
                           gate=assess_file_recovery,
                           stopped_probe=check_poststop,
                           replace_file=_replace_old_file_atomically):
    refused = {"state": "DETACHED_FILE_RESTORE_REFUSED", "verified": False,
               "installer_executed": False, "delete_authorized": False}
    if external is not True or execute is not True or not callable(journal):
        return {**refused, "reason": "EXTERNAL_EXECUTION_AND_JOURNAL_REQUIRED"}
    root = Path(installed).resolve()
    archive_path = Path(snapshot).absolute()
    try:
        evidence = gate(
            installed=root, snapshot=archive_path,
            snapshot_sha256=expected_sha256, preimage=preimage,
            preimage_sha256=preimage_sha256, journal_path=journal_path,
            expected_new_hashes=expected_new_hashes, independent=True)
        if evidence.get("state") != "PRODUCTION_FILE_ROLLBACK_GATES_OBSERVED_ONLY":
            return {**refused, "reason": "INDEPENDENT_ROLLBACK_EVIDENCE_UNVERIFIED"}
        with ZipFile(archive_path) as z:
            manifest = json.loads(z.read("manifest.json"))
            previous = manifest["existing"]
            targets = manifest["targets"]
            fresh = sorted(set(targets)-set(previous))
            if (not isinstance(expected_new_hashes, dict)
                    or set(expected_new_hashes) != set(fresh)
                    or len(set(targets)) != len(targets)
                    or Path(manifest["installed_root"]).resolve() != root):
                return {**refused, "reason": "RESTORE_MANIFEST_NOT_BOUND"}
            originals={}
            for name, meta in previous.items():
                original=z.read("old/"+name)
                if hashlib.sha256(original).hexdigest()!=meta["sha256"]:
                    return {**refused, "reason": "BACKUP_BYTES_UNVERIFIED"}
                originals[name]=original
            # Check the full destination set before first journal arm/write.
            destinations={}
            for name in targets:
                rel=PurePosixPath(name)
                if (rel.is_absolute() or not rel.parts
                        or any(x in ("", ".", "..") for x in rel.parts)
                        or "\\" in name or ":" in name):
                    return {**refused, "reason": "RESTORE_TARGET_UNTRUSTED"}
                dest=root.joinpath(*rel.parts)
                if any(p.is_symlink() for p in (dest, *dest.parents)):
                    return {**refused, "reason": "RESTORE_PATH_REDIRECTED"}
                if name in previous and not dest.is_file():
                    return {**refused, "reason": "EXISTING_RESTORE_DESTINATION_MISSING"}
                if name in fresh and dest.exists():
                    if (not dest.is_file()
                            or hashlib.sha256(dest.read_bytes()).hexdigest()
                            != expected_new_hashes[name].lower()):
                        return {**refused, "reason": "NEW_TARGET_NOT_OWNED"}
                destinations[name]=dest
        # A second independent stopped-process sample narrows TOCTOU.
        stopped=stopped_probe(root)
        if (stopped.get("state") != "POSTSTOP_OBSERVED_ONLY"
                or stopped.get("observed_stopped") is not True):
            return {**refused, "reason": "POSTSTOP_RECHECK_FAILED"}
        journal("SHELL_PRODUCTION_FILE_RESTORE_ARMED",
                {"files":len(previous),"new_targets":len(fresh)})
        restored=0
        removed=0
        for name, original in originals.items():
            dest=destinations[name]
            if (dest.is_symlink() or not dest.is_file()
                    or any(p.is_symlink() for p in dest.parents)):
                raise ValueError("RESTORE_DESTINATION_CHANGED")
            journal("SHELL_PRODUCTION_FILE_BEFORE_REPLACE", {})
            replace_file(dest, original)
            restored+=1
        for name in fresh:
            dest=destinations[name]
            if dest.exists():
                if (dest.is_symlink() or not dest.is_file()
                        or any(p.is_symlink() for p in dest.parents)
                        or hashlib.sha256(dest.read_bytes()).hexdigest()
                        != expected_new_hashes[name].lower()):
                    raise ValueError("NEW_TARGET_CHANGED_BEFORE_UNLINK")
                journal("SHELL_PRODUCTION_FILE_BEFORE_UNLINK", {})
                dest.unlink()
                removed+=1
        checked=all(hashlib.sha256(destinations[name].read_bytes()).hexdigest()
                    ==hashlib.sha256(original).hexdigest()
                    for name,original in originals.items())
        checked=checked and all(not destinations[name].exists() for name in fresh)
        if not checked:
            journal("SHELL_PRODUCTION_FILE_POSTVERIFY_FAILED", {})
            return {**refused,"state":"DETACHED_FILE_RESTORE_REVIEW_REQUIRED",
                    "reason":"POSTVERIFY_FAILED"}
        journal("SHELL_PRODUCTION_FILE_RESTORED",{"postverified":True})
        return {**refused,"state":"DETACHED_FILES_RESTORED_SHELL_PENDING",
                "verified":True,"files_restored":restored,
                "new_files_removed":removed,"shell_restore_required":True}
    except Exception as exc:
        try:
            journal("SHELL_PRODUCTION_FILE_RESTORE_FAILED",
                    {"type":type(exc).__name__})
        except Exception:
            pass
        return {**refused,"state":"DETACHED_FILE_RESTORE_REVIEW_REQUIRED",
                "reason":"RESTORE_EXCEPTION",
                "exception_type":type(exc).__name__}
