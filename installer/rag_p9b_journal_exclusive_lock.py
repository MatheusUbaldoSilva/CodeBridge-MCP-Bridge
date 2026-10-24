"""OS-backed exclusive lock for disposable P9-B rollback journals.

The persistent sidecar is initialized while holding the same OS lock used by
all subsequent readers. Never delete it; local advisory locking is not trust.
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
    created = False
    try:
        stream = lock.open("x+b")
        created = True
    except FileExistsError:
        stream = lock.open("r+b")
    with stream:
        stream.seek(0)
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(stream.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        try:
            if lock.is_symlink() or not lock.is_file():
                raise ValueError("JOURNAL_LOCK_PATH_INVALID")
            if created:
                if lock.stat().st_size != 0:
                    raise ValueError("JOURNAL_LOCK_PATH_INVALID")
                stream.write(b"1")
                stream.flush()
                os.fsync(stream.fileno())
            else:
                stream.seek(0)
                if lock.stat().st_size != 1 or stream.read(1) != b"1":
                    raise ValueError("JOURNAL_LOCK_PATH_INVALID")
            yield
        finally:
            stream.seek(0)
            if os.name == "nt":
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)