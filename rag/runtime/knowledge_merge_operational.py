"""RAG-ADD-01: juntar arquivos recem-indexados a um projeto privado existente.

Monta uma geracao nova = conhecimento atual + arquivos de um trabalho de
indexacao ja preparado (arquivo com o mesmo caminho e substituido), confere
SQLite/FTS, manifesto e cada vetor relido, grava um recibo fixado no catalogo
e troca o projeto com o mesmo swap journaled da exclusao. Desfazer usa
rollback_knowledge_removal. Fontes nunca sao alteradas; o indice publico e
recusado.
"""
from __future__ import annotations

from contextlib import closing
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import json
import re
import shutil
import sqlite3
import uuid

from rag.index.manifest import IndexManifest, load_index_manifest, save_index_manifest
from rag.index.qdrant_local import (
    CODE_VECTOR_COLLECTION, TEXT_VECTOR_COLLECTION,
    close_qdrant_local, ensure_vector_collections, open_qdrant_local,
)
from rag.index.vector_ids import deterministic_vector_point_id
from rag.runtime.isolated_project_index import resolve_isolated_project
from rag.runtime.knowledge_deletion_operational import (
    PUBLIC_PROJECT, _LOCK, _commit_active, _operational_paths, _reconcile_auto_canaries,
)
from rag.runtime.knowledge_deletion_swap_lab import _transactional_rollback, _transactional_swap
from rag.runtime.knowledge_deletion_vector_copy import _same_vector

FAMILY = "RAG_ADD_01"
RECEIPT_NAME = "merge-generation-receipt.json"
BATCH = 256
_HEX32 = re.compile(r"[0-9a-f]{32}\Z")
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")
_TABLES = ("rag_documents", "rag_chunks", "rag_chunk_symbols")


class KnowledgeMergeError(RuntimeError):
    pass


def _sha_file(path: Path) -> str:
    digest = sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _kind(entry) -> str:
    return str(getattr(entry.index_kind, "value", entry.index_kind)).upper()


def _collection(entry) -> str:
    return CODE_VECTOR_COLLECTION if _kind(entry) == "CODE" else TEXT_VECTOR_COLLECTION


def _verified_job_generation(job_id: str) -> dict:
    """Prepared, re-verified job generation (raises if anything changed)."""
    from rag.runtime.auto_index_generation import verify_prepared_auto_generation
    from rag.runtime.auto_index_queue import default_queue_path
    return verify_prepared_auto_generation(default_queue_path(), job_id)


def _plan(project_id: str, job_id: str):
    if not isinstance(project_id, str) or not project_id or project_id == PUBLIC_PROJECT:
        raise KnowledgeMergeError("o indice publico nao pode receber arquivos por aqui")
    if not isinstance(job_id, str) or not _HEX32.fullmatch(job_id):
        raise KnowledgeMergeError("trabalho de indexacao invalido")
    index = resolve_isolated_project(project_id)
    if index is None:
        raise KnowledgeMergeError("projeto ainda nao existe; use a ativacao de projeto novo")
    job = _verified_job_generation(job_id)
    if job.get("project_id") != project_id or job.get("job_id") != job_id:
        raise KnowledgeMergeError("o trabalho pertence a outro projeto")
    job_generation = Path(job["generation"])
    base = load_index_manifest(index.manifest)
    new = load_index_manifest(job_generation / "rag-index-manifest.json")
    new_entries = list(new.entries)
    if not new_entries:
        raise KnowledgeMergeError("o trabalho nao tem arquivos indexados")
    if any(e.project_id != project_id for e in new_entries):
        raise KnowledgeMergeError("o trabalho contem arquivos de outro projeto")
    new_paths = sorted({e.path for e in new_entries})
    if len(new_paths) != len(new_entries):
        raise KnowledgeMergeError("o trabalho repete caminhos")
    models = {}
    for entry in base.entries:
        models.setdefault(_kind(entry), set()).add(entry.model_version)
    for entry in new_entries:
        known = models.get(_kind(entry))
        if known and entry.model_version not in known:
            raise KnowledgeMergeError(
                "modelo de embeddings diferente do projeto (" + _kind(entry) + "); reindexe o projeto inteiro")
    chosen = set(new_paths)
    keep_entries = [e for e in base.entries if e.path not in chosen]
    base_paths = {e.path for e in base.entries}
    payload = {
        "project_id": project_id, "job_id": job_id,
        "base_generation": index.generation, "base_source_revision": index.source_revision,
        "base_sqlite_sha256": _sha_file(Path(index.sqlite)),
        "job_sqlite_sha256": job["sqlite_sha256"], "job_manifest_sha256": job["manifest_sha256"],
        "added_paths": sorted(chosen - base_paths),
        "replaced_paths": sorted(chosen & base_paths),
        "documents_before": len(base.entries),
        "documents_after": len(keep_entries) + len(new_entries),
        "chunks_before": sum(len(e.chunk_ids) for e in base.entries),
        "chunks_after": (sum(len(e.chunk_ids) for e in keep_entries)
                         + sum(len(e.chunk_ids) for e in new_entries)),
        "chunks_added": sum(len(e.chunk_ids) for e in new_entries),
    }
    digest = sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
    review = {**payload, "state": "READ_ONLY_REVIEW", "execution_enabled": False,
              "review_sha256": digest}
    return review, index, job, keep_entries, new_entries


def preview_knowledge_merge(project_id: str, job_id: str) -> dict:
    """Read-only summary of what joining the job to the project would do."""
    return _plan(project_id, job_id)[0]


def _columns(con, schema: str, table: str) -> list[str]:
    return [row[1] for row in con.execute(f"PRAGMA {schema}.table_info({table})")]


def _merge_sqlite(base: Path, job: Path, target: Path, project_id: str,
                  new_paths: list[str], revision: str) -> tuple[int, int]:
    with closing(sqlite3.connect(Path(base).as_uri() + "?mode=ro", uri=True)) as src, \
            closing(sqlite3.connect(str(target))) as dst:
        src.backup(dst)
    with closing(sqlite3.connect(Path(target).as_uri(), uri=True)) as con:
        con.execute("ATTACH DATABASE ? AS job", (Path(job).as_uri() + "?mode=ro",))
        for table in _TABLES:
            if _columns(con, "main", table) != _columns(con, "job", table):
                raise KnowledgeMergeError("esquema do banco do trabalho difere do projeto: " + table)
        owners = {row[0] for row in con.execute(
            "SELECT project_id FROM job.rag_documents UNION SELECT project_id FROM job.rag_chunks")}
        if owners != {project_id}:
            raise KnowledgeMergeError("banco do trabalho contem outro projeto")
        job_paths = sorted(row[0] for row in con.execute("SELECT path FROM job.rag_documents"))
        if job_paths != sorted(new_paths):
            raise KnowledgeMergeError("banco do trabalho nao confere com o manifesto")
        con.execute("CREATE TEMP TABLE merge_paths(path TEXT PRIMARY KEY)")
        con.executemany("INSERT INTO merge_paths(path) VALUES(?)", [(p,) for p in new_paths])
        con.execute(
            "DELETE FROM rag_chunk_symbols WHERE chunk_id IN (SELECT chunk_id FROM rag_chunks "
            "WHERE project_id=? AND path IN (SELECT path FROM merge_paths))", (project_id,))
        con.execute("DELETE FROM rag_chunks WHERE project_id=? AND path IN (SELECT path FROM merge_paths)",
                    (project_id,))
        con.execute("DELETE FROM rag_documents WHERE project_id=? AND path IN (SELECT path FROM merge_paths)",
                    (project_id,))
        for table in _TABLES:
            cols = ",".join(_columns(con, "main", table))
            con.execute(f"INSERT INTO main.{table}({cols}) SELECT {cols} FROM job.{table} ORDER BY rowid")
        documents = con.execute("SELECT COUNT(*) FROM rag_documents WHERE project_id=?", (project_id,)).fetchone()[0]
        chunks = con.execute("SELECT COUNT(*) FROM rag_chunks WHERE project_id=?", (project_id,)).fetchone()[0]
        con.execute("UPDATE rag_index_state SET source_revision=?, document_count=?, chunk_count=? "
                    "WHERE project_id=?", (revision, documents, chunks, project_id))
        con.commit()
        con.execute("DETACH DATABASE job")
        if con.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise KnowledgeMergeError("banco juntado falhou na verificacao de integridade")
        con.execute("INSERT INTO rag_chunks_fts(rag_chunks_fts) VALUES('integrity-check')")
        if con.execute("SELECT COUNT(*) FROM rag_chunks_fts").fetchone()[0] != chunks:
            raise KnowledgeMergeError("indice de texto (FTS) nao confere com os chunks")
        orphans = con.execute(
            "SELECT COUNT(*) FROM rag_chunks c LEFT JOIN rag_documents d ON d.document_id=c.document_id "
            "WHERE d.document_id IS NULL").fetchone()[0]
        if orphans:
            raise KnowledgeMergeError("chunks sem documento no banco juntado")
        con.commit()
    return documents, chunks


def _copy_batch(source, target, collection: str, ids: list[str]) -> int:
    from qdrant_client import models
    items = source.retrieve(collection_name=collection, ids=ids, with_payload=True, with_vectors=True)
    if {str(item.id) for item in items} != set(ids):
        raise KnowledgeMergeError("vetores ausentes na origem (" + collection + ")")
    target.upsert(collection, points=[models.PointStruct(
        id=str(item.id), vector=item.vector, payload=item.payload) for item in items], wait=True)
    back = {str(item.id): item for item in target.retrieve(
        collection_name=collection, ids=ids, with_payload=True, with_vectors=True)}
    for item in items:
        stored = back.get(str(item.id))
        if (stored is None or stored.payload != item.payload
                or not _same_vector(item.vector, stored.vector)):
            raise KnowledgeMergeError("vetor gravado difere do original; nova geracao descartada")
    return len(items)


def _merge_vectors(base_q: Path, job_q: Path, target_q: Path, project_id: str,
                   keep_entries, new_entries, step) -> dict:
    groups = []
    for label, entries in (("base", keep_entries), ("job", new_entries)):
        for collection in (TEXT_VECTOR_COLLECTION, CODE_VECTOR_COLLECTION):
            ids = [deterministic_vector_point_id(project_id, collection, cid)
                   for entry in entries if _collection(entry) == collection for cid in entry.chunk_ids]
            for start in range(0, len(ids), BATCH):
                groups.append((label, collection, ids[start:start + BATCH]))
    totals = {TEXT_VECTOR_COLLECTION: 0, CODE_VECTOR_COLLECTION: 0}
    base = job = target = None
    try:
        base = open_qdrant_local(Path(base_q))
        job = open_qdrant_local(Path(job_q))
        target = open_qdrant_local(Path(target_q))
        ensure_vector_collections(target)
        for number, (label, collection, ids) in enumerate(groups, 1):
            step(f"Copiando vetores ({number}/{len(groups)})")
            totals[collection] += _copy_batch(base if label == "base" else job, target, collection, ids)
        for collection, expected in totals.items():
            stored = target.count(collection_name=collection, exact=True).count
            if stored != expected:
                raise KnowledgeMergeError("contagem de vetores difere em " + collection)
    finally:
        for client in (target, job, base):
            if client is not None:
                close_qdrant_local(client)
    return totals


def _snapshot(base_root: Path, job_root: Path, snapshot: Path, new_paths: list[str]) -> None:
    temp = snapshot.with_name(snapshot.name + ".copying")
    shutil.copytree(base_root, temp, symlinks=False)
    job_root = Path(job_root).resolve(strict=True)
    for relative in new_paths:
        origin = (job_root / relative).resolve(strict=True)
        if not origin.is_relative_to(job_root) or not origin.is_file():
            raise KnowledgeMergeError("arquivo do trabalho fora da copia aprovada: " + relative)
        destination = temp / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(origin, destination)
        if _sha_file(destination) != _sha_file(origin):
            raise KnowledgeMergeError("copia da origem falhou: " + relative)
    temp.rename(snapshot)


def _paths_present(sqlite_path: Path, project_id: str, paths: list[str]) -> int:
    with closing(sqlite3.connect(Path(sqlite_path).as_uri() + "?mode=ro", uri=True)) as con:
        marks = ",".join("?" for _ in paths)
        return con.execute("SELECT COUNT(*) FROM rag_documents WHERE project_id=? AND path IN (" + marks + ")",
                           (project_id, *paths)).fetchone()[0]


def execute_knowledge_merge(project_id: str, job_id: str, expected_review_sha256: str,
                            confirmation: str, *, progress=None) -> dict:
    """Join the job's indexed files to the existing project (undoable)."""
    def step(message: str):
        if callable(progress):
            progress(message)

    if confirmation != project_id:
        raise KnowledgeMergeError("confirmacao nao confere com o nome do projeto")
    with _LOCK:
        catalog, pointer = _operational_paths()
        step("Conferindo a previa")
        review, index, job, keep_entries, new_entries = _plan(project_id, job_id)
        if review["review_sha256"] != expected_review_sha256:
            raise KnowledgeMergeError("a previa mudou desde a revisao; confira de novo")
        new_paths = sorted(e.path for e in new_entries)
        transaction = uuid.uuid4().hex
        revision = sha256(f"{FAMILY}|{index.source_revision}|{job['source_revision']}|{transaction}"
                          .encode("utf-8")).hexdigest()
        generations = Path(index.sqlite).parent.parent
        stage = generations / ("add_" + transaction)
        snapshots = generations.parent / "snapshots"
        snapshot = snapshots / ("source_" + transaction)
        job_generation = Path(job["generation"])
        switched = False
        try:
            stage.mkdir(parents=False)
            step("Juntando o banco de dados")
            documents, chunks = _merge_sqlite(index.sqlite, job_generation / "rag_index.sqlite3",
                                              stage / "rag_index.sqlite3", project_id, new_paths, revision)
            step("Juntando o manifesto")
            entries = sorted(list(keep_entries) + list(new_entries), key=lambda e: (e.path, _kind(e)))
            save_index_manifest(stage / "rag-index-manifest.json", IndexManifest(tuple(entries)))
            totals = _merge_vectors(index.qdrant, job_generation / "qdrant", stage / "qdrant",
                                    project_id, keep_entries, new_entries, step)
            vectors = sum(totals.values())
            if not (documents == review["documents_after"] and chunks == review["chunks_after"] == vectors):
                raise KnowledgeMergeError(
                    f"contagens nao conferem: documentos {documents}, chunks {chunks}, vetores {vectors}")
            text, code = totals[TEXT_VECTOR_COLLECTION], totals[CODE_VECTOR_COLLECTION]
            (stage / "progress.json").write_text(json.dumps({
                "project_id": project_id, "source_revision": revision, "transaction": transaction,
                "state": "INDEXING_NOT_PUBLISHED", "expected_chunks": chunks,
                "text_vectors_done": text, "code_vectors_done": code, "total_vectors_done": vectors,
                "text_vectors_expected": text, "code_vectors_expected": code,
                "last_batch_result": "COMPLETE", "published": False,
                "last_updated_at": datetime.now(timezone.utc).isoformat(),
            }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            step("Copiando os arquivos de origem")
            snapshots.mkdir(parents=False, exist_ok=True)
            _snapshot(Path(index.source_root), Path(job["source_snapshot"]), snapshot, new_paths)
            artifacts = {name: _sha_file(stage / name)
                         for name in ("rag_index.sqlite3", "rag-index-manifest.json", "progress.json")}
            receipt = stage / RECEIPT_NAME
            receipt.write_text(json.dumps({
                "schema_version": 1, "index_family": FAMILY, "state": "VERIFIED_NOT_REGISTERED",
                "project_id": project_id, "transaction": transaction, "source_revision": revision,
                "source_snapshot": str(snapshot.resolve()),
                "base_generation": index.generation, "base_source_revision": index.source_revision,
                "job_id": job_id, "job_generation": str(job_generation),
                "job_source_revision": job["source_revision"],
                "added_paths": review["added_paths"], "replaced_paths": review["replaced_paths"],
                "counts": {"documents": documents, "chunks": chunks, "text_vectors": text,
                           "code_vectors": code, "chunks_added": review["chunks_added"]},
                "artifact_sha256": artifacts, "published_publicly": False,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            candidate = {
                "enabled": True, "project_id": project_id, "index_family": FAMILY,
                "transaction": transaction, "job_id": job_id, "source_revision": revision,
                "generation_directory": str(stage.resolve()), "source_directory": str(snapshot.resolve()),
                "python_executable": str(index.python_executable),
                "sqlite_sha256": artifacts["rag_index.sqlite3"],
                "manifest_sha256": artifacts["rag-index-manifest.json"],
                "generation_receipt_sha256": _sha_file(receipt),
            }
            _reconcile_auto_canaries(catalog, pointer)
            committed = _commit_active(catalog)
            step("Ativando a nova geracao do projeto")
            swap = _transactional_swap(catalog, pointer, project_id, index.source_revision, candidate)
            switched = True
        except Exception:
            if not switched:
                for path in (stage, snapshot, snapshot.with_name(snapshot.name + ".copying")):
                    shutil.rmtree(path, ignore_errors=True)
            raise

        step("Conferindo o projeto apos a troca")
        try:
            current = resolve_isolated_project(project_id)
            if current is None or current.generation != stage.name:
                raise KnowledgeMergeError("projeto nao resolve a nova geracao")
            if _paths_present(current.sqlite, project_id, new_paths) != len(new_paths):
                raise KnowledgeMergeError("arquivos novos ausentes depois da troca")
        except Exception as exc:
            _transactional_rollback(swap["transaction"], catalog, pointer)
            raise KnowledgeMergeError("verificacao apos a troca falhou; alteracao desfeita: " + str(exc)) from exc

        return {
            "state": "MERGED", "transaction": swap["transaction"], "project_id": project_id,
            "job_id": job_id, "added_files": review["added_paths"],
            "replaced_files": review["replaced_paths"],
            "documents": documents, "chunks": chunks, "chunks_added": review["chunks_added"],
            "previous_generation": index.generation, "generation": stage.name,
            "committed_previous": committed, "source_files_modified": False,
        }


def verify_merge_generation(row: dict, project_id: str, generation: Path,
                            source_root: Path, revision: str) -> None:
    """Fail-closed check used by resolve_isolated_project for RAG_ADD_01 rows."""
    transaction = row.get("transaction")
    if not isinstance(transaction, str) or not _HEX32.fullmatch(transaction):
        raise KnowledgeMergeError("transacao invalida")
    if (generation.name != "add_" + transaction or source_root.name != "source_" + transaction
            or source_root.parent.name != "snapshots"):
        raise KnowledgeMergeError("nome da geracao ou da copia nao confere")
    receipt_file = generation / RECEIPT_NAME
    expected = row.get("generation_receipt_sha256")
    if (not isinstance(expected, str) or not _HEX64.fullmatch(expected)
            or not receipt_file.is_file() or _sha_file(receipt_file) != expected):
        raise KnowledgeMergeError("recibo da geracao mudou")
    receipt = json.loads(receipt_file.read_text(encoding="utf-8"))
    if (receipt.get("index_family") != FAMILY or receipt.get("state") != "VERIFIED_NOT_REGISTERED"
            or receipt.get("project_id") != project_id or receipt.get("transaction") != transaction
            or receipt.get("source_revision") != revision
            or Path(str(receipt.get("source_snapshot"))).resolve() != Path(source_root).resolve()
            or receipt.get("published_publicly") is not False):
        raise KnowledgeMergeError("recibo da geracao invalido")
    artifacts = receipt.get("artifact_sha256") or {}
    if (artifacts.get("rag_index.sqlite3") != row.get("sqlite_sha256")
            or artifacts.get("rag-index-manifest.json") != row.get("manifest_sha256")
            or not (generation / "progress.json").is_file()
            or _sha_file(generation / "progress.json") != artifacts.get("progress.json")):
        raise KnowledgeMergeError("artefatos da geracao nao conferem com o recibo")