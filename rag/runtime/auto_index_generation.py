"""RAG-AUTO-03.2/03.3 — immutable verified candidate, no public activation.

A READY_FOR_REVIEW job is copied into a separate versioned generation with
approved, hash-pinned source files. This module NEVER writes catalog or
active-generation.json. The copy is completed and verified before registration.
"""
from __future__ import annotations

from contextlib import closing
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3

from rag.index.manifest import load_index_manifest
from rag.runtime.auto_index_approval import (
    read_reviewed_sources,revalidate_auto_index_preview,_source_hash,
)
from rag.runtime.auto_index_batch import inventory_auto_vectors
from rag.runtime.auto_index_queue import get_job,AutoIndexQueueError
from rag.runtime.production_publish import validate_staged_index

class AutoGenerationError(RuntimeError):
    pass


def _hash(path: Path) -> str:
    digest=hashlib.sha256()
    with path.open("rb") as stream:
        for part in iter(lambda:stream.read(1024*1024),b""):
            digest.update(part)
    return digest.hexdigest()


def _forbid_reparse(path: Path) -> None:
    if path.is_symlink() or (
        hasattr(path,"is_junction") and path.is_junction()
    ):
        raise AutoGenerationError("reparse point prohibited in immutable generation")


def _tree_hashes(folder: Path) -> dict[str,str]:
    result={}
    _forbid_reparse(folder)
    for item in sorted(folder.rglob("*")):
        _forbid_reparse(item)
        if item.is_file() and item.name != ".lock":
            result[item.relative_to(folder).as_posix()]=_hash(item)
        elif not item.is_dir() and not item.is_file():
            raise AutoGenerationError("unexpected file type in generation")
    return result


def validate_reviewed_auto_generation(queue_path: Path,job_id: str) -> dict:
    """Independent job, source, SQLite, FTS, manifest, Qdrant checks."""
    job=get_job(queue_path,job_id)
    if job is None or job["state"]!="READY_FOR_REVIEW" or not job["approved"]:
        raise AutoGenerationError("only fully reviewed and validated jobs may be prepared")
    reviewed=read_reviewed_sources(queue_path,job_id)
    current=revalidate_auto_index_preview({
        "schema_version":1,"project_id":job["project_id"],
        "source_root":job["source_root"],"scope":job["requested_scope"],
        "review_sha256":reviewed["review_sha256"],
        "sources":reviewed["sources"],
    })
    vectors=inventory_auto_vectors(queue_path,job_id)
    if not vectors["complete"]:
        raise AutoGenerationError("vectors not complete")
    stage=Path(vectors["stage"])
    progress=json.loads((stage/"progress.json").read_text(encoding="utf-8"))
    if (progress.get("published") is not False
            or progress.get("state")!="INDEXING_NOT_PUBLISHED"
            or progress.get("last_batch_result")!="COMPLETE"
            or progress.get("source_revision")!=reviewed["review_sha256"]
            or progress.get("total_vectors_done")!=vectors["chunks"]):
        raise AutoGenerationError("stage progress receipt not ready")
    if (job["chunk_count"]!=vectors["chunks"]
            or job["file_count"]!=len(reviewed["sources"])
            or job["text_vectors_done"]!=vectors["text_done"]
            or job["code_vectors_done"]!=vectors["code_done"]):
        raise AutoGenerationError("SQLite queue counts do not match Qdrant")
    from rag.runtime.auto_index_staging import stage_directory
    if stage.resolve()!=stage_directory(queue_path,job_id).resolve():
        raise AutoGenerationError("unexpected staging path")
    report=validate_staged_index(stage,job["project_id"])
    if (report["documents"]!=len(reviewed["sources"])
            or report["chunks"]!=vectors["chunks"]
            or report["text_vectors"]!=vectors["text_done"]
            or report["code_vectors"]!=vectors["code_done"]):
        raise AutoGenerationError("stage validator drift")
    manifest=load_index_manifest(stage/"rag-index-manifest.json")
    by_path={entry.path:entry for entry in manifest.entries}
    if len(by_path)!=len(manifest.entries) or len(by_path)!=len(reviewed["sources"]):
        raise AutoGenerationError("manifest does not match source receipt")
    with closing(sqlite3.connect(
        f"{(stage/'rag_index.sqlite3').as_uri()}?mode=ro",uri=True,
    )) as cn:
        if cn.execute("PRAGMA integrity_check").fetchone()[0]!="ok":
            raise AutoGenerationError("SQLite integrity failure")
        fts=cn.execute("SELECT count(*) FROM rag_chunks_fts").fetchone()[0]
        if fts!=vectors["chunks"]:
            raise AutoGenerationError("FTS drift")
        for source in reviewed["sources"]:
            entry=by_path.get(source["path"])
            db=cn.execute(
                "SELECT sha256 FROM rag_documents WHERE project_id=? AND path=?",
                (job["project_id"],source["path"]),
            ).fetchone()
            from rag.chunking.provenance import source_sha256
            raw=(Path(job["source_root"])/source["path"]).read_bytes()
            expected_source_sha=source_sha256(raw.decode("utf-8",errors="replace"))
            if (entry is None or entry.sha256!=expected_source_sha
                    or db is None or db[0]!=expected_source_sha
                    or source["sha256"]!=hashlib.sha256(raw).hexdigest()):
                raise AutoGenerationError("document sha or manifest diverged")
            chunks=tuple(row[0] for row in cn.execute(
                "SELECT chunk_id FROM rag_chunks WHERE project_id=? AND path=? "
                "ORDER BY ordinal",(job["project_id"],source["path"]),
            ))
            if entry.chunk_ids!=chunks:
                raise AutoGenerationError("manifest chunk ids diverged")
    return {
        "job_id":job_id,"project_id":job["project_id"],
        "source_revision":current["review_sha256"],
        "stage":str(stage),"sources":len(reviewed["sources"]),
        "chunks":vectors["chunks"],"text_vectors":vectors["text_done"],
        "code_vectors":vectors["code_done"],
        "canary_ready":True,"public_generation_changed":False,
    }


def _paths(queue_path: Path,job_id: str,project_id: str) -> tuple[Path,Path]:
    from rag.runtime.auto_index_queue import _canonical_queue_path
    auto=_canonical_queue_path(queue_path).parent.parent
    parent=auto/"projects"/project_id
    return (parent/"generations"/("auto_"+job_id),
            parent/"snapshots"/("source_"+job_id))


def prepare_verified_auto_generation(
    queue_path: Path,job_id: str, *,
    operator_approved: bool=False,prepare_enabled: bool=False,
) -> dict:
    if operator_approved is not True or prepare_enabled is not True:
        raise PermissionError("explicit generation preparation approval required")
    report=validate_reviewed_auto_generation(queue_path,job_id)
    job=get_job(queue_path,job_id)
    generation,snapshot=_paths(queue_path,job_id,job["project_id"])
    for parent in (generation.parent,snapshot.parent):
        for ancestor in (parent,parent.parent,parent.parent.parent):
            _forbid_reparse(ancestor)
        parent.mkdir(parents=True,exist_ok=True)
    # Never overwrite a previous candidate or snapshot; this is deliberately
    # fail-closed if a prior attempt was interrupted.
    if generation.exists() or snapshot.exists():
        raise AutoGenerationError("immutable generation already exists; inspect before retry")
    source_tmp=snapshot.with_name(snapshot.name+".copying")
    generation_tmp=generation.with_name(generation.name+".copying")
    if source_tmp.exists() or generation_tmp.exists():
        raise AutoGenerationError("interrupted preparation requires manual audit")
    stage=Path(report["stage"])
    source=Path(job["source_root"]).resolve(strict=True)
    reviewed=read_reviewed_sources(queue_path,job_id)
    source_tmp.mkdir()
    try:
        for item in reviewed["sources"]:
            if _source_hash(source,item["path"])!=item["sha256"]:
                raise AutoGenerationError("source changed during preparation")
            origin=(source/item["path"]).resolve(strict=True)
            if not origin.is_relative_to(source) or not origin.is_file():
                raise AutoGenerationError("source path escaped pinned tree")
            destination=source_tmp/item["path"]
            destination.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(origin,destination)
            if _hash(destination)!=item["sha256"]:
                raise AutoGenerationError("source copy failed verification")
        # The models have completed; no Qdrant client may still be open.
        shutil.copytree(stage,generation_tmp,ignore=shutil.ignore_patterns(".lock"))
        expected_hashes=_tree_hashes(stage)
        if _tree_hashes(generation_tmp)!=expected_hashes:
            raise AutoGenerationError("candidate differs from staged generation")
        # Revalidate source review after copying. If any source changed during
        # the copy, do not make the immutable candidate available.
        validate_reviewed_auto_generation(queue_path,job_id)
        metadata={
            "schema_version":1,"state":"VERIFIED_NOT_REGISTERED",
            "project_id":job["project_id"],"job_id":job_id,
            "source_revision":report["source_revision"],
            "source_snapshot":str(snapshot),
            "generation":generation.name,
            "counts":{k:report[k] for k in ("sources","chunks","text_vectors","code_vectors")},
            "artifact_sha256":expected_hashes,
            "created_at":datetime.now(timezone.utc).isoformat(),
            "public_pointer_updated":False,"published_publicly":False,
        }
        (generation_tmp/"auto-generation-receipt.json").write_text(
            json.dumps(metadata,indent=2,sort_keys=True)+"\n",encoding="utf-8"
        )
        os.replace(source_tmp,snapshot)
        os.replace(generation_tmp,generation)
        return {
            "generation":str(generation),"source_snapshot":str(snapshot),
            "job_id":job_id,"project_id":job["project_id"],
            "source_revision":report["source_revision"],
            "counts":metadata["counts"],
            "public_pointer_updated":False,"catalog_updated":False,
        }
    except BaseException:
        # We can safely remove only unfinished folders; completed version
        # directories are deliberately preserved for manual recovery.
        for temp in (source_tmp,generation_tmp):
            if temp.exists():
                shutil.rmtree(temp)
        raise


def verify_prepared_auto_generation(queue_path: Path,job_id: str) -> dict:
    job=get_job(queue_path,job_id)
    if job is None:
        raise AutoGenerationError("job missing")
    generation,snapshot=_paths(queue_path,job_id,job["project_id"])
    for path in (generation,snapshot):
        if not path.is_dir():
            raise AutoGenerationError("prepared generation or source snapshot missing")
        _forbid_reparse(path)
    receipt=json.loads(
        (generation/"auto-generation-receipt.json").read_text(encoding="utf-8")
    )
    if (receipt.get("job_id")!=job_id
            or receipt.get("project_id")!=job["project_id"]
            or receipt.get("source_snapshot")!=str(snapshot)
            or receipt.get("state")!="VERIFIED_NOT_REGISTERED"
            or receipt.get("public_pointer_updated") is not False):
        raise AutoGenerationError("prepared generation receipt invalid")
    if _tree_hashes(generation)!={
        **receipt["artifact_sha256"],
        "auto-generation-receipt.json":_hash(generation/"auto-generation-receipt.json"),
    }:
        raise AutoGenerationError("prepared generation changed")
    reviewed=read_reviewed_sources(queue_path,job_id)
    for source in reviewed["sources"]:
        pinned=snapshot/source["path"]
        _forbid_reparse(pinned)
        if not pinned.resolve(strict=True).is_relative_to(snapshot.resolve()):
            raise AutoGenerationError("snapshot file escaped the pinned root")
        if _hash(pinned)!=source["sha256"]:
            raise AutoGenerationError("pinned source snapshot changed")
    validated=validate_staged_index(generation,job["project_id"])
    if validated["chunks"]!=receipt["counts"]["chunks"]:
        raise AutoGenerationError("verified generation vector counts changed")
    return {
        "project_id":job["project_id"],"job_id":job_id,
        "generation":str(generation),"source_snapshot":str(snapshot),
        "source_revision":receipt["source_revision"],
        "counts":receipt["counts"],
        "sqlite_sha256":_hash(generation/"rag_index.sqlite3"),
        "manifest_sha256":_hash(generation/"rag-index-manifest.json"),
        "verified":True,"public_pointer_updated":False,
    }
