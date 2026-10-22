"""Durable identity contract for independent P9-B recovery.

This module only creates/verifies a manifest, never starts NSIS, deletes
files, changes HKCU or stops processes. Bind every recovery input by SHA256.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path

NAMES=("installer","file_snapshot","shell_snapshot","crash_preimage")
PURPOSE="P9B_RELEASE_TRANSACTION_IDENTITY_V1"

def digest(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b""):
            h.update(chunk)
    return h.hexdigest()

def write_identity(output,*,artifacts,installed,source_commit):
    rejected={"state":"TRANSACTION_IDENTITY_REFUSED","written":False,
              "installed_modified":False,"installer_executed":False}
    destination=Path(output)
    if (destination.exists() or destination.is_symlink()
            or not destination.parent.is_dir() or destination.parent.is_symlink()):
        return {**rejected,"reason":"IDENTITY_OUTPUT_NOT_NEW"}
    if set(artifacts)!=set(NAMES) or not isinstance(source_commit,str) or len(source_commit)!=40:
        return {**rejected,"reason":"ARTIFACT_SET_INVALID"}
    try:
        values={}
        for name in NAMES:
            path=Path(artifacts[name]).resolve()
            if not path.is_file() or path.is_symlink():
                return {**rejected,"reason":"ARTIFACT_NOT_REGULAR","artifact":name}
            values[name]={"path":str(path),"sha256":digest(path)}
        manifest={"schema":1,"purpose":PURPOSE,"source_commit":source_commit,
                  "installed":str(Path(installed).resolve()),"artifacts":values}
        payload=(json.dumps(manifest,sort_keys=True,separators=(",",":"))+chr(10)).encode("utf-8")
        with destination.open("xb") as f:
            f.write(payload);f.flush();os.fsync(f.fileno())
        return {**rejected,"state":"TRANSACTION_IDENTITY_PERSISTED","written":True,
                "manifest_sha256":hashlib.sha256(payload).hexdigest()}
    except (OSError,ValueError,TypeError):
        return {**rejected,"reason":"IDENTITY_PERSISTENCE_FAILED"}

def verify_identity(path,expected_sha):
    rejected={"state":"TRANSACTION_IDENTITY_UNVERIFIED","verified":False,
              "inspection_only":True}
    src=Path(path)
    expected=str(expected_sha).lower()
    if (len(expected)!=64 or any(c not in "0123456789abcdef" for c in expected)
            or not src.is_file() or src.is_symlink()):
        return {**rejected,"reason":"MANIFEST_IDENTITY_INVALID"}
    try:
        if src.stat().st_size>8192 or digest(src)!=expected:
            return {**rejected,"reason":"MANIFEST_HASH_MISMATCH"}
        body=json.loads(src.read_text(encoding="utf-8"))
        if (body.get("schema")!=1 or body.get("purpose")!=PURPOSE
                or set(body.get("artifacts",{}))!=set(NAMES)
                or len(body.get("source_commit",""))!=40):
            return {**rejected,"reason":"MANIFEST_SCHEMA_INVALID"}
        for name in NAMES:
            spec=body["artifacts"][name]
            if not isinstance(spec,dict) or set(spec)!={"path","sha256"}:
                return {**rejected,"reason":"ARTIFACT_ENTRY_INVALID","artifact":name}
            p=Path(spec["path"])
            if (not p.is_absolute() or not p.is_file() or p.is_symlink()
                    or len(spec["sha256"])!=64 or digest(p)!=spec["sha256"]):
                return {**rejected,"reason":"BOUND_ARTIFACT_CHANGED","artifact":name}
        return {**rejected,"state":"TRANSACTION_IDENTITY_VERIFIED","verified":True,
                "artifact_count":len(NAMES),"source_commit":body["source_commit"]}
    except (OSError,ValueError,TypeError,KeyError):
        return {**rejected,"reason":"IDENTITY_VERIFICATION_ERROR"}
