"""Complete bounded catalog of synthetic SQLite, manifest and Qdrant files.

A stable catalog is NOT a closed-handles, mmap, or production backup proof.
"""
from __future__ import annotations
import hashlib
import os
from pathlib import Path
from rag.runtime.offline_fixture_snapshot import _root, _redirected, _qdrant_sqlite_sidecars

def catalog_synthetic_stores(root_path, *, max_files=10000, max_bytes=67108864):
    report={"state":"BLOCKED","issues":[],"files":[],"files_checked":0,
            "bytes_checked":0,"copy_authorized":False,
            "all_handles_closed":False,"production_quiescence_proven":False}
    try:
        if type(max_files) is not int or max_files < 3 or type(max_bytes) is not int or max_bytes < 1:
            raise ValueError("invalid catalog bounds")
        root=_root(root_path)
        if _qdrant_sqlite_sidecars(root/"qdrant"):
            report["issues"].append("QDRANT_SQLITE_SIDECAR_PRESENT")
            return report
        for suffix in ("-wal","-shm","-journal"):
            path=root/("rag_index.sqlite3"+suffix)
            if path.exists() or _redirected(path):
                report["issues"].append("SQLITE_SIDECAR_PRESENT")
                return report
        def scan_once():
            output={}
            total=0
            base=[root/"rag_index.sqlite3", root/"rag-index-manifest.json"]
            vector=root/"qdrant"
            if not vector.is_dir() or _redirected(vector):
                raise ValueError("missing or redirected Qdrant tree")
            pending=[vector]
            while pending:
                folder=pending.pop()
                if _redirected(folder):
                    raise ValueError("redirected directory")
                if folder != vector and not any(folder.iterdir()):
                    raise ValueError("empty vector directory")
                with os.scandir(folder) as iterator:
                    for entry in iterator:
                        item=Path(entry.path)
                        if _redirected(item) or entry.is_symlink():
                            raise ValueError("redirected entry")
                        if entry.is_dir(follow_symlinks=False):
                            pending.append(item)
                        elif entry.is_file(follow_symlinks=False):
                            base.append(item)
                        else:
                            raise ValueError("unsupported file kind")
                        if len(base)+len(pending) > max_files+128:
                            raise ValueError("directory listing limit")
            if len(base) < 3 or len(base)>max_files:
                raise ValueError("missing files or limit exceeded")
            for file in base:
                if _redirected(file) or not file.is_file():
                    raise ValueError("missing or redirected file")
                stat=file.stat()
                if stat.st_nlink>1:
                    raise ValueError("hardlink not allowed")
                total+=stat.st_size
                if total>max_bytes:
                    raise ValueError("catalog byte limit")
                hash=hashlib.sha256()
                with file.open("rb") as stream:
                    for part in iter(lambda:stream.read(65536),b""):
                        hash.update(part)
                after=file.stat()
                if (stat.st_size,stat.st_mtime_ns)!=(after.st_size,after.st_mtime_ns):
                    raise ValueError("file mutated during read")
                key=file.relative_to(root).as_posix()
                if key in output:
                    raise ValueError("duplicate file")
                output[key]=(stat.st_size,hash.hexdigest())
            return output,total
        first,nbytes=scan_once()
        second,nbytes2=scan_once()
        if first!=second or nbytes!=nbytes2:
            report["issues"].append("FILE_TREE_CHANGED_DURING_CATALOG")
            return report
        for suffix in ("-wal","-shm","-journal"):
            sidecar=root/("rag_index.sqlite3"+suffix)
            if sidecar.exists() or _redirected(sidecar):
                report["issues"].append("SQLITE_SIDECAR_PRESENT")
                return report
        vector=root/"qdrant"
        if not vector.is_dir() or _redirected(vector):
            report["issues"].append("VECTOR_TREE_REDIRECTED_OR_MISSING")
            return report
        if _qdrant_sqlite_sidecars(root/"qdrant"):
            report["issues"].append("QDRANT_SQLITE_SIDECAR_PRESENT")
            return report
        report["files"]=sorted(first)
        report["files_checked"]=len(first)
        report["bytes_checked"]=nbytes
        report["state"]="LAB_FILE_TREE_CATALOG_UNPROVEN"
    except (ValueError,TypeError,OSError,RuntimeError) as exc:
        report["issues"].append(type(exc).__name__)
    return report
