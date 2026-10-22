"""Reconstruct an interrupted shell transaction exclusively in a scratch lab.

No production restore entrypoint exists in this module. A real preimage
may be used as the source, but destination must be a new scratch folder.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from zipfile import ZipFile

from installer.rag_p9b_crash_preimage import verify_crash_preimage


def replay_preimage_scratch(preimage, expected_sha256, scratch):
    refused={"state":"CRASH_REPLAY_REFUSED","replayed":False,
             "registry_modified":False,"real_shortcuts_modified":False}
    destination=Path(scratch).absolute()
    if (destination.exists() or destination.is_symlink()
            or not destination.parent.is_dir()
            or destination.parent.is_symlink()):
        return {**refused,"reason":"SCRATCH_NOT_FRESH"}
    proof=verify_crash_preimage(preimage,expected_sha256)
    if proof.get("verified") is not True:
        return {**refused,"reason":"PREIMAGE_UNVERIFIED"}
    try:
        with ZipFile(preimage) as archive:
            manifest=json.loads(archive.read("manifest.json"))
            # Read everything before creating any destination.
            links=[archive.read(f"links/{i}.bin") if item["exists"] else None
                   for i,item in enumerate(manifest["links"])]
            registry=manifest["registry"]
            destination.mkdir()
            restored=0
            for i,payload in enumerate(links):
                if payload is None:
                    continue
                link=destination/f"shortcut_{i}.bin"
                link.write_bytes(payload)
                if hashlib.sha256(link.read_bytes()).hexdigest()!=manifest["links"][i]["sha256"]:
                    return {**refused,"reason":"RESTORED_HASH_MISMATCH"}
                restored+=1
            register=destination/"registry_review.json"
            register.write_text(json.dumps(registry,sort_keys=True),encoding="utf-8")
            if json.loads(register.read_text(encoding="utf-8"))!=registry:
                return {**refused,"reason":"REGISTRY_LAB_MISMATCH"}
            return {**refused,"state":"CRASH_REPLAY_SCRATCH_VERIFIED",
                    "replayed":True,"restored_shortcuts":restored,
                    "reviewed_registry_keys":len(registry)}
    except (OSError,ValueError,KeyError,TypeError):
        return {**refused,"reason":"SCRATCH_REPLAY_FAILED"}
