"""Offline-only full Python runtime snapshot, no automatic restore or update."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def create_offline_runtime_snapshot(
    install_root: Path, archive_path: Path, *,
    allow_offline_snapshot: bool = False,
) -> dict:
    install=Path(install_root).resolve()
    runtime=install/"runtime"/"python"
    target=Path(archive_path).absolute()
    default={"archive_created":False,"runtime_modified":False,
             "public_index_modified":False,"restore_performed":False}
    if (not runtime.is_dir() or target.exists() or target.is_symlink()
            or target.resolve(strict=False).is_relative_to(install)):
        return {**default,"state":"SNAPSHOT_PATH_INVALID"}
    if not target.parent.is_dir():
        return {**default,"state":"SNAPSHOT_PARENT_MISSING"}
    paths=[]
    total=0
    try:
        for path in runtime.rglob("*"):
            if path.is_symlink():
                return {**default,"state":"SYMLINK_IN_RUNTIME"}
            if path.is_file():
                paths.append(path)
                total+=path.stat().st_size
    except OSError:
        return {**default,"state":"RUNTIME_SCAN_FAILED"}
    if not paths:
        return {**default,"state":"RUNTIME_EMPTY"}
    if not allow_offline_snapshot:
        return {**default,"state":"OFFLINE_SNAPSHOT_DRY_RUN",
                "file_count":len(paths),"runtime_bytes":total}
    # The caller must prove offline state through its independent maintenance
    # channel. This helper never stops services, changes packages or restores.
    entries={}
    owned=False
    try:
        # Exclusive file creation lets failure cleanup delete only our own ZIP.
        with target.open("xb") as stream:
            owned=True
            with ZipFile(stream,"w",compression=ZIP_DEFLATED,allowZip64=True) as output:
                for path in sorted(paths):
                    relative=path.relative_to(install).as_posix()
                    # Stream binary packages, then rehash the source to detect drift.
                    digest=hashlib.sha256()
                    written=0
                    with path.open("rb") as source, output.open(relative,"w") as dest:
                        for chunk in iter(lambda: source.read(1024 * 1024), b""):
                            digest.update(chunk)
                            written+=len(chunk)
                            dest.write(chunk)
                    check=hashlib.sha256()
                    with path.open("rb") as check_source:
                        for chunk in iter(lambda: check_source.read(1024 * 1024), b""):
                            check.update(chunk)
                    if check.digest()!=digest.digest() or written!=path.stat().st_size:
                        raise RuntimeError("RUNTIME_CHANGED_DURING_SNAPSHOT")
                    entries[relative]={"sha256":digest.hexdigest(),"bytes":written}
                output.writestr("RUNTIME_SHA256.json",json.dumps(entries,sort_keys=True))
    except Exception:
        if owned:
            target.unlink(missing_ok=True)
        return {**default,"state":"SNAPSHOT_FAILED"}
    return {**default,"archive_created":True,"state":"OFFLINE_SNAPSHOT_CREATED",
            "file_count":len(entries),"runtime_bytes":total}

def verify_offline_runtime_snapshot(archive_path: Path) -> dict:
    path=Path(archive_path)
    if not path.is_file():
        return {"state":"SNAPSHOT_UNAVAILABLE","verified":False}
    try:
        with ZipFile(path) as archive:
            names=archive.namelist()
            if len(names)!=len(set(names)) or "RUNTIME_SHA256.json" not in names:
                raise ValueError("missing or duplicate entries")
            metadata=json.loads(archive.read("RUNTIME_SHA256.json"))
            if not isinstance(metadata,dict) or not metadata:
                raise ValueError("empty metadata")
            if set(names)!=(set(metadata)|{"RUNTIME_SHA256.json"}):
                raise ValueError("entries mismatch")
            for key, expected in metadata.items():
                if (not key.startswith("runtime/python/") or ".." in Path(key).parts
                        or key.startswith("/") or "\\" in key):
                    raise ValueError("path escape")
                digest=hashlib.sha256()
                size=0
                with archive.open(key, "r") as source:
                    for chunk in iter(lambda: source.read(1024 * 1024), b""):
                        digest.update(chunk)
                        size+=len(chunk)
                if digest.hexdigest()!=expected["sha256"] or size!=expected["bytes"]:
                    raise ValueError("invalid hash")
            return {"state":"SNAPSHOT_CONTENT_VERIFIED","verified":True,
                    "file_count":len(metadata),"restore_performed":False}
    except Exception:
        return {"state":"SNAPSHOT_INTEGRITY_BLOCKED","verified":False}
