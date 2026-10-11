"""Controlled recovery switch for test-only RAG generation trees.

Never deletes generations and never touches production. The caller explicitly
selects a candidate. Validation and activation share a publication lock.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
import tempfile

from rag.runtime.generation_activation import PUBLICATION_LOCK_NAME
from rag.runtime.generation_process_lock import generation_lock
from rag.runtime.generation_pointer import resolve_generation
from rag.runtime.generation_recovery_candidate import verify_recovery_candidate


class ControlledRestoreError(RuntimeError):
    pass


def restore_test_generation(state_root, chosen, *, fail_before_switch=False, fail_after_switch=False):
    root = Path(state_root).resolve()
    if "codebridge-rag-generation-test" not in {p.lower() for p in root.parts}:
        raise ControlledRestoreError("test roots only")
    # Hold this lock across candidate re-validation, pointer change and check.
    with generation_lock(root, PUBLICATION_LOCK_NAME, exclusive=True):
        verified = verify_recovery_candidate(root, chosen)
        previous = resolve_generation(root)
        previous_name = previous.generation if previous is not None else None
        if previous_name is not None:
            verify_recovery_candidate(root, previous_name)
        pointer = root / "active-generation.json"
        temporary = None
        switched = False
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=root,
                prefix=".restore-generation.", suffix=".tmp", delete=False
            ) as handle:
                temporary = Path(handle.name)
                json.dump({"schema_version": 1, "generation": chosen}, handle)
                handle.flush()
                os.fsync(handle.fileno())
            if fail_before_switch:
                raise ControlledRestoreError("injected failure before switch")
            os.replace(temporary, pointer)
            temporary = None
            switched = True
            if fail_after_switch:
                raise ControlledRestoreError('injected failure after switch')
            selected = resolve_generation(root)
            if selected is None or selected.generation != chosen:
                raise ControlledRestoreError("activation verification failed")
            return {"state": "TEST_RESTORED", "generation": chosen,
                    "previous": previous_name, "report": verified["report"]}
        except BaseException:
            if switched:
                if previous_name is None:
                    raise ControlledRestoreError(
                        "no validated previous generation; manual recovery required"
                    )
                try:
                    verify_recovery_candidate(root, previous_name)
                    with tempfile.NamedTemporaryFile(
                        mode="w", encoding="utf-8", dir=root,
                        prefix=".rollback-generation.", suffix=".tmp", delete=False,
                    ) as handle:
                        rollback_temp = Path(handle.name)
                        json.dump({"schema_version": 1, "generation": previous_name}, handle)
                        handle.flush()
                        os.fsync(handle.fileno())
                    try:
                        os.replace(rollback_temp, pointer)
                    finally:
                        rollback_temp.unlink(missing_ok=True)
                    restored = resolve_generation(root)
                    if restored is None or restored.generation != previous_name:
                        raise ControlledRestoreError("rollback verification failed")
                except Exception as exc:
                    raise ControlledRestoreError("rollback failed; manual recovery required") from exc
                raise ControlledRestoreError("activation failed; previous generation restored")
            raise
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
