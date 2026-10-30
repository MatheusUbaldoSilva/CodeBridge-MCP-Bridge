"""RAG-DEL: read-only filesystem fingerprint of a CLOSED isolated Qdrant store.

Callers must close the Qdrant client before hashing; the manifest never
authorizes activation and cannot substitute semantic vector verification.
"""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import json

class QdrantFreezeError(RuntimeError):
    pass

def fingerprint_closed_qdrant_store(root: str | Path, *, max_files: int = 100000,
                                    max_bytes: int = 100 * 1024**3) -> dict:
    folder = Path(root)
    if not folder.is_dir() or folder.is_symlink() or (
        hasattr(folder, "is_junction") and folder.is_junction()
    ):
        raise QdrantFreezeError("Qdrant directory unavailable or redirected")
    root_resolved=folder.resolve(strict=True)
    files=[]
    aggregate=0
    for candidate in sorted(folder.rglob("*")):
        if candidate.is_symlink() or (
            hasattr(candidate,"is_junction") and candidate.is_junction()
        ):
            raise QdrantFreezeError("redirected Qdrant entry")
        resolved=candidate.resolve(strict=True)
        if not resolved.is_relative_to(root_resolved):
            raise QdrantFreezeError("Qdrant entry escaped root")
        if candidate.is_dir():
            continue
        if not candidate.is_file():
            raise QdrantFreezeError("unexpected Qdrant entry type")
        if len(files)>=max_files:
            raise QdrantFreezeError("Qdrant file count limit exceeded")
        size=candidate.stat().st_size
        aggregate+=size
        if aggregate>max_bytes:
            raise QdrantFreezeError("Qdrant total size limit exceeded")
        digest=sha256()
        with candidate.open("rb") as handle:
            while chunk:=handle.read(1024*1024):
                digest.update(chunk)
        if candidate.stat().st_size!=size:
            raise QdrantFreezeError("Qdrant file changed during freeze")
        files.append({
            "path":candidate.relative_to(folder).as_posix(),
            "bytes":size,"sha256":digest.hexdigest(),
        })
    if not files:
        raise QdrantFreezeError("Qdrant folder is empty")
    encoded=json.dumps(files,sort_keys=True,separators=(",",":")).encode("utf-8")
    return {"state":"CLOSED_QDRANT_FILES_FINGERPRINTED",
            "files":files,"total_files":len(files),
            "total_bytes":aggregate,
            "inventory_sha256":sha256(encoded).hexdigest(),
            "activation_authorized":False,
            "source_modified":False}


def verify_closed_qdrant_inventory(root: str | Path, expected: dict) -> dict:
    """Verify that a CLOSED store still matches a previously frozen inventory."""
    if (not isinstance(expected,dict)
            or expected.get("state")!="CLOSED_QDRANT_FILES_FINGERPRINTED"
            or expected.get("activation_authorized") is not False
            or not isinstance(expected.get("files"),list)):
        raise QdrantFreezeError("invalid baseline Qdrant inventory")
    current=fingerprint_closed_qdrant_store(root)
    if (current["inventory_sha256"]!=expected.get("inventory_sha256")
            or current["files"]!=expected["files"]
            or current["total_bytes"]!=expected.get("total_bytes")):
        raise QdrantFreezeError("isolated Qdrant files drifted after close")
    return {"state":"CLOSED_QDRANT_FINGERPRINT_REVALIDATED",
            "inventory_sha256":current["inventory_sha256"],
            "activation_authorized":False}
