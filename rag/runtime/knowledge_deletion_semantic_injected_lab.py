"""DQ-E-D-3C-D: dry-run semantic executor binding on a pinned TEMP generation.

An injected callback substitutes for a model. This is neither a production
semantic route nor proof of a signed Qdrant snapshot/liveness of another PID.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from rag.contracts import SearchResult
from rag.runtime.production_generation_read import SearchStoragePaths
from rag.runtime.knowledge_deletion_private_read_session_lab import PrivateLabPin
from rag.runtime.knowledge_deletion_semantic_dispatch_lab import (
    dispatch_semantic_already_locked_lab,
)
from rag.runtime.knowledge_deletion_semantic_request_lab import (
    PinnedSemanticRequestV1, verify_pinned_semantic_request_lab,
)
from rag.runtime.knowledge_deletion_bounded_catalog_lab import (
    _validated_scratch_catalog,
)


class InjectedSemanticLabError(RuntimeError):
    pass


def invoke_pinned_semantic_injected_lab(
    query: Any, route: Any, *, pin: PrivateLabPin, catalog_file: Path,
    model_stub: Callable[..., tuple[SearchResult, ...]],
    laboratory_mode: bool = False, operator_approved: bool = False,
) -> tuple[SearchResult, ...]:
    """Execute ONLY injected callable with verified SearchStoragePaths.

    Parent retains generation(shared)->semantic(exclusive)->catalog during
    entire call; no lock is acquired here or in the injected callback.
    """
    if laboratory_mode is not True or operator_approved is not True:
        raise PermissionError("scratch semantic injection requires lab approval")
    if not callable(model_stub):
        raise TypeError("explicit injected model stub required")

    def call_under_parent_lock(q,r,envelope):
        request=PinnedSemanticRequestV1.parse({
            "schema_version":1,"pin":envelope.to_payload(),
            "query":q.query,"route":r.value,"top_k":q.top_k,
            "source_types":[s.value for s in q.source_types],
            "path_filter":q.path_filter,"branch":q.branch,
        })
        verify_pinned_semantic_request_lab(
            request,catalog_file=catalog_file,laboratory_mode=True,
        )
        catalog,root=_validated_scratch_catalog(catalog_file)
        generation=root/"generations"/request.pin.generation_id
        qdrant=generation/"qdrant"
        if (not qdrant.is_dir() or qdrant.is_symlink()
                or (hasattr(qdrant,"is_junction") and qdrant.is_junction())
                or not qdrant.resolve(strict=True).is_relative_to(generation.resolve(strict=True))):
            raise InjectedSemanticLabError("scratch Qdrant directory missing or redirected")
        paths=SearchStoragePaths(
            generation=request.pin.generation_id,
            sqlite=generation/"rag_index.sqlite3",
            manifest=generation/"rag-index-manifest.json",
            qdrant=qdrant,
        )
        # The real production_search path is NEVER called here. Stub receives
        # exactly the same pinned storage dataclass used by the real engine.
        returned=model_stub(q,r,_generation_paths=paths)
        if type(returned) is not tuple or any(
            type(item) is not SearchResult
            or item.metadata.project_id!=pin.project_id
            or item.stale
            for item in returned
        ):
            raise InjectedSemanticLabError("synthetic results escaped private namespace or became stale")
        verify_pinned_semantic_request_lab(
            request,catalog_file=catalog,laboratory_mode=True,
        )
        return returned

    return dispatch_semantic_already_locked_lab(
        query,route,pin=pin,catalog_file=catalog_file,
        executor=call_under_parent_lock,
        laboratory_mode=True,operator_approved=True,
    )