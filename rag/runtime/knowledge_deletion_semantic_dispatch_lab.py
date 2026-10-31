"""DQ-E-D-2: scratch semantic dispatch under already-held parent lock only.

No MCP/real semantic child is used. An injected synthetic dispatch is the
only supported execution path until parent-child pin IPC is operationally
verified by an independent attestation.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from rag.runtime.knowledge_deletion_pin_ipc_lab import (
    envelope_from_private_lab_pin,
)
from rag.runtime.knowledge_deletion_private_read_session_lab import PrivateLabPin


def dispatch_semantic_already_locked_lab(
    query: Any, route: Any, *, pin: PrivateLabPin,
    catalog_file: Path, executor: Callable[..., Any],
    laboratory_mode: bool = False, operator_approved: bool = False,
) -> Any:
    """Pass immutable pinned IPC evidence to a synthetic executor once.

    Never calls production_generation_lock: semantic is already held by
    private_read_session_lab, and the parent retains all locks until return.
    """
    if laboratory_mode is not True or operator_approved is not True:
        raise PermissionError("scratch semantic dispatch approval required")
    if not callable(executor):
        raise TypeError("explicit synthetic executor required")
    if not hasattr(query, "project_id") or query.project_id != pin.project_id:
        raise PermissionError("cross-project semantic query denied")
    envelope = envelope_from_private_lab_pin(
        pin, catalog_file=catalog_file, laboratory_mode=True,
    )
    return pin.call_semantic_already_locked(executor,query,route,envelope)
