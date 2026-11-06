"""Strict read-only RAG_DEL_01 generation contract validator."""
from __future__ import annotations
from hashlib import sha256
import json
from pathlib import Path
import re

HEX64=re.compile(r"[0-9a-f]{64}\Z")
HEX32=re.compile(r"[0-9a-f]{32}\Z")
REVISION=re.compile(r"[0-9a-f]{40}(?:[0-9a-f]{24})?\Z")

class DeletionGenerationUnavailable(RuntimeError):
    pass

def digest_file(path:Path)->str:
    h=sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda:stream.read(1048576),b""):
            h.update(chunk)
    return h.hexdigest()

def verify_deletion_generation(row:dict,project_id:str,generation:Path,source_root:Path,revision:str)->dict:
    """Validate row/receipt/progress/anchor artifacts without writing or opening Qdrant."""
    fail=DeletionGenerationUnavailable
    tid=row.get("transaction_id")
    if not isinstance(tid,str) or not HEX32.fullmatch(tid):
        raise fail("invalid deletion transaction id")
    if generation.name!="del_"+tid or generation.parent.name!="generations":
        raise fail("deletion generation layout mismatch")
    if not isinstance(revision,str) or not REVISION.fullmatch(revision):
        raise fail("invalid deletion source revision")
    if not isinstance(row.get("generation_receipt_sha256"),str) or not HEX64.fullmatch(row["generation_receipt_sha256"]):
        raise fail("missing pinned receipt digest")
    receipt_path=generation/"deletion-generation-receipt.json"
    if not receipt_path.is_file() or receipt_path.is_symlink():
        raise fail("deletion receipt missing")
    if digest_file(receipt_path)!=row["generation_receipt_sha256"]:
        raise fail("deletion receipt file changed")
    receipt=json.loads(receipt_path.read_text(encoding="utf-8"))
    if (receipt.get("schema_version")!=1 or receipt.get("state")!="VERIFIED_NOT_REGISTERED"
            or receipt.get("index_family")!="RAG_DEL_01"
            or receipt.get("transaction_id")!=tid
            or receipt.get("project_id")!=project_id
            or receipt.get("source_revision")!=revision
            or receipt.get("source_snapshot")!=str(source_root)
            or receipt.get("published_publicly") is not False
            or receipt.get("activation_authorized") is not False):
        raise fail("deletion receipt identity mismatch")
    for field in ("baseline_generation","selection_sha256","review_bundle_sha256"):
        value=receipt.get(field)
        if not isinstance(value,str) or (field!="baseline_generation" and not HEX64.fullmatch(value)):
            raise fail("deletion provenance missing")
    for field,name in (("sqlite_sha256","rag_index.sqlite3"),
                       ("manifest_sha256","rag-index-manifest.json")):
        expected=row.get(field)
        path=generation/name
        if not isinstance(expected,str) or not HEX64.fullmatch(expected) or not path.is_file() or path.is_symlink():
            raise fail("missing deletion anchor")
        if digest_file(path)!=expected or receipt.get(field)!=expected:
            raise fail("deletion anchor changed")
    qdrant=generation/"qdrant"
    if not qdrant.is_dir() or qdrant.is_symlink():
        raise fail("deletion vector store unavailable")
    from rag.runtime.knowledge_deletion_qdrant_freeze import fingerprint_closed_qdrant_store
    frozen=fingerprint_closed_qdrant_store(qdrant)
    if frozen["inventory_sha256"]!=receipt.get("qdrant_inventory_sha256"):
        raise fail("deletion vector store changed")
    progress=generation/"progress.json"
    if not progress.is_file() or progress.is_symlink():
        raise fail("deletion progress missing")
    state=json.loads(progress.read_text(encoding="utf-8"))
    if (state.get("project_id")!=project_id or state.get("source_revision")!=revision
            or state.get("transaction_id")!=tid or state.get("state")!="INDEXING_NOT_PUBLISHED"
            or state.get("last_batch_result")!="COMPLETE"
            or state.get("total_vectors_done")!=state.get("expected_chunks")
            or state.get("total_vectors_done")!=receipt.get("vectors_verified")
            or state.get("published") is not False):
        raise fail("deletion progress mismatch")
    return receipt
