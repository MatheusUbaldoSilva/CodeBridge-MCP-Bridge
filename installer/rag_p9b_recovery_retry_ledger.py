"""Disposable-lab durable retry ledger for independent P9-B scheduled recovery.

Records bounded attempts only. Does not launch NSIS, create a scheduled task,
trust publisher identity or permit any production write.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from pathlib import Path

from installer.rag_p9b_journal_exclusive_lock import exclusive_journal_lock
from installer.rag_p9b_frozen_disposable_bundle import _contained

_HEX = re.compile(r"^[0-9a-f]{64}$")
_PURPOSE = "P9B_DISPOSABLE_RETRY_LEDGER_V1"
_MAX_ATTEMPTS = 3


def _safe_pairs(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise ValueError("DUPLICATE_KEY")
        out[key] = value
    return out


def _validate_record(doc, transaction_sha):
    return (type(doc) is dict
            and set(doc) == {"purpose", "transaction_sha256", "attempts",
                              "state", "schema"}
            and doc["purpose"] == _PURPOSE
            and type(doc["schema"]) is int and doc["schema"] == 1
            and doc["transaction_sha256"] == transaction_sha
            and type(doc["attempts"]) is int
            and 0 <= doc["attempts"] <= _MAX_ATTEMPTS
            and doc["state"] in {"READY", "REVIEW_REQUIRED", "TERMINAL"})


def reserve_disposable_retry(path, *, transaction_sha256, temp_root=None):
    refused = {"state": "P9B_RETRY_REFUSED", "reserved": False,
               "production_modified": False, "cutover_authorized": False}
    if not isinstance(transaction_sha256, str) or _HEX.fullmatch(transaction_sha256) is None:
        return {**refused, "reason": "TRANSACTION_SHA_INVALID"}
    target = Path(path).absolute()
    temp = Path(temp_root or tempfile.gettempdir()).resolve(strict=True)
    system_temp = Path(tempfile.gettempdir()).resolve(strict=True)
    if (temp != system_temp and system_temp not in temp.parents
            or not _contained(target.parent, temp) or target.parent.is_symlink()
            or target.is_symlink() or (target.exists() and not target.is_file())):
        return {**refused, "reason": "RETRY_PATH_NOT_DISPOSABLE"}
    try:
        with exclusive_journal_lock(target):
            if target.exists():
                if target.stat().st_size > 2048:
                    return {**refused, "reason": "LEDGER_UNVERIFIED"}
                doc = json.loads(target.read_text(encoding="utf-8"),
                                 object_pairs_hook=_safe_pairs)
                if not _validate_record(doc, transaction_sha256):
                    return {**refused, "reason": "LEDGER_IDENTITY_OR_SCHEMA_MISMATCH"}
            else:
                doc = {"schema": 1, "purpose": _PURPOSE,
                       "transaction_sha256": transaction_sha256,
                       "attempts": 0, "state": "READY"}
            if doc["state"] == "TERMINAL":
                return {**refused, "state": "P9B_RECOVERY_ALREADY_TERMINAL",
                        "reason": "DURABLE_TERMINAL_STATE", "attempts": doc["attempts"]}
            if doc["state"] == "REVIEW_REQUIRED" or doc["attempts"] >= _MAX_ATTEMPTS:
                return {**refused, "state": "P9B_RECOVERY_REVIEW_REQUIRED",
                        "reason": "RETRY_BUDGET_EXHAUSTED",
                        "attempts": doc["attempts"]}
            doc["attempts"] += 1
            if doc["attempts"] == _MAX_ATTEMPTS:
                doc["state"] = "REVIEW_REQUIRED"
            encoded = (json.dumps(doc, sort_keys=True, separators=(",", ":"))+"\n").encode()
            tmp = target.with_name(target.name + ".pending")
            if tmp.exists() or tmp.is_symlink():
                return {**refused, "reason": "RETRY_TEMP_COLLISION"}
            try:
                with tmp.open("xb") as stream:
                    stream.write(encoded)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(tmp, target)
            finally:
                if tmp.exists() and not tmp.is_symlink():
                    tmp.unlink()
            return {**refused, "state": "P9B_DISPOSABLE_RETRY_RESERVED",
                    "reserved": True, "attempt": doc["attempts"],
                    "remaining": _MAX_ATTEMPTS - doc["attempts"],
                    "requires_external_scheduler": True,
                    "requires_authenticated_transaction": True}
    except (OSError, TypeError, ValueError, UnicodeError, KeyError):
        return {**refused, "reason": "LEDGER_UNVERIFIED"}

def mark_disposable_retry_terminal(path, *, transaction_sha256, temp_root=None,
                                   postverified=False):
    """Store idempotent terminal evidence, never authorize production actions."""
    refused = {"state": "P9B_TERMINAL_REFUSED", "written": False,
               "production_modified": False, "cutover_authorized": False}
    if postverified is not True:
        return {**refused, "reason": "POSTVERIFICATION_REQUIRED"}
    if not isinstance(transaction_sha256, str) or _HEX.fullmatch(transaction_sha256) is None:
        return {**refused, "reason": "TRANSACTION_SHA_INVALID"}
    target = Path(path).absolute()
    temp = Path(temp_root or tempfile.gettempdir()).resolve(strict=True)
    system_temp = Path(tempfile.gettempdir()).resolve(strict=True)
    if (temp != system_temp and system_temp not in temp.parents
            or not _contained(target.parent, temp) or target.is_symlink()
            or not target.is_file()):
        return {**refused, "reason": "TERMINAL_PATH_NOT_DISPOSABLE"}
    try:
        with exclusive_journal_lock(target):
            if target.stat().st_size > 2048:
                return {**refused, "reason": "LEDGER_UNVERIFIED"}
            doc = json.loads(target.read_text(encoding="utf-8"),
                             object_pairs_hook=_safe_pairs)
            if not _validate_record(doc, transaction_sha256):
                return {**refused, "reason": "LEDGER_IDENTITY_OR_SCHEMA_MISMATCH"}
            if doc["state"] == "TERMINAL":
                return {**refused, "state": "P9B_TERMINAL_ALREADY_DURABLE",
                        "attempts": doc["attempts"]}
            if doc["attempts"] == 0:
                return {**refused, "reason": "NO_RECOVERY_ATTEMPT"}
            doc["state"] = "TERMINAL"
            encoded = (json.dumps(doc, sort_keys=True, separators=(",", ":"))+"\n").encode()
            pending = target.with_name(target.name+".pending")
            if pending.exists() or pending.is_symlink():
                return {**refused, "reason": "RETRY_TEMP_COLLISION"}
            try:
                with pending.open("xb") as stream:
                    stream.write(encoded)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(pending, target)
            finally:
                if pending.exists() and not pending.is_symlink():
                    pending.unlink()
            return {**refused, "state": "P9B_TERMINAL_PERSISTED",
                    "written": True, "attempts": doc["attempts"]}
    except (OSError, TypeError, ValueError, UnicodeError, KeyError):
        return {**refused, "reason": "LEDGER_UNVERIFIED"}