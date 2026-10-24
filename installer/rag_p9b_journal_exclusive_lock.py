"""OS-backed exclusive lock for one disposable P9-B rollback journal.

The lock sidecar persists across process crashes to keep the lock inode stable.
A host-local advisory lock does not authenticate an untrusted filesystem.
"""
from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def exclusive_journal_lock(path):
    journal = Path(path).absolute()
    lock = journal.with_name(journal.name + ".lock")
    if (not journal.parent.is_dir() or journal.parent.is_symlink()
            or lock.is_symlink() or (lock.exists() and not lock.is_file())):
        raise ValueError("JOURNAL_LOCK_PATH_INVALID")
    try:
        with lock.open("xb") as initializer:
            initializer.write(b"1")
            initializer.flush()
            os.fsync(initializer.fileno())
    except FileExistsError:
        pass
    if lock.is_symlink() or not lock.is_file() or lock.stat().st_size!=1:
        raise ValueError("JOURNAL_LOCK_PATH_INVALID")
    with lock.open("r+b") as stream:
        stream.seek(0)
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(stream.fileno(), msvcrt.LK_LOCK, 1)
            try:
                yield
            finally:
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)