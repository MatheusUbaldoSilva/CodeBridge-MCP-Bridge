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


def restore_test_generation(state_root, chosen, *, fail_before_switch=False):
    root = Path(state_root).resolve()
    if "codebridge-rag-generation-test" not in {p.lower() for p in root.parts}:
        raise ControlledRestoreError("test roots only")
    # Hold this lock across candidate re-validation, pointer change and check.
    with generation_lock(root, PUBLICATION_LOCK_NAME, exclusive=True):
        verified = verify_recovery_candidate(root, chosen)
        previous = resolve_generation(root)
        previous_name = previous.generation if previous is not None else None
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
            selected = resolve_generation(root)
            if selected is None or selected.generation != chosen:
                raise ControlledRestoreError("activation verification failed")
            return {"state": "TEST_RESTORED", "generation": chosen,
                    "previous": previous_name, "report": verified["report"]}
        except BaseException:
            # Never automatically guess or overwrite a pointer after a switch:
            # a failed post-check requires manual recovery.
            if switched:
                raise ControlledRestoreError(
                    "pointer changed but post-check failed; manual inspection required"
                )
            raise
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
