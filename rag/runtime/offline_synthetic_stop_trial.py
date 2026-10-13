"""Synthetic Windows graceful-stop drill; touches only its own child process."""
from __future__ import annotations

from pathlib import Path
import subprocess
import sys

from rag.runtime.offline_fixture_snapshot import _root
from rag.runtime.offline_fixture_file_guard import (
    hold_fixture_files_readonly, FixtureFileBusy,
)


class SyntheticStopTrialError(RuntimeError):
    pass


_CHILD = (
    "import sys;"
    "files=[open(path, 'r+b', buffering=0) for path in sys.argv[1:]];"
    "print('CHILD_READY', flush=True);"
    "signal=sys.stdin.readline().strip();"
    "[file.close() for file in files];"
    "sys.exit(0 if signal=='GRACEFUL_STOP' else 2)"
)


def run_synthetic_stop_trial(fixture_root, *, timeout=8):
    root = _root(fixture_root)
    db = root / "rag_index.sqlite3"
    if not db.is_file() or db.is_symlink() or db.stat().st_nlink > 1:
        raise SyntheticStopTrialError("synthetic SQLite fixture unavailable")
    manifest = root / "rag-index-manifest.json"
    vectors = root / "qdrant"
    vector_file = next((p for p in sorted(vectors.rglob("*")) if p.is_file()), None) if vectors.is_dir() else None
    sources = [db, manifest, vector_file]
    if (vector_file is None or
            any(not p.is_file() or p.is_symlink() or p.stat().st_nlink > 1 for p in sources)):
        raise SyntheticStopTrialError("synthetic cross-store fixture unavailable")
    if not 1 <= timeout <= 20:
        raise SyntheticStopTrialError("invalid timeout")
    proc = subprocess.Popen([sys.executable, "-c", _CHILD, *(str(p) for p in sources)],
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True)
    try:
        ready = proc.stdout.readline().strip()
        if ready != "CHILD_READY":
            raise SyntheticStopTrialError("synthetic child not ready")
        blocked = False
        try:
            with hold_fixture_files_readonly(sources):
                pass
        except FixtureFileBusy:
            blocked = True
        if not blocked:
            raise SyntheticStopTrialError("active synthetic writer was not blocked")
        output, errors = proc.communicate(input="GRACEFUL_STOP\n", timeout=timeout)
        if proc.returncode != 0:
            raise SyntheticStopTrialError("synthetic child did not exit cleanly")
        with hold_fixture_files_readonly(sources):
            pass
        return {"state": "LAB_CHILD_GRACEFULLY_STOPPED",
                "writer_was_blocked": True, "handle_released": True,
                "child_exit_code": 0, "stores_verified": 3,
                "production_quiescence_proven": False,
                "copy_authorized": False, "publication_authorized": False}
    finally:
        if proc.poll() is None:
            proc.kill()  # Only the subprocess spawned by this trial.
            proc.communicate(timeout=5)
