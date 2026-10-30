"""RAG-DEL snapshot provenance: hashes surviving source files, read-only."""
from __future__ import annotations
from hashlib import sha256
from pathlib import Path, PurePosixPath
import re
from rag.index.manifest import load_index_manifest

class DeletionSnapshotError(RuntimeError):
    pass

def inspect_survivor_snapshot(snapshot_root: str | Path, manifest_path: str | Path,
                              project_id: str, *, max_files: int=100000,
                              max_bytes: int=100*1024**3) -> dict:
    root=Path(snapshot_root)
    if (not root.is_dir() or root.is_symlink()
            or (hasattr(root,"is_junction") and root.is_junction())
            or not isinstance(project_id,str) or not project_id
            or project_id=="codebridge"):
        raise DeletionSnapshotError("invalid isolated project snapshot")
    root_real=root.resolve(strict=True)
    entries=load_index_manifest(manifest_path).entries
    if len(entries)>max_files or max_files<1 or max_bytes<1:
        raise DeletionSnapshotError("snapshot inventory safety limit")
    seen=set()
    aggregate=0
    h=sha256()
    for entry in sorted(entries,key=lambda e:e.path):
        name=entry.path
        pure=PurePosixPath(name)
        if (entry.project_id!=project_id or
                not isinstance(name,str) or not name or
                pure.is_absolute() or len(pure.parts)==0 or
                ".." in pure.parts or "." in pure.parts or "\\" in name or
                ":" in name or name in seen):
            raise DeletionSnapshotError("foreign or redirected source path")
        seen.add(name)
        file=root.joinpath(*pure.parts)
        for ancestor in (file,*file.parents):
            if ancestor==root.parent:
                break
            if ancestor.exists() and (ancestor.is_symlink() or (
                hasattr(ancestor,"is_junction") and ancestor.is_junction()
            )):
                raise DeletionSnapshotError("source symlink/junction forbidden")
        try:
            resolved=file.resolve(strict=True)
        except OSError as exc:
            raise DeletionSnapshotError("missing snapshot source") from exc
        if not resolved.is_relative_to(root_real) or not resolved.is_file():
            raise DeletionSnapshotError("source escaped snapshot")
        size=resolved.stat().st_size
        if size!=entry.size:
            raise DeletionSnapshotError("source size differs from manifest")
        aggregate+=size
        if aggregate>max_bytes:
            raise DeletionSnapshotError("snapshot size limit exceeded")
        digest=sha256()
        with resolved.open("rb") as stream:
            for block in iter(lambda:stream.read(1024*1024),b""):
                digest.update(block)
        if size!=resolved.stat().st_size or digest.hexdigest()!=entry.sha256:
            raise DeletionSnapshotError("source changed since index manifest")
        h.update((name+"\0"+entry.sha256+"\0").encode("utf-8"))
    return {
        "state":"SURVIVOR_SNAPSHOT_READ_ONLY_VERIFIED",
        "project_id":project_id,"files_verified":len(seen),
        "bytes_verified":aggregate,"snapshot_inventory_sha256":h.hexdigest(),
        "sources_modified":False,"activation_authorized":False,
    }
