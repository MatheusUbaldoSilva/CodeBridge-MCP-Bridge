"""Fluxo unico da aba Indexar: escolher -> conferir -> indexar -> ativar.

Camada fina sobre a fila/worker existentes (auto_index_*) e sobre a juncao
RAG-ADD-01. Cada passo continua exigindo a confirmacao propria dele; aqui so
se escolhe o caminho certo (projeto novo = canario; projeto existente =
juntar) e se lembra qual trabalho ja foi ativado, para o Desfazer.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from rag.runtime.auto_index_queue import default_queue_path, list_jobs

DONE_STATES = ("CANCELLED", "FAILED")
LEDGER_NAME = "index-activations.json"


def _queue() -> Path:
    return default_queue_path()


def _ledger_path() -> Path:
    return Path(_queue()).parent / LEDGER_NAME


def _ledger() -> dict:
    try:
        data = json.loads(_ledger_path().read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _save_ledger(data: dict) -> None:
    path = _ledger_path()
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temp, path)


def current_job(project_id: str) -> dict | None:
    """Most recent job of the project that still needs attention."""
    activated = _ledger()
    jobs = [j for j in list_jobs(_queue())
            if j.get("project_id") == project_id and j.get("state") not in DONE_STATES
            and j.get("job_id") not in activated]
    if not jobs:
        return None
    key = lambda j: float(j.get("updated_at_epoch") or j.get("created_at_epoch") or 0)
    return sorted(jobs, key=key)[-1]


def preview(project_id: str, root: str, paths: list[str] | None = None) -> dict:
    from rag.runtime.auto_index_api import auto_preview
    return auto_preview(project_id, root, paths=paths or None)


def queue(project_id: str, root: str, paths: list[str] | None, review_sha256: str) -> dict:
    from rag.runtime.auto_index_api import auto_approve
    return auto_approve(project_id, root, paths=paths or None, confirmed_digest=review_sha256,
                        operator_approved=True, execute=True,
                        confirmation="RAG_AUTO_QUEUE:" + project_id + ":" + review_sha256)


def start(job_id: str) -> dict:
    from rag.runtime.auto_index_launch import launch_approved_auto_job
    return launch_approved_auto_job(_queue(), job_id, execute=True, operator_approved=True,
                                    confirmation="RAG_AUTO_LAUNCH:" + job_id)


def status(job_id: str) -> dict:
    from rag.runtime.auto_index_api import auto_status
    return auto_status(job_id=job_id)


def control(job_id: str, action: str) -> dict:
    from rag.runtime.auto_index_controls import request_auto_index_control
    return request_auto_index_control(_queue(), job_id, action,
                                      operator_requested=True, control_enabled=True)


def _ensure_prepared(project_id: str, job_id: str) -> dict:
    from rag.runtime.auto_index_generation import AutoGenerationError, verify_prepared_auto_generation
    try:
        return verify_prepared_auto_generation(_queue(), job_id)
    except AutoGenerationError as exc:
        if "missing" not in str(exc):
            raise
    from rag.runtime.auto_index_promotion import prepare_auto_candidate
    prepare_auto_candidate(job_id, execute=True, operator_approved=True,
                           confirmation="RAG_AUTO_PREPARE:" + project_id + ":" + job_id)
    return verify_prepared_auto_generation(_queue(), job_id)


def activation_review(project_id: str, job_id: str) -> dict:
    """Prepare the finished job (if needed) and describe the activation."""
    from rag.runtime.isolated_project_index import resolve_isolated_project
    prepared = _ensure_prepared(project_id, job_id)
    if resolve_isolated_project(project_id) is not None:
        from rag.runtime.knowledge_merge_operational import preview_knowledge_merge
        return {"mode": "MERGE", **preview_knowledge_merge(project_id, job_id)}
    counts = prepared.get("counts") or {}
    return {"mode": "NEW", "project_id": project_id, "job_id": job_id,
            "documents_after": counts.get("sources"), "chunks_after": counts.get("chunks"),
            "added_paths": [], "replaced_paths": [], "review_sha256": prepared["sqlite_sha256"]}


def activate(project_id: str, job_id: str, review: dict, confirmation: str, *, progress=None) -> dict:
    if confirmation != project_id:
        raise PermissionError("confirmacao nao confere com o nome do projeto")
    if review.get("mode") == "MERGE":
        from rag.runtime.knowledge_merge_operational import execute_knowledge_merge
        result = execute_knowledge_merge(project_id, job_id, review["review_sha256"],
                                         confirmation, progress=progress)
        entry = {"mode": "MERGE", "transaction": result["transaction"]}
    else:
        from rag.runtime.auto_index_promotion import enable_auto_canary
        if callable(progress):
            progress("Registrando o projeto novo")
        result = enable_auto_canary(job_id, execute=True, operator_approved=True,
                                    confirmation="RAG_AUTO_CANARY:" + project_id + ":" + job_id)
        entry = {"mode": "NEW"}
    ledger = _ledger()
    ledger[job_id] = {**entry, "project_id": project_id,
                      "activated_at": datetime.now(timezone.utc).isoformat()}
    _save_ledger(ledger)
    return {**result, "mode": entry["mode"]}


def pending_undo(project_id: str) -> dict | None:
    """The latest activation of this project that can still be undone."""
    from rag.runtime.isolated_project_index import catalog_path
    from rag.runtime.knowledge_deletion_operational import pending_removal
    for job_id, entry in sorted(_ledger().items(), key=lambda kv: kv[1].get("activated_at", ""),
                                reverse=True):
        if entry.get("project_id") != project_id:
            continue
        if entry.get("mode") == "MERGE":
            pending = pending_removal(project_id)
            if pending and pending.get("transaction") == entry.get("transaction"):
                return {"job_id": job_id, **entry}
        else:
            journal = catalog_path().parent / f"auto-canary-{job_id}.journal.json"
            try:
                if json.loads(journal.read_text(encoding="utf-8")).get("state") == "CANARY_ACTIVE":
                    return {"job_id": job_id, **entry}
            except (OSError, ValueError):
                pass
        return None
    return None


def undo(project_id: str) -> dict:
    pending = pending_undo(project_id)
    if pending is None:
        raise RuntimeError("nao ha ativacao recente para desfazer")
    job_id = pending["job_id"]
    if pending["mode"] == "MERGE":
        from rag.runtime.knowledge_deletion_operational import rollback_knowledge_removal
        result = rollback_knowledge_removal(pending["transaction"])
    else:
        from rag.runtime.auto_index_promotion import disable_auto_canary
        result = disable_auto_canary(job_id, execute=True, operator_approved=True,
                                     confirmation="RAG_AUTO_CANARY_ROLLBACK:" + job_id)
    ledger = _ledger()
    ledger.pop(job_id, None)
    _save_ledger(ledger)
    return {**result, "mode": pending["mode"], "job_id": job_id}