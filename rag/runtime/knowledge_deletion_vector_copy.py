"""RAG-DEL-01.03-B: single bounded batch transfer between supplied isolated clients.

Caller must enforce the client filesystem boundaries and discard incomplete stages.
No catalog registration or public collection opening is performed here.
"""
from __future__ import annotations

from rag.runtime.auto_index_incremental_read import read_reusable_vectors
from rag.runtime.auto_index_incremental_stage_write import import_verified_reuse_batch
from rag.runtime.auto_index_incremental_plan import IncrementalPlanError

import math

# Qdrant (distancia cosseno) renormaliza o vetor ao gravar; um vetor ja
# normalizado volta com diferencas de 1 ULP em float32 (~1.5e-8). Tolerancia
# muito abaixo de qualquer efeito na busca, mas que ainda pega corrupcao real.
VECTOR_READBACK_TOLERANCE = 1e-6


def _same_vector(original, persisted, tolerance=VECTOR_READBACK_TOLERANCE) -> bool:
    if isinstance(original, dict) or isinstance(persisted, dict):
        if not isinstance(original, dict) or not isinstance(persisted, dict):
            return False
        if set(original) != set(persisted):
            return False
        return all(_same_vector(original[k], persisted[k], tolerance) for k in original)
    if not isinstance(original, (list, tuple)) or not isinstance(persisted, (list, tuple)):
        return False
    if len(original) != len(persisted) or not original:
        return False
    for a, b in zip(original, persisted):
        if (isinstance(a, bool) or isinstance(b, bool)
                or not isinstance(a, (int, float)) or not isinstance(b, (int, float))):
            return False
        if not (math.isfinite(a) and math.isfinite(b)) or abs(a - b) > tolerance:
            return False
    return True


def copy_survivor_batch(source_client, staging_client, plan: dict, batch_index: int,
                        *, verified_source: bool = False,
                        isolated_staging: bool = False, operator_approved: bool = False,
                        max_vectors: int = 256) -> dict:
    if (verified_source is not True or isolated_staging is not True
            or operator_approved is not True):
        raise PermissionError("verified source, isolated stage and explicit approval required")
    if source_client is None or staging_client is None or source_client is staging_client:
        raise IncrementalPlanError("separate source and stage clients required")
    if (not isinstance(plan,dict) or plan.get("state")!="SURVIVOR_RECEIPTS_ONLY"
            or plan.get("activation_authorized") is not False
            or plan.get("project_id")=="codebridge"):
        raise IncrementalPlanError("untrusted or public vector plan")
    batches=plan.get("batches")
    if (not isinstance(batch_index,int) or isinstance(batch_index,bool)
            or not isinstance(batches,list) or batch_index<0 or batch_index>=len(batches)):
        raise IncrementalPlanError("invalid batch")
    receipt=batches[batch_index]
    if receipt.get("project_id")!=plan.get("project_id"):
        raise IncrementalPlanError("project drift in batch")
    sources=plan.get("sources")
    records=read_reusable_vectors(source_client,receipt,sources,max_vectors=max_vectors)
    imported=import_verified_reuse_batch(
        staging_client,receipt,sources,records,
        isolated_destination=True,allow_stage_write=True,max_vectors=max_vectors,
    )
    # Recheck persisted vectors and provenance after import.
    verified=read_reusable_vectors(staging_client,receipt,sources,max_vectors=max_vectors)
    written=sum(len(verified[k]) for k in ("TEXT","CODE"))
    if written!=imported["vectors_written"]:
        raise IncrementalPlanError("post-write vector count mismatch; discard stage")
    for kind in ("TEXT", "CODE"):
        before={point["id"]:point for point in records[kind]}
        after={point["id"]:point for point in verified[kind]}
        if set(before)!=set(after):
            raise IncrementalPlanError("post-write point identity mismatch; discard stage")
        for point_id,original in before.items():
            persisted=after[point_id]
            if (persisted["payload"]!=original["payload"]
                    or not _same_vector(original["vector"], persisted["vector"])):
                raise IncrementalPlanError("post-write vector/payload mismatch; discard stage")
    return {"state":"SURVIVOR_BATCH_READBACK_VERIFIED",
            "batch_index":batch_index,"vectors_verified":written,
            "requires_durable_checkpoint":True,
            "generation_activated":False,"public_pointer_updated":False}
