"""Read-only manifest-scoped inventory of NSIS-created files to remove on rollback."""
from __future__ import annotations

import json
from pathlib import Path, PurePosixPath
from zipfile import ZipFile, BadZipFile
from installer.rag_p9b_installer_rollback_scope import verify_installer_rollback_snapshot


def inspect_new_targets(snapshot, installed):
    base=dict(state="NEW_TARGETS_UNVERIFIED",read_only=True,
              installed_modified=False,delete_authorized=False)
    proof=verify_installer_rollback_snapshot(snapshot,installed)
    if not proof.get("verified"):
        return {**base,"reason":"ROLLBACK_SNAPSHOT_INVALID"}
    root=Path(installed).resolve()
    try:
        with ZipFile(snapshot) as z:
            m=json.loads(z.read("manifest.json"))
        targets=set(m["targets"])
        existing=set(m["existing"])
        if len(targets)!=len(m["targets"]) or not existing.issubset(targets):
            return {**base,"reason":"MANIFEST_SCOPE_INVALID"}
        fresh=sorted(targets-existing)
        records=[]
        for name in fresh:
            path=PurePosixPath(name)
            if path.is_absolute() or ".." in path.parts:
                return {**base,"reason":"UNSAFE_TARGET_NAME"}
            target=root.joinpath(*path.parts)
            if target.is_symlink() or (target.exists() and not target.is_file()):
                return {**base,"reason":"NEW_TARGET_NOT_REGULAR","name":name}
            records.append({"name":name,"exists":target.is_file(),
                            "rollback_action":"REVIEW_NSIS_CREATED_FILE"})
        return {**base,"state":"NEW_TARGETS_OBSERVED_ONLY",
                "count":len(records),"targets":records,
                "requires_postupdate_checksum":True,
                "requires_stopped_processes":True}
    except (OSError,TypeError,KeyError,ValueError,BadZipFile):
        return {**base,"reason":"NEW_TARGET_INVENTORY_FAILED"}
