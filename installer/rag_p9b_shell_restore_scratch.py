"""Dry-run CodeBridge shell backup restore into a scratch directory only."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from zipfile import ZipFile, BadZipFile
from installer.rag_p9b_shell_snapshot import verify_shell_snapshot


def rehearse_shell_restore_scratch(snapshot, scratch):
    result={"state":"SHELL_SCRATCH_RESTORE_REFUSED",
            "rehearsed":False,"registry_modified":False,
            "real_shortcuts_modified":False}
    destination=Path(scratch).absolute()
    if destination.exists() or destination.is_symlink() or not destination.parent.is_dir():
        return {**result,"reason":"SCRATCH_PATH_UNSAFE"}
    source=Path(snapshot)
    proof=verify_shell_snapshot(source)
    if not proof["verified"]:
        return {**result,"reason":"SHELL_BACKUP_UNVERIFIED"}
    try:
        with ZipFile(source) as archive:
            manifest=json.loads(archive.read("manifest.json"))
            links=manifest["shortcuts"]
            destination.mkdir()
            created=0
            for item in links:
                if not item["exists"]:
                    continue
                slot=int(item["slot"])
                if slot not in range(5):
                    return {**result,"reason":"UNEXPECTED_SLOT"}
                data=archive.read(f"links/{slot}.bin")
                if hashlib.sha256(data).hexdigest()!=item["sha256"]:
                    return {**result,"reason":"CONTENT_CHANGED"}
                file=destination/f"shortcut_{slot}.bin"
                file.write_bytes(data)
                if hashlib.sha256(file.read_bytes()).hexdigest()!=item["sha256"]:
                    return {**result,"reason":"RESTORED_CONTENT_MISMATCH"}
                created+=1
            (destination/"registry_review.json").write_text(
                json.dumps(manifest["registry"],sort_keys=True),encoding="utf-8")
            return {**result,"state":"SHELL_SCRATCH_RESTORE_REHEARSED",
                    "rehearsed":True,"shortcut_files":created,
                    "registry_keys_reviewed":len(manifest["registry"])}
    except (OSError,ValueError,KeyError,TypeError,BadZipFile):
        return {**result,"reason":"SCRATCH_RESTORE_EXCEPTION"}
