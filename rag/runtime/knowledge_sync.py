"""Atualizacao do conhecimento a partir de uma pasta vigiada (RAG-SYNC-01).

Tres modos por projeto: AUTO (atualiza sozinho), MANUAL (avisa e espera o
clique) e OFF. A atualizacao repete os passos da aba Indexar - conferir,
indexar na fila e juntar ao projeto - e tira do conhecimento os arquivos que
sumiram da pasta, tudo numa unica troca de geracao que pode ser desfeita.
So vale para projetos com indice proprio.
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import time
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

MODES = ("AUTO", "OFF", "MANUAL")
SETTINGS_NAME = "knowledge-sync.json"
SKIP_DIRS = frozenset({".git", ".hg", ".svn", "node_modules", "__pycache__", ".venv", "venv",
                       ".mypy_cache", ".pytest_cache", ".ruff_cache", ".idea", ".vs"})
TERMINAL = ("READY_FOR_REVIEW", "FAILED", "CANCELLED")


class KnowledgeSyncError(RuntimeError):
    pass


def _flow():
    from rag.runtime import knowledge_index_flow
    return knowledge_index_flow


def _settings_path() -> Path:
    from rag.runtime.auto_index_queue import default_queue_path
    return Path(default_queue_path()).parent / SETTINGS_NAME


def _read_all(path=None) -> dict:
    try:
        data = json.loads(Path(path or _settings_path()).read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _write_all(data: dict, path=None) -> None:
    target = Path(path or _settings_path())
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_name(target.name + ".tmp")
    temp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temp, target)


def settings(project_id: str, path=None) -> dict:
    row = (_read_all(path).get("projects") or {}).get(project_id) or {}
    mode = row.get("mode") if row.get("mode") in MODES else "OFF"
    return {"mode": mode, "folder": row.get("folder") or None, "last": row.get("last") or None}


def update_settings(project_id: str, path=None, **changes) -> dict:
    if "mode" in changes and changes["mode"] not in MODES:
        raise KnowledgeSyncError("modo de atualizacao invalido")
    data = _read_all(path)
    projects = data.setdefault("projects", {})
    row = {**settings(project_id, path), **changes}
    projects[project_id] = row
    _write_all(data, path)
    return row


def supported(project_id: str) -> bool:
    try:
        from rag.runtime.isolated_project_index import resolve_isolated_project
        return resolve_isolated_project(project_id) is not None
    except Exception:
        return False


def indexed_hashes(project_id: str) -> dict:
    from rag.runtime.isolated_project_index import resolve_isolated_project
    index = resolve_isolated_project(project_id)
    if index is None:
        raise KnowledgeSyncError("projeto sem indice proprio")
    with closing(sqlite3.connect(Path(index.sqlite).as_uri() + "?mode=ro", uri=True, timeout=5)) as con:
        return dict(con.execute("SELECT path, sha256 FROM rag_documents WHERE project_id=?", (project_id,)))


def fingerprint(folder) -> str:
    """Barato: nome, tamanho e data de cada arquivo. So serve para saber se vale comparar."""
    root = Path(folder)
    digest = hashlib.sha256()
    for current, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        base = Path(current)
        for name in sorted(filenames):
            try:
                info = (base / name).stat()
            except OSError:
                continue
            relative = (base / name).relative_to(root).as_posix()
            digest.update(f"{relative}|{info.st_size}|{info.st_mtime_ns}\n".encode("utf-8"))
    return digest.hexdigest()


def compute_changes(project_id: str, folder, *, flow=None, hashes=indexed_hashes) -> dict:
    flow = flow or _flow()
    if not folder or not Path(folder).is_dir():
        raise KnowledgeSyncError("pasta vigiada nao encontrada: " + str(folder))
    review = flow.preview(project_id, str(folder))
    current = {s["path"]: s["sha256"] for s in review.get("sources") or []}
    indexed = hashes(project_id)
    added = sorted(set(current) - set(indexed))
    removed = sorted(set(indexed) - set(current))
    changed = sorted(p for p in set(current) & set(indexed) if current[p] != indexed[p])
    return {"project_id": project_id, "folder": str(folder), "added": added, "changed": changed,
            "removed": removed, "total": len(added) + len(changed) + len(removed),
            "checked_at": time.time()}

def _remove_only(project_id: str, removed: list[str], step) -> dict:
    from rag.runtime.knowledge_deletion_operational import execute_knowledge_removal, pending_removal
    from rag.runtime.knowledge_deletion_preview import preview_knowledge_removal
    step(f"Tirando {len(removed)} arquivo(s) apagado(s) da pasta")
    review = preview_knowledge_removal(project_id, removed)
    result = execute_knowledge_removal(project_id, removed, review["review_sha256"], project_id,
                                       progress=step, origin="AUTO")
    transaction = result.get("transaction") or (pending_removal(project_id) or {}).get("transaction")
    return {"mode": "REMOVE", "transaction": transaction, "documents": result.get("documents")}


def _index_and_merge(project_id: str, folder: str, paths: list[str], removed: list[str], *,
                     flow, step, cancelled, sleep, poll) -> dict:
    step(f"Conferindo {len(paths)} arquivo(s)")
    review = flow.preview(project_id, folder, paths)
    found = sorted(s["path"] for s in review.get("sources") or [])
    if found != sorted(paths):
        raise KnowledgeSyncError("a pasta mudou durante a conferencia; a proxima verificacao tenta de novo")
    queued = flow.queue(project_id, folder, paths, review["review_sha256"])
    job_id = queued["job_id"]
    flow.start(job_id)
    while True:
        if callable(cancelled) and cancelled():
            flow.control(job_id, "CANCEL")
            raise KnowledgeSyncError("atualizacao cancelada")
        state = (flow.status(job_id) or {}).get("state")
        if state in TERMINAL:
            break
        step(f"Indexando {len(paths)} arquivo(s)")
        sleep(poll)
    if state != "READY_FOR_REVIEW":
        raise KnowledgeSyncError(f"indexacao terminou como {state}")
    step("Preparando a juncao")
    activation = flow.activation_review(project_id, job_id, removed or None)
    if activation.get("mode") != "MERGE":
        raise KnowledgeSyncError("o projeto precisa ter indice proprio para ser atualizado")
    result = flow.activate(project_id, job_id, activation, project_id, progress=step)
    return {"mode": "MERGE", "job_id": job_id, "transaction": result.get("transaction"),
            "documents": result.get("documents")}


def apply_changes(project_id: str, changes: dict, *, flow=None, progress=None, cancelled=None,
                  sleep=time.sleep, poll=3.0, path=None) -> dict:
    """Leva para o conhecimento o que mudou na pasta (novos, alterados e apagados)."""
    flow = flow or _flow()
    step = progress if callable(progress) else (lambda message: None)
    folder = changes["folder"]
    paths = sorted(set(changes["added"]) | set(changes["changed"]))
    removed = sorted(changes["removed"])
    if not paths and not removed:
        return {"state": "UP_TO_DATE"}
    if paths:
        result = _index_and_merge(project_id, folder, paths, removed, flow=flow, step=step,
                                  cancelled=cancelled, sleep=sleep, poll=poll)
    else:
        result = _remove_only(project_id, removed, step)
    last = {**result, "added": len(changes["added"]), "changed": len(changes["changed"]),
            "removed": len(removed), "at": datetime.now(timezone.utc).isoformat()}
    update_settings(project_id, path=path, last=last)
    return {"state": "SYNCED", **last}


def can_undo(project_id: str, path=None) -> bool:
    last = settings(project_id, path).get("last") or {}
    if not last.get("transaction"):
        return False
    try:
        from rag.runtime.knowledge_deletion_operational import pending_removal
        pending = pending_removal(project_id)
    except Exception:
        return False
    return bool(pending) and pending.get("transaction") == last["transaction"]


def undo_last(project_id: str, *, flow=None, path=None) -> dict:
    last = settings(project_id, path).get("last") or {}
    if not can_undo(project_id, path):
        raise KnowledgeSyncError("nao ha atualizacao recente para desfazer")
    if last.get("mode") == "MERGE":
        result = (flow or _flow()).undo(project_id)
    else:
        from rag.runtime.knowledge_deletion_operational import rollback_knowledge_removal
        result = rollback_knowledge_removal(last["transaction"])
    update_settings(project_id, path=path, last=None)
    return result