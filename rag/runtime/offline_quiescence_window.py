"""Read-only synthetic quiescence-window probe; NEVER authorizes real backup."""
from __future__ import annotations

import hashlib
from pathlib import Path
import time

from rag.runtime.offline_fixture_snapshot import _root, _hash_tree, _redirected
from rag.runtime.offline_quiescence_advisory import inspect_processes
from rag.runtime.offline_fixture_file_guard import hold_fixture_files_readonly, FixtureFileBusy
from rag.runtime.generation_process_lock import generation_lock, GenerationBusy


def _fingerprints(root):
    files = [root / "rag_index.sqlite3", root / "rag-index-manifest.json"]
    qdrant = root / "qdrant"
    if any(not p.is_file() or _redirected(p) for p in files):
        raise ValueError("missing or redirected fixture")
    if not qdrant.is_dir() or _redirected(qdrant):
        raise ValueError("missing or redirected vector directory")
    result = {}
    for p in files:
        if p.stat().st_nlink != 1:
            raise ValueError("hardlinked fixture source")
        result[p.name] = hashlib.sha256(p.read_bytes()).hexdigest()
    result.update({"qdrant/" + k: v for k, v in _hash_tree(qdrant).items()})
    if len(result) <= 2:
        raise ValueError("empty vector fixture")
    return result


def inspect_synthetic_quiet_window(root_path, *, samples=3, delay=0.01,
                                   process_inspector=inspect_processes, pause=time.sleep):
    """Hold read-only Windows handles across samples; process inventory stays advisory.

    Return BLOCKED for observed activity/errors, otherwise LAB_STABLE_BUT_UNPROVEN.
    This cannot detect every writer or prove a production shutdown.
    """
    outcome = {"state": "BLOCKED", "copy_authorized": False,
               "publication_authorized": False, "production_quiescence_proven": False,
               "samples_completed": 0, "issues": []}
    try:
        root = _root(root_path)
        if not isinstance(samples, int) or isinstance(samples, bool) or not 2 <= samples <= 10:
            raise ValueError("invalid sample count")
        if not isinstance(delay, (int, float)) or not 0 <= delay <= 2:
            raise ValueError("invalid delay")
        with generation_lock(root, "offline_capture", exclusive=True):
            all_files = [root / "rag_index.sqlite3", root / "rag-index-manifest.json"]
            all_files += [p for p in (root / "qdrant").rglob("*") if p.is_file()]
            # Fail before reading if any watched path is a reparse point or hardlink.
            _fingerprints(root)
            with hold_fixture_files_readonly(all_files):
                first = None
                for i in range(samples):
                    check = process_inspector()
                    if (not check.get("process_listing_ok") or
                            check.get("state") != "UNPROVEN_QUIESCENCE"):
                        outcome["issues"].append("ACTIVE_OR_UNVERIFIED_PROCESSES")
                        break
                    current = _fingerprints(root)
                    outcome["samples_completed"] = i + 1
                    if first is None:
                        first = current
                    elif first != current:
                        outcome["issues"].append("FIXTURE_CHANGED_DURING_WINDOW")
                        break
                    if i < samples - 1:
                        pause(delay)
                else:
                    outcome["state"] = "LAB_STABLE_BUT_UNPROVEN"
    except (OSError, ValueError, RuntimeError, TypeError, KeyError, FixtureFileBusy, GenerationBusy) as exc:
        outcome["issues"].append(type(exc).__name__)
    return outcome
