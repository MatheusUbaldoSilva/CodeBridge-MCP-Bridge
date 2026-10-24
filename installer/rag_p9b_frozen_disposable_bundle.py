"""Copy and bind a disposable P9-B lab artifact set.

This module NEVER authenticates a publisher, runs NSIS, or authorizes cutover.
It freezes bytes in a private TEMP folder and returns a consistency digest.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path

from installer.rag_p9b_transaction_identity import NAMES, digest

PURPOSE = "P9B_DISPOSABLE_FROZEN_BUNDLE_V1"

def _unique_pairs(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise ValueError("DUPLICATE_MANIFEST_KEY")
        out[key] = value
    return out


def _contained(path, root):
    raw = Path(path)
    if raw.is_symlink() or not raw.exists():
        return False
    resolved = raw.resolve()
    return resolved == root or root in resolved.parents


def freeze_disposable_bundle(destination, *, artifacts, source_commit, transaction_id,
                             installed, appdata, desktop, hkcu_prefix, temp_root=None):
    refused = {"state": "P9B_LAB_BUNDLE_REFUSED", "frozen": False,
               "production_modified": False, "trusted_origin": False}
    try:
        temp = Path(temp_root or tempfile.gettempdir()).resolve(strict=True)
        system_temp = Path(tempfile.gettempdir()).resolve(strict=True)
        if temp != system_temp and system_temp not in temp.parents:
            return {**refused, "reason": "TEMP_ROOT_UNTRUSTED"}
        output = Path(destination).absolute()
        if (output.exists() or output.is_symlink() or not output.parent.is_dir()
                or not _contained(output.parent, temp) or output.parent.is_symlink()):
            return {**refused, "reason": "LAB_OUTPUT_NOT_NEW_OR_NOT_TEMP"}
        if (not isinstance(artifacts, dict) or set(artifacts) != set(NAMES)
                or not isinstance(source_commit, str) or len(source_commit) != 40
                or any(c not in "0123456789abcdef" for c in source_commit)
                or not isinstance(transaction_id, str) or len(transaction_id) != 32
                or any(c not in "0123456789abcdef" for c in transaction_id)):
            return {**refused, "reason": "IDENTITY_INPUT_INVALID"}
        scopes = {}
        for name, scope in (("installed", installed), ("appdata", appdata),
                            ("desktop", desktop)):
            target = Path(scope)
            if not _contained(target, temp) or target.is_symlink():
                return {**refused, "reason": "SCOPE_OUTSIDE_LAB", "scope": name}
            scopes[name] = str(target.resolve())
        if (not isinstance(hkcu_prefix, str)
                or not hkcu_prefix.startswith("Software\\CodeBridge_P9B_Lab\\")
                or len(hkcu_prefix) > 220):
            return {**refused, "reason": "HKCU_SCOPE_INVALID"}
        sources = {}
        for name in NAMES:
            path = Path(artifacts[name])
            if (not path.is_file() or path.is_symlink()
                    or path.stat().st_nlink != 1
                    or not _contained(path, temp)):
                return {**refused, "reason": "SOURCE_NOT_DISPOSABLE", "artifact": name}
            sources[name] = path
        output.mkdir(mode=0o700)
        contents = {}
        for name, source in sources.items():
            before = digest(source)
            target = output / (name + ".bin")
            with source.open("rb") as stream, target.open("xb") as sink:
                shutil.copyfileobj(stream, sink)
                sink.flush()
                os.fsync(sink.fileno())
            after = digest(source)
            copied = digest(target)
            if before != after or copied != before:
                raise ValueError("SOURCE_CHANGED_DURING_FREEZE")
            contents[name] = {"name": target.name, "sha256": copied,
                              "bytes": target.stat().st_size}
        body = {"purpose": PURPOSE, "schema": 1,
                "transaction_id": transaction_id, "source_commit": source_commit,
                "scopes": {**scopes, "hkcu_prefix": hkcu_prefix}, "artifacts": contents}
        encoded = (json.dumps(body, sort_keys=True, separators=(",", ":")) + "\n").encode()
        manifest = output / "manifest.json"
        with manifest.open("xb") as sink:
            sink.write(encoded)
            sink.flush()
            os.fsync(sink.fileno())
        return {"state": "P9B_LAB_BUNDLE_FROZEN", "frozen": True,
                "manifest": str(manifest), "manifest_sha256": hashlib.sha256(encoded).hexdigest(),
                "trusted_origin": False, "production_modified": False}
    except (OSError, ValueError, TypeError, KeyError) as error:
        return {**refused, "reason": str(error) or type(error).__name__}


def verify_disposable_bundle(manifest, expected_sha256, *, temp_root=None):
    refused = {"state": "P9B_LAB_BUNDLE_UNVERIFIED", "verified": False,
               "trusted_origin": False, "production_modified": False}
    try:
        temp = Path(temp_root or tempfile.gettempdir()).resolve(strict=True)
        system_temp = Path(tempfile.gettempdir()).resolve(strict=True)
        if temp != system_temp and system_temp not in temp.parents:
            return {**refused, "reason": "TEMP_ROOT_UNTRUSTED"}
        path = Path(manifest)
        if (not path.is_file() or path.is_symlink() or not _contained(path, temp)
                or path.stat().st_size > 16384):
            return {**refused, "reason": "MANIFEST_PATH_INVALID"}
        raw = path.read_bytes()
        if (not isinstance(expected_sha256, str)
                or hashlib.sha256(raw).hexdigest() != expected_sha256):
            return {**refused, "reason": "MANIFEST_DIGEST_MISMATCH"}
        body = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_pairs)
        if (not isinstance(body, dict) or body.get("purpose") != PURPOSE
                or type(body.get("schema")) is not int or body["schema"] != 1
                or set(body.get("artifacts", {})) != set(NAMES)
                or not isinstance(body.get("scopes"), dict)
                or set(body["scopes"]) != {"installed","appdata","desktop","hkcu_prefix"}
                or not isinstance(body.get("transaction_id"), str)
                or len(body["transaction_id"]) != 32
                or any(c not in "0123456789abcdef" for c in body["transaction_id"])
                or not isinstance(body.get("source_commit"), str)
                or len(body["source_commit"]) != 40
                or any(c not in "0123456789abcdef" for c in body["source_commit"])):
            return {**refused, "reason": "MANIFEST_SCHEMA_INVALID"}
        for name in ("installed", "appdata", "desktop"):
            raw_scope = body["scopes"][name]
            if not isinstance(raw_scope, str) or not _contained(raw_scope, temp):
                return {**refused, "reason": "SCOPE_OUTSIDE_LAB"}
        prefix = body["scopes"]["hkcu_prefix"]
        if (not isinstance(prefix, str)
                or not prefix.startswith("Software\\CodeBridge_P9B_Lab\\")
                or len(prefix) > 220):
            return {**refused, "reason": "HKCU_SCOPE_INVALID"}
        root = path.parent.resolve()
        for name in NAMES:
            entry = body["artifacts"][name]
            target = root / (name + ".bin")
            if (not isinstance(entry, dict) or entry.get("name") != target.name
                    or not target.is_file() or target.is_symlink()
                    or target.stat().st_nlink != 1
                    or digest(target) != entry.get("sha256")
                    or target.stat().st_size != entry.get("bytes")):
                return {**refused, "reason": "FROZEN_ARTIFACT_CHANGED", "artifact": name}
        return {"state": "P9B_LAB_BUNDLE_CONSISTENT", "verified": True,
                "trusted_origin": False, "production_modified": False,
                "transaction_id": body.get("transaction_id")}
    except (OSError, ValueError, KeyError, TypeError, UnicodeError):
        return {**refused, "reason": "BUNDLE_CHECK_FAILED"}