"""Atomic, same-directory shortcut replacement for P9-B recovery.

No automatic parent creation. Existing directories must be real and
non-reparse; sensitive HKCU registry operations remain separate.
"""
from __future__ import annotations

import os
from pathlib import Path
from tempfile import NamedTemporaryFile


def write_atomic_shortcut(target, payload):
    target=Path(target)
    if not isinstance(payload,bytes) or len(payload)>65536:
        raise ValueError("SHORTCUT_PAYLOAD_INVALID")
    if target.is_symlink() or (target.exists() and not target.is_file()):
        raise ValueError("SHORTCUT_TARGET_INVALID")
    if not target.parent.is_dir() or target.parent.is_symlink():
        raise ValueError("SHORTCUT_PARENT_INVALID")
    # Reject any junction/symlink in the existing path, not merely its leaf.
    for parent in target.parents:
        if parent.is_symlink():
            raise ValueError("SHORTCUT_PARENT_SYMLINK")
    tmp=None
    try:
        with NamedTemporaryFile(mode="wb",dir=str(target.parent),
                                prefix=".cb-p9b-",suffix=".tmp",delete=False) as f:
            tmp=Path(f.name)
            f.write(payload)
            f.flush()
            os.fsync(f.fileno())
        if tmp.stat().st_size!=len(payload):
            raise OSError("TEMP_BYTES_MISMATCH")
        # Revalidate the destination immediately before replace.
        if target.is_symlink() or (target.exists() and not target.is_file()):
            raise ValueError("SHORTCUT_TARGET_CHANGED")
        os.replace(tmp,target)
        tmp=None
    finally:
        if tmp is not None:
            try:tmp.unlink(missing_ok=True)
            except OSError:pass


def remove_shortcut_if_present(target):
    target=Path(target)
    if target.is_symlink() or (target.exists() and not target.is_file()):
        raise ValueError("SHORTCUT_TARGET_INVALID")
    if target.parent.is_symlink():
        raise ValueError("SHORTCUT_PARENT_INVALID")
    if target.exists():target.unlink()
