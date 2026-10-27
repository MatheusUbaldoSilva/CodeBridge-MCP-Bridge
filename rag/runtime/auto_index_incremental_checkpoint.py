"""RAG-AUTO-05-E durable isolated batch receipt and recovery guard."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from rag.runtime.auto_index_incremental_plan import IncrementalPlanError


def _receipt_payload(batch_id: str, record: dict) -> dict:
    if not isinstance(batch_id,str) or len(batch_id) != 32 or any(ch not in "0123456789abcdef" for ch in batch_id):
        raise IncrementalPlanError("invalid immutable batch identifier")
    if (not isinstance(record,dict)
            or record.get("mode") != "ISOLATED_STAGE_BATCH_WRITTEN"
            or record.get("public_pointer_updated") is not False
            or type(record.get("vectors_written")) is not int
            or not 1 <= record["vectors_written"] <= 256
            or record.get("requires_staging_revalidation") is not True):
        raise IncrementalPlanError("batch write has no valid isolated-stage result")
    return {"schema_version":1,"batch_id":batch_id,
            "vectors_written":record["vectors_written"],
            "state":"NEEDS_QDRANT_REVALIDATION","public_pointer_updated":False}


def persist_isolated_batch_receipt(stage_path: Path, batch_id: str, record: dict, *,
                                   allow_write: bool = False) -> dict:
    if allow_write is not True:
        raise PermissionError("explicit stage receipt write required")
    stage=Path(stage_path)
    if not stage.is_dir() or stage.is_symlink() or (hasattr(stage,"is_junction") and stage.is_junction()):
        raise IncrementalPlanError("stage must be an existing isolated non-redirected directory")
    data=_receipt_payload(batch_id,record)
    body=json.dumps(data,sort_keys=True,separators=(",",":")).encode("utf-8")
    data["receipt_sha256"]=hashlib.sha256(body).hexdigest()
    target=stage/("batch_"+batch_id+".json")
    temp=stage/("batch_"+batch_id+".writing")
    if target.exists() or temp.exists() or target.is_symlink() or temp.is_symlink():
        raise IncrementalPlanError("batch receipt exists or interrupted write must be audited")
    encoded=json.dumps(data,sort_keys=True,indent=2)+"\n"
    with temp.open("x",encoding="utf-8",newline="\n") as file:
        file.write(encoded)
        file.flush()
        os.fsync(file.fileno())
    os.replace(temp,target)
    return {"receipt_path":str(target),"receipt_sha256":data["receipt_sha256"],
            "revalidation_required":True}


def read_isolated_batch_receipt(stage_path: Path,batch_id: str) -> dict:
    stage=Path(stage_path)
    _receipt_payload(batch_id,{"mode":"ISOLATED_STAGE_BATCH_WRITTEN",
                               "vectors_written":1,"public_pointer_updated":False,
                               "requires_staging_revalidation":True})
    target=stage/("batch_"+batch_id+".json")
    if (stage.is_symlink() or target.is_symlink() or
            (hasattr(stage,"is_junction") and stage.is_junction()) or not target.is_file()):
        raise IncrementalPlanError("missing or redirected batch receipt")
    if target.stat().st_size > 16384:
        raise IncrementalPlanError("batch receipt exceeds safe size")
    item=json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(item,dict):
        raise IncrementalPlanError("invalid batch receipt payload")
    checksum=item.pop("receipt_sha256",None)
    body=json.dumps(item,sort_keys=True,separators=(",",":")).encode("utf-8")
    if (item.get("schema_version") != 1 or item.get("batch_id") != batch_id
            or item.get("state") != "NEEDS_QDRANT_REVALIDATION"
            or type(item.get("vectors_written")) is not int
            or not 1 <= item["vectors_written"] <= 256
            or item.get("public_pointer_updated") is not False
            or checksum != hashlib.sha256(body).hexdigest()):
        raise IncrementalPlanError("batch receipt altered")
    return {**item,"receipt_sha256":checksum}
