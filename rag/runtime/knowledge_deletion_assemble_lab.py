"""RAG-DEL-01.03-E: offline LAB-only generation receipt assembly.

Only writes to a fresh candidate under an ephemeral temporary directory;
the caller must have independently validated the candidate and closed Qdrant.
No catalog switch or deletion action.
"""
from __future__ import annotations
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import tempfile
from rag.runtime.knowledge_deletion_bundle import verify_deletion_review_bundle
from rag.runtime.knowledge_deletion_generation import digest_file
from rag.runtime.knowledge_deletion_qdrant_freeze import fingerprint_closed_qdrant_store

class DeletionGenerationAssemblyError(RuntimeError):
    pass

def assemble_lab_deletion_generation(stage:Path,source_snapshot:Path,
                                    project_id:str,source_revision:str,
                                    transaction_id:str,preview:dict,bundle:dict,
                                    *,laboratory_mode:bool=False) -> dict:
    if laboratory_mode is not True: raise PermissionError("laboratory-only API")
    stage=Path(stage)
    snapshot=Path(source_snapshot)
    tid=transaction_id
    root=Path(tempfile.gettempdir()).resolve(strict=True)
    if (not stage.is_dir() or not snapshot.is_dir() or
            not stage.is_absolute() or not snapshot.is_absolute() or
            not stage.resolve(strict=True).is_relative_to(root) or
            not snapshot.resolve(strict=True).is_relative_to(root) or
            stage.name!="del_"+tid or stage.parent.name!="generations" or
            snapshot.parent.name!="snapshots" or snapshot.name!="source_"+tid or
            not re.fullmatch(r"[a-f0-9]{32}",tid) or
            not re.fullmatch(r"[a-f0-9]{64}",source_revision) or
            not re.fullmatch(r"[a-z][a-z0-9_-]{1,63}",project_id)):
        raise DeletionGenerationAssemblyError("unsafe laboratory layout")
    if ((stage/"progress.json").exists() or
            (stage/"deletion-generation-receipt.json").exists()):
        raise DeletionGenerationAssemblyError("generation receipt already present")
    if (preview.get("project_id")!=project_id or
            preview.get("source_revision")!=source_revision or
            preview.get("deletion_authorized") is not False or
            not isinstance(preview.get("chunks_to_preserve"),int) or
            preview["chunks_to_preserve"]<0 or
            bundle.get("project_id")!=project_id or
            bundle.get("selection_sha256")!=preview.get("review_sha256")):
        raise DeletionGenerationAssemblyError("invalid preview/bundle")
    if (bundle.get("activation_authorized") is not False or
            bundle.get("operational_use_allowed") is not False):
        raise DeletionGenerationAssemblyError("unexpected bundle authorization")
    verify_deletion_review_bundle(stage,bundle)
    inventory=fingerprint_closed_qdrant_store(stage/"qdrant")
    db=stage/"rag_index.sqlite3"
    manifest=stage/"rag-index-manifest.json"
    if not db.is_file() or not manifest.is_file():
        raise DeletionGenerationAssemblyError("missing candidate artifacts")
    sqlite_sha=digest_file(db)
    manifest_sha=digest_file(manifest)
    progress={
        "project_id":project_id,"source_revision":source_revision,
        "transaction_id":tid,"state":"INDEXING_NOT_PUBLISHED",
        "total_vectors_done":preview["chunks_to_preserve"],
        "expected_chunks":preview["chunks_to_preserve"],
        "last_batch_result":"COMPLETE","published":False,
    }
    receipt={
        "schema_version":1,"state":"VERIFIED_NOT_REGISTERED",
        "index_family":"RAG_DEL_01","transaction_id":tid,
        "project_id":project_id,"source_revision":source_revision,
        "source_snapshot":str(snapshot),
        "baseline_generation":preview["generation"],
        "selection_sha256":preview["review_sha256"],
        "review_bundle_sha256":bundle["bundle_sha256"],
        "sqlite_sha256":sqlite_sha,"manifest_sha256":manifest_sha,
        "qdrant_inventory_sha256":inventory["inventory_sha256"],
        "vectors_verified":preview["chunks_to_preserve"],
        "published_publicly":False,"activation_authorized":False,
    }
    # Exclusive creation: on interruption the stage remains quarantined.
    for name,value in (("progress.json",progress),
                       ("deletion-generation-receipt.json",receipt)):
        encoded=(json.dumps(value,sort_keys=True,indent=2)+"\n").encode("utf-8")
        fd=os.open(stage/name,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
        with os.fdopen(fd,"wb") as f:
            f.write(encoded)
            f.flush()
            os.fsync(f.fileno())
    return {
        "index_family":"RAG_DEL_01","transaction_id":tid,
        "project_id":project_id,"enabled":True,
        "source_revision":source_revision,
        "source_directory":str(snapshot),
        "generation_directory":str(stage),
        "generation_receipt_sha256":digest_file(stage/"deletion-generation-receipt.json"),
        "sqlite_sha256":sqlite_sha,"manifest_sha256":manifest_sha,
        "activation_authorized":False,
    }
