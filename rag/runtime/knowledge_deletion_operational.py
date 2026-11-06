"""RAG-DEL CLOSE-04: operational removal of INDEXED knowledge.

Builds a new verified RAG_DEL_01 generation for a private isolated project
without the selected files, then switches that project's catalog entry with
the same journaled swap/rollback used by the laboratory tests:

  preview -> staged SQLite/FTS/manifest -> surviving vectors copied and
  checkpointed -> candidate validated -> review bundle -> generation receipt
  -> journaled catalog switch -> post-switch verification (auto rollback).

Source files are never modified or deleted. The public project is refused.
The RAG-AUTO canary interlock still blocks any switch while an AUTO
rollback journal pins the shared catalog.
"""
from __future__ import annotations

from contextlib import closing
from pathlib import Path
import json
import re
import shutil
import sqlite3
import threading
import uuid

from rag.index.qdrant_local import (
    close_qdrant_local, ensure_vector_collections, open_qdrant_local,
)
from rag.runtime.isolated_project_index import (
    _workspace_root, catalog_path, resolve_isolated_project,
)
from rag.runtime.knowledge_deletion_assemble_lab import _assemble_deletion_generation
from rag.runtime.knowledge_deletion_bundle import prepare_deletion_review_bundle
from rag.runtime.knowledge_deletion_checkpoint import checkpoint_survivor_batch
from rag.runtime.knowledge_deletion_evidence import seal_deletion_candidate
from rag.runtime.knowledge_deletion_preview import preview_knowledge_removal
from rag.runtime.knowledge_deletion_stage import stage_removal_sqlite_manifest
from rag.runtime.knowledge_deletion_swap_lab import (
    _transactional_commit, _transactional_rollback, _transactional_swap,
)
from rag.runtime.knowledge_deletion_vector_copy import copy_survivor_batch
from rag.runtime.knowledge_deletion_vectors import plan_surviving_vector_batches
from rag.runtime.knowledge_deletion_verify import validate_deletion_candidate

PUBLIC_PROJECT = "codebridge"
POINTER_NAME = "active-generation.json"
_HEX32 = re.compile(r"[0-9a-f]{32}\Z")
_REVISION = re.compile(r"[0-9a-f]{40}(?:[0-9a-f]{24})?\Z")
_LOCK = threading.RLock()


class KnowledgeRemovalError(RuntimeError):
    pass


def _operational_paths() -> tuple[Path, Path]:
    catalog = catalog_path()
    pointer = catalog.parent / POINTER_NAME
    for path in (catalog, pointer):
        if (not path.is_absolute() or not path.is_file() or path.is_symlink()
                or (hasattr(path, "is_junction") and path.is_junction())):
            raise KnowledgeRemovalError("catalogo ou ponteiro publico indisponivel: " + str(path))
    return catalog.resolve(strict=True), pointer.resolve(strict=True)


def _journals(catalog: Path) -> list[dict]:
    records = []
    for journal in sorted(catalog.parent.glob("rag-del-*.journal.json")):
        try:
            records.append(json.loads(journal.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            continue
    return records


def pending_removal(project_id: str | None = None) -> dict | None:
    """The ACTIVE (still undoable) removal, if any."""
    catalog, _ = _operational_paths()
    for record in _journals(catalog):
        if record.get("state") == "ACTIVE" and (
                project_id is None or record.get("project_id") == project_id):
            return {"transaction": record.get("transaction"),
                    "project_id": record.get("project_id")}
    return None


def _commit_active(catalog: Path) -> list[str]:
    committed = []
    for record in _journals(catalog):
        if record.get("state") == "ACTIVE":
            _transactional_commit(record["transaction"], catalog)
            committed.append(record["transaction"])
    return committed


def _remaining_selected(sqlite_path: Path, project_id: str, selected: list[str]) -> int:
    with closing(sqlite3.connect(Path(sqlite_path).as_uri() + "?mode=ro", uri=True)) as con:
        marks = ",".join("?" for _ in selected)
        return con.execute(
            "SELECT COUNT(*) FROM rag_documents WHERE project_id=? AND path IN (" + marks + ")",
            (project_id, *selected),
        ).fetchone()[0]


def execute_knowledge_removal(project_id: str, selected_paths: list[str],
                              expected_review_sha256: str, confirmation: str,
                              *, progress=None) -> dict:
    """Remove the selected files' indexed knowledge from a private project."""
    def step(message: str):
        if callable(progress):
            progress(message)

    if not isinstance(project_id, str) or not project_id or project_id == PUBLIC_PROJECT:
        raise KnowledgeRemovalError("exclusao do indice publico nao e permitida")
    if confirmation != project_id:
        raise KnowledgeRemovalError("confirmacao nao confere com o nome do projeto")
    if (not isinstance(selected_paths, list) or not selected_paths
            or len(set(selected_paths)) != len(selected_paths)):
        raise KnowledgeRemovalError("selecione arquivos unicos")
    selected = sorted(selected_paths)

    with _LOCK:
        catalog, pointer = _operational_paths()
        step("Conferindo a previa")
        preview = preview_knowledge_removal(project_id, selected)
        if preview["review_sha256"] != expected_review_sha256:
            raise KnowledgeRemovalError("a previa mudou desde a revisao; confira de novo")
        if preview["chunks_to_preserve"] <= 0:
            raise KnowledgeRemovalError("ao menos um conhecimento precisa permanecer no projeto")
        index = resolve_isolated_project(project_id)
        if index is None or index.generation != preview["generation"]:
            raise KnowledgeRemovalError("a geracao do projeto mudou; confira de novo")
        if not _REVISION.fullmatch(index.source_revision or ""):
            raise KnowledgeRemovalError(
                "revisao do projeto invalida para a exclusao")

        transaction_id = uuid.uuid4().hex
        generations = Path(index.sqlite).parent.parent
        stage = generations / ("del_" + transaction_id)
        snapshots = generations.parent / "snapshots"
        snapshot = snapshots / ("source_" + transaction_id)
        switched = False
        try:
            step("Gerando o indice sem os arquivos selecionados")
            stage_removal_sqlite_manifest(project_id, selected, expected_review_sha256, stage)
            step("Planejando os vetores que permanecem")
            plan = plan_surviving_vector_batches(index.manifest, preview)
            batch_ids = []
            source = destination = None
            try:
                source = open_qdrant_local(Path(index.qdrant))
                destination = open_qdrant_local(stage / "qdrant")
                ensure_vector_collections(destination)
                total = len(plan["batches"])
                for number, batch in enumerate(plan["batches"]):
                    step(f"Copiando vetores ({number + 1}/{total})")
                    copied = copy_survivor_batch(
                        source, destination, plan, number,
                        verified_source=True, isolated_staging=True,
                        operator_approved=True,
                    )
                    batch_id = uuid.uuid4().hex
                    checkpoint_survivor_batch(
                        destination, stage, batch_id, copied, batch,
                        plan["sources"], operator_approved=True,
                    )
                    batch_ids.append(batch_id)
                step("Validando a nova geracao")
                verification = validate_deletion_candidate(stage, plan, destination, batch_ids)
            finally:
                close_qdrant_local(destination)
                close_qdrant_local(source)
            seal_deletion_candidate(stage, preview, verification, operator_approved=True)
            bundle = prepare_deletion_review_bundle(stage)
            step("Registrando o recibo da geracao")
            snapshots.mkdir(parents=False, exist_ok=True)
            shutil.copytree(Path(index.source_root), snapshot, symlinks=False)
            candidate = _assemble_deletion_generation(
                stage, snapshot, project_id, index.source_revision,
                transaction_id, preview, bundle, allowed_root=_workspace_root(),
            )
            candidate["python_executable"] = str(index.python_executable)
            committed = _commit_active(catalog)
            step("Ativando a nova geracao do projeto")
            swap = _transactional_swap(
                catalog, pointer, project_id, index.source_revision, candidate,
            )
            switched = True
        except Exception:
            if not switched:
                for path in (stage, snapshot):
                    shutil.rmtree(path, ignore_errors=True)
            raise

        step("Conferindo o projeto apos a troca")
        try:
            current = resolve_isolated_project(project_id)
            if current is None or current.generation != stage.name:
                raise KnowledgeRemovalError("projeto nao resolve a nova geracao")
            if _remaining_selected(current.sqlite, project_id, selected) != 0:
                raise KnowledgeRemovalError("arquivos selecionados ainda presentes")
        except Exception as exc:
            _transactional_rollback(swap["transaction"], catalog, pointer)
            raise KnowledgeRemovalError(
                "verificacao apos a troca falhou; exclusao desfeita: " + str(exc)) from exc

        return {
            "state": "REMOVED",
            "transaction": swap["transaction"],
            "project_id": project_id,
            "removed_files": selected,
            "documents_removed": preview["documents_to_remove"],
            "chunks_removed": preview["chunks_to_remove"],
            "documents_preserved": preview["documents_to_preserve"],
            "previous_generation": index.generation,
            "generation": stage.name,
            "committed_previous": committed,
            "source_files_modified": False,
        }


def rollback_knowledge_removal(transaction: str) -> dict:
    if not isinstance(transaction, str) or not _HEX32.fullmatch(transaction):
        raise KnowledgeRemovalError("transacao invalida")
    with _LOCK:
        catalog, pointer = _operational_paths()
        return _transactional_rollback(transaction, catalog, pointer)