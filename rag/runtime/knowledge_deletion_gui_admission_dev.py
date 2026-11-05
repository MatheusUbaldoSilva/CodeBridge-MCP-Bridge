"""DEV GUI opt-in, one-shot, read-only RAG-DEL admission diagnostic.

NEVER handles DELETE, mutates RAG data, or authorizes deletion. Uses the
already-tested scratch-only Named Pipe PRECHECK service inside the GUI process
when an explicit DEV diagnostic environment opt-in is present. The installed
Stable runtime never needs this feature or a restart.
"""
from __future__ import annotations

import os
from pathlib import Path
import sys
import threading
import uuid

OPT_IN_ENV = "CODEBRIDGE_RAGDEL_DEV_ADMISSION_DIAGNOSTIC"


def start_gui_admission_diagnostic_dev(
    *, inventory_reader=None, project_reader=None, review_reader=None
) -> str | None:
    """Start one admission-only test connection, never a mutation listener.

    A supplied reader is used solely by isolated tests. DEV defaults read
    the existing queue/catalog with query_only, never opening a writer.
    """
    if os.environ.get(OPT_IN_ENV) != "1":
        return None
    from PySide6.QtWidgets import QApplication
    if QApplication.instance() is None:
        raise RuntimeError("DEV GUI QApplication must exist")
    if "rag_panel" not in sys.modules:
        raise RuntimeError("DEV RagPanel module must already be imported")

    from rag.runtime.knowledge_deletion_admission_pipe_dev import (
        serve_one_deletion_admission_precheck_dev,
    )

    if inventory_reader is None:
        def inventory_reader():
            from rag.runtime.auto_index_queue import default_queue_path
            from rag.runtime.knowledge_deletion_operational_reconcile_dev import (
                reconcile_operational_generation_read_only,
            )
            root = Path.home() / "AppData" / "Local" / "CodeBridge" / "rag"
            return reconcile_operational_generation_read_only(root, default_queue_path())
    if project_reader is None:
        def project_reader(project_id):
            from rag.runtime.auto_index_queue import default_queue_path
            from rag.runtime.knowledge_deletion_project_conflicts_dev import (
                inspect_project_conflicts_read_only,
            )
            root = Path.home() / "AppData" / "Local" / "CodeBridge" / "rag"
            return inspect_project_conflicts_read_only(
                project_id=project_id, catalog_directory=root,
                queue_path=default_queue_path(),
            )
    if review_reader is None:
        from rag.runtime.knowledge_deletion_review import build_deletion_review
        review_reader=build_deletion_review
    if (not callable(inventory_reader) or not callable(project_reader)
            or not callable(review_reader)):
        raise TypeError("read-only observers required")

    name = r"\\.\pipe\CB.RAGDEL.ADMISSION.SCRATCH." + uuid.uuid4().hex
    def handle():
        try:
            serve_one_deletion_admission_precheck_dev(
                name,
                # Explicitly UNVERIFIED: an in-process diagnostic cannot
                # promote its own GUI identity into security authorization.
                get_gui_witness=lambda: {"state":"GUI_WITNESS_NOT_ATTESTED"},
                get_operational_inventory=inventory_reader,
                get_project_conflicts=project_reader,
                get_server_review=review_reader,
            )
        except Exception:
            # Diagnostic transport must not affect the GUI event loop.
            return
    worker = threading.Thread(
        target=handle, name="RAGDEL-Admission-Diagnostic-DEV",daemon=True
    )
    worker.start()
    return name
