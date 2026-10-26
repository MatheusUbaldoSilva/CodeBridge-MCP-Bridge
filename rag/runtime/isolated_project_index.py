"""Local, explicit, read-only project-index routing for CodeBridge RAG.

A separately audited candidate is registered by a local configuration file.
The public CodeBridge generation pointer is never read as a candidate switch and
never modified by this module. No ingestion or publication actions are exposed.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
import re
from typing import Any

PROJECT_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_-]{1,63}$")
CATALOG_FILENAME = "project-indexes.json"


class IsolatedProjectUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class IsolatedProjectIndex:
    project_id: str
    generation: str
    source_root: Path
    sqlite: Path
    qdrant: Path
    manifest: Path
    python_executable: Path
    source_revision: str


def catalog_path() -> Path:
    local = os.environ.get("LOCALAPPDATA")
    if not local:
        raise IsolatedProjectUnavailable("LOCALAPPDATA is required")
    return Path(local) / "CodeBridge" / "rag" / CATALOG_FILENAME


def _workspace_root() -> Path:
    home = os.environ.get("USERPROFILE")
    if not home:
        raise IsolatedProjectUnavailable("USERPROFILE is required")
    return (Path(home) / "CodeBridge-RAG-Workspace").resolve(strict=True)


def _contained_path(raw: Any, anchor: Path, *, directory: bool = True) -> Path:
    if not isinstance(raw, str) or not raw or not Path(raw).is_absolute():
        raise IsolatedProjectUnavailable("project index requires absolute local paths")
    path = Path(raw).resolve(strict=True)
    if not path.is_relative_to(anchor) or path == anchor:
        raise IsolatedProjectUnavailable("project index path outside approved workspace")
    if directory and not path.is_dir():
        raise IsolatedProjectUnavailable("project index directory unavailable")
    return path


def _fingerprint(path: Path) -> str:
    with path.open("rb") as src:
        digest = sha256()
        while buffer := src.read(1024 * 1024):
            digest.update(buffer)
        return digest.hexdigest()


def _entries() -> dict[str, Any]:
    path = catalog_path()
    if not path.is_file():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8-sig"))
    if raw.get("schema_version") != 1 or not isinstance(raw.get("projects"), dict):
        raise IsolatedProjectUnavailable("unsupported project index catalog")
    return raw["projects"]


def resolve_isolated_project(project_id: str) -> IsolatedProjectIndex | None:
    """Fail closed on malformed enabled registrations; ignore unregistered IDs."""
    projects = _entries()
    row = projects.get(project_id)
    if row is None:
        return None
    if not isinstance(row, dict):
        raise IsolatedProjectUnavailable("malformed project registration")
    if row.get("enabled") is not True:
        return None
    if not isinstance(project_id, str) or not PROJECT_ID_PATTERN.fullmatch(project_id):
        raise IsolatedProjectUnavailable("invalid project namespace")
    if row.get("project_id") != project_id or row.get("source_revision") is None:
        raise IsolatedProjectUnavailable("project ID or revision mismatch")
    workspace = _workspace_root()
    generation = _contained_path(row.get("generation_directory"), workspace)
    source_root = _contained_path(row.get("source_directory"), workspace)
    # Never let a registered candidate point at the public state directory.
    if generation.parent.name != "generations":
        raise IsolatedProjectUnavailable("candidate must be within a generations directory")
    revision = row["source_revision"]
    is_auto=row.get("index_family")=="RAG_AUTO_03"
    revision_pattern=r"[0-9a-f]{64}" if is_auto else r"[0-9a-f]{40}"
    if not isinstance(revision, str) or not re.fullmatch(revision_pattern, revision):
        raise IsolatedProjectUnavailable("invalid pinned source revision")
    if is_auto:
        job_id=row.get("job_id")
        if not isinstance(job_id,str) or not re.fullmatch(r"[0-9a-f]{32}",job_id):
            raise IsolatedProjectUnavailable("invalid automatic generation job")
        if generation.name!="auto_"+job_id:
            raise IsolatedProjectUnavailable("automatic generation name mismatch")
        if source_root.name!="source_"+job_id or source_root.parent.name!="snapshots":
            raise IsolatedProjectUnavailable("automatic source snapshot mismatch")
        receipt_file=generation/"auto-generation-receipt.json"
        expected_receipt=row.get("generation_receipt_sha256")
        if (not isinstance(expected_receipt,str)
                or not re.fullmatch(r"[0-9a-f]{64}",expected_receipt)
                or not receipt_file.is_file()
                or _fingerprint(receipt_file)!=expected_receipt):
            raise IsolatedProjectUnavailable("automatic generation receipt changed")
        receipt=json.loads(receipt_file.read_text(encoding="utf-8"))
        if (receipt.get("job_id")!=job_id
                or receipt.get("project_id")!=project_id
                or receipt.get("source_snapshot")!=str(source_root)
                or receipt.get("source_revision")!=revision
                or receipt.get("state")!="VERIFIED_NOT_REGISTERED"
                or receipt.get("published_publicly") is not False):
            raise IsolatedProjectUnavailable("automatic generation receipt invalid")
    python = Path(row.get("python_executable", ""))
    if not python.is_absolute() or not python.is_file():
        raise IsolatedProjectUnavailable("approved project Python is missing")
    database = generation / "rag_index.sqlite3"
    manifest = generation / "rag-index-manifest.json"
    vectors = generation / "qdrant"
    progress_file = generation / "progress.json"
    if not database.is_file() or not manifest.is_file() or not vectors.is_dir() or not progress_file.is_file():
        raise IsolatedProjectUnavailable("candidate generation is incomplete")
    for candidate in (database,manifest,vectors,progress_file):
        if not candidate.resolve(strict=True).is_relative_to(generation):
            raise IsolatedProjectUnavailable("candidate files cannot redirect outside generation")
    progress = json.loads(progress_file.read_text(encoding="utf-8"))
    if (progress.get("project_id") != project_id
            or progress.get("source_revision") != revision
            or progress.get("state") != "INDEXING_NOT_PUBLISHED"
            or progress.get("total_vectors_done") != progress.get("expected_chunks")
            or progress.get("last_batch_result") != ("COMPLETE" if is_auto else "PASS")
            or (is_auto and progress.get("job_id")!=row.get("job_id"))
            or progress.get("published") is not False):
        raise IsolatedProjectUnavailable("candidate index has not passed final staging validation")
    # A full index check was completed before registration. Compare the two
    # anchor artifacts on every read so replacing the candidate fails closed.
    for key,path in (("sqlite_sha256",database),("manifest_sha256",manifest)):
        expected = row.get(key)
        if not isinstance(expected, str) or not re.fullmatch(r"[0-9a-f]{64}",expected):
            raise IsolatedProjectUnavailable("candidate fingerprint not configured")
        if _fingerprint(path) != expected:
            raise IsolatedProjectUnavailable("candidate fingerprint changed")
    return IsolatedProjectIndex(
        project_id=project_id,
        generation=generation.name,
        source_root=source_root,
        sqlite=database,
        qdrant=vectors,
        manifest=manifest,
        python_executable=python,
        source_revision=revision,
    )


def list_isolated_project_indexes() -> list[dict[str, Any]]:
    """Expose an optional status summary; never start models or open Qdrant."""
    result = []
    for name in sorted(_entries()):
        row = _entries()[name]
        if row.get("enabled") is not True:
            result.append({"project_id":name,"state":"DISABLED"})
            continue
        try:
            index = resolve_isolated_project(name)
            import sqlite3
            from contextlib import closing
            with closing(sqlite3.connect(f"{index.sqlite.as_uri()}?mode=ro",uri=True)) as db:
                documents=db.execute(
                    "SELECT count(*) FROM rag_documents WHERE project_id=?",(name,)
                ).fetchone()[0]
                chunks=db.execute(
                    "SELECT count(*) FROM rag_chunks WHERE project_id=?",(name,)
                ).fetchone()[0]
            result.append({
                "project_id":name,
                "state":"ISOLATED_READ_ONLY",
                "generation":index.generation,
                "source_revision":index.source_revision,
                "document_count":documents,
                "chunk_count":chunks,
                "public_generation_unchanged":True,
            })
        except (OSError, KeyError, ValueError, TypeError, IsolatedProjectUnavailable) as exc:
            result.append({"project_id":name,"state":"UNAVAILABLE","reason":type(exc).__name__})
    return result
