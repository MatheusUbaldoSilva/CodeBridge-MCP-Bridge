"""Read-only manifest-scoped inventory of NSIS-created files to remove on rollback."""
from __future__ import annotations

import json
import hashlib
from pathlib import Path, PurePosixPath
from zipfile import ZipFile, BadZipFile
from installer.rag_p9b_installer_rollback_scope import verify_installer_rollback_snapshot


def inspect_new_targets(snapshot, installed, *, expected_new_hashes=None):
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
        if expected_new_hashes is not None:
            if (not isinstance(expected_new_hashes,dict)
                    or set(expected_new_hashes)!=set(fresh)
                    or any(not isinstance(digest,str) or len(digest)!=64
                           or any(c not in "0123456789abcdef" for c in digest.lower())
                           for digest in expected_new_hashes.values())):
                return {**base,"reason":"NEW_TARGET_DIGEST_SCOPE_INVALID"}
        records=[]
        for name in fresh:
            path=PurePosixPath(name)
            if path.is_absolute() or ".." in path.parts:
                return {**base,"reason":"UNSAFE_TARGET_NAME"}
            target=root.joinpath(*path.parts)
            if (any(parent.is_symlink() for parent in (target,*target.parents))
                    or (target.exists() and not target.is_file())):
                return {**base,"reason":"NEW_TARGET_NOT_REGULAR","name":name}
            exists=target.is_file()
            if exists and expected_new_hashes is not None:
                if hashlib.sha256(target.read_bytes()).hexdigest()!=expected_new_hashes[name].lower():
                    return {**base,"reason":"UNRECOGNIZED_NEW_TARGET_CONTENT","name":name}
            records.append({"name":name,"exists":exists,
                            "rollback_action":"REVIEW_NSIS_CREATED_FILE"})
        return {**base,"state":"NEW_TARGETS_CONTENT_VERIFIED" if expected_new_hashes is not None else "NEW_TARGETS_OBSERVED_ONLY",
                "count":len(records),"targets":records,
                "ownership_evidence_verified":expected_new_hashes is not None,
                "requires_postupdate_checksum":expected_new_hashes is None,
                "requires_stopped_processes":True}
    except (OSError,TypeError,KeyError,ValueError,BadZipFile):
        return {**base,"reason":"NEW_TARGET_INVENTORY_FAILED"}
