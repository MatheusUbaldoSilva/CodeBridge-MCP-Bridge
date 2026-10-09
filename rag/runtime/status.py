"""Read-only RAG status snapshot for MCP exposure — RAG-013-A.

Importing this module does not open databases load models or create storage.
All filesystem and process inspection happens only when build_rag_status is called.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import sqlite3
from typing import Any, Optional, Tuple

from rag.index.manifest import (
    DEFAULT_MANIFEST_FILENAME,
    IndexManifest,
    ManifestIndexKind,
    load_index_manifest,
)
from rag.index.qdrant_local import resolve_qdrant_local_path
from rag.index.sqlite_schema import DEFAULT_DATABASE_FILENAME
from rag.index.vector_backend_policy import (
    SELECTED_VECTOR_BACKEND,
    SELECTED_VECTOR_PACKAGE,
    SELECTED_VECTOR_PACKAGE_VERSION,
)
from rag.models.artifact_install import resolve_selected_model_path
from rag.models.backend_policy import (
    SELECTED_TEXT_BACKEND,
    TEXT_MODEL_REVISION,
)
from rag.models.code_artifact_install import (
    resolve_selected_code_model_path,
)
from rag.models.code_backend_policy import (
    CODE_MODEL_REVISION,
    SELECTED_CODE_BACKEND,
)


DEFAULT_RAG_STATE_SUBDIR = Path("CodeBridge") / "rag"


@dataclass(frozen=True)
class ModelRuntimeStatus:
    model: str
    revision: str
    artifact_path: str
    installed: bool
    loaded: Optional[bool]
    runtime_state: str
    execution_mode: str
    gpu_preferred: bool
    cpu_fallback_required: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "model": self.model,
            "revision": self.revision,
            "artifact_path": self.artifact_path,
            "installed": self.installed,
            "loaded": self.loaded,
            "runtime_state": self.runtime_state,
            "execution_mode": self.execution_mode,
            "gpu_preferred": self.gpu_preferred,
            "cpu_fallback_required": self.cpu_fallback_required,
        }


@dataclass(frozen=True)
class RagStatusSnapshot:
    index: dict[str, Any]
    projects: Tuple[dict[str, Any], ...]
    models: dict[str, dict[str, Any]]
    backend: dict[str, Any]
    last_indexed_at: Optional[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": dict(self.index),
            "projects": [dict(item) for item in self.projects],
            "models": {
                key: dict(value)
                for key, value in self.models.items()
            },
            "backend": dict(self.backend),
            "last_indexed_at": self.last_indexed_at,
        }


def resolve_rag_state_directory(
    *,
    local_app_data: Optional[Path] = None,
) -> Path:
    root = local_app_data
    if root is None:
        value = os.environ.get("LOCALAPPDATA")
        if not value:
            raise RuntimeError(
                "LOCALAPPDATA is required to resolve RAG state paths"
            )
        root = Path(value)
    return Path(root) / DEFAULT_RAG_STATE_SUBDIR


def resolve_rag_manifest_path(
    *,
    local_app_data: Optional[Path] = None,
) -> Path:
    return (
        resolve_rag_state_directory(local_app_data=local_app_data)
        / DEFAULT_MANIFEST_FILENAME
    )


def resolve_rag_sqlite_path(
    *,
    local_app_data: Optional[Path] = None,
) -> Path:
    return (
        resolve_rag_state_directory(local_app_data=local_app_data)
        / DEFAULT_DATABASE_FILENAME
    )


def _load_manifest_if_present(path: Path) -> IndexManifest:
    if not path.is_file():
        return IndexManifest()
    return load_index_manifest(path)


def _read_index_state(
    database_path: Path,
) -> tuple[tuple[dict[str, Any], ...], Optional[str]]:
    if not database_path.is_file():
        return (), None

    uri = f"{database_path.resolve().as_uri()}?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    try:
        rows = connection.execute(
            """
            SELECT
                project_id,
                state,
                source_revision,
                last_indexed_at,
                document_count,
                chunk_count,
                last_error_type,
                last_error_message
            FROM rag_index_state
            ORDER BY project_id
            """
        ).fetchall()
    except sqlite3.Error:
        return (), None
    finally:
        connection.close()

    projects = tuple(
        {
            "project_id": str(row[0]),
            "index_state": str(row[1]),
            "source_revision": row[2],
            "last_indexed_at": row[3],
            "document_count": int(row[4] or 0),
            "chunk_count": int(row[5] or 0),
            "last_error_type": row[6],
            "last_error_message": row[7],
        }
        for row in rows
    )
    timestamps = [
        str(row[3])
        for row in rows
        if row[3] is not None and str(row[3]).strip()
    ]
    return projects, max(timestamps) if timestamps else None


def _manifest_project_summaries(
    manifest: IndexManifest,
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for entry in manifest.entries:
        project = result.setdefault(
            entry.project_id,
            {
                "project_id": entry.project_id,
                "manifest_entries": 0,
                "text_entries": 0,
                "code_entries": 0,
                "text_model_versions": set(),
                "code_model_versions": set(),
            },
        )
        project["manifest_entries"] += 1
        if entry.index_kind is ManifestIndexKind.TEXT:
            project["text_entries"] += 1
            project["text_model_versions"].add(entry.model_version)
        else:
            project["code_entries"] += 1
            project["code_model_versions"].add(entry.model_version)

    for project in result.values():
        project["text_model_versions"] = sorted(
            project["text_model_versions"]
        )
        project["code_model_versions"] = sorted(
            project["code_model_versions"]
        )
    return result


def _merge_project_state(
    manifest: IndexManifest,
    sqlite_projects: tuple[dict[str, Any], ...],
) -> Tuple[dict[str, Any], ...]:
    merged = _manifest_project_summaries(manifest)

    for state in sqlite_projects:
        project_id = str(state["project_id"])
        target = merged.setdefault(
            project_id,
            {
                "project_id": project_id,
                "manifest_entries": 0,
                "text_entries": 0,
                "code_entries": 0,
                "text_model_versions": [],
                "code_model_versions": [],
            },
        )
        target.update(state)

    return tuple(
        merged[key]
        for key in sorted(merged)
    )


def _probe_model_process(model_filename: str) -> tuple[Optional[bool], str]:
    try:
        import psutil
    except Exception:
        return None, "UNKNOWN"

    for process in psutil.process_iter(["name", "cmdline"]):
        try:
            command = " ".join(process.info.get("cmdline") or [])
            name = str(process.info.get("name") or "").lower()
        except (psutil.Error, OSError):
            continue

        if "llama-server" not in name and "llama-server" not in command.lower():
            continue
        if model_filename.lower() not in command.lower():
            continue

        lowered = command.lower()
        if "--device none" in lowered or "-ngl 0" in lowered:
            return True, "CPU"
        if "cuda" in lowered or "-ngl 99" in lowered:
            return True, "GPU"
        return True, "UNKNOWN"

    return False, "UNLOADED"


def _model_statuses(
    *,
    local_app_data: Optional[Path] = None,
) -> dict[str, dict[str, Any]]:
    text_path = resolve_selected_model_path(
        local_app_data=local_app_data
    )
    code_path = resolve_selected_code_model_path(
        local_app_data=local_app_data
    )

    text_loaded, text_mode = _probe_model_process(
        SELECTED_TEXT_BACKEND.artifact_pin.filename or ""
    )
    code_loaded, code_mode = _probe_model_process(
        SELECTED_CODE_BACKEND.artifact_pin.filename or ""
    )

    def state(loaded: Optional[bool]) -> str:
        if loaded is True:
            return "LOADED"
        if loaded is False:
            return "UNLOADED"
        return "UNKNOWN"

    text = ModelRuntimeStatus(
        model=SELECTED_TEXT_BACKEND.model_family,
        revision=TEXT_MODEL_REVISION,
        artifact_path=str(text_path),
        installed=text_path.is_file(),
        loaded=text_loaded,
        runtime_state=state(text_loaded),
        execution_mode=text_mode,
        gpu_preferred=SELECTED_TEXT_BACKEND.gpu_preferred,
        cpu_fallback_required=SELECTED_TEXT_BACKEND.cpu_fallback_required,
    )
    code = ModelRuntimeStatus(
        model=SELECTED_CODE_BACKEND.model_family,
        revision=CODE_MODEL_REVISION,
        artifact_path=str(code_path),
        installed=code_path.is_file(),
        loaded=code_loaded,
        runtime_state=state(code_loaded),
        execution_mode=code_mode,
        gpu_preferred=SELECTED_CODE_BACKEND.gpu_preferred,
        cpu_fallback_required=SELECTED_CODE_BACKEND.cpu_fallback_required,
    )
    return {
        "text": text.to_dict(),
        "code": code.to_dict(),
    }


def build_rag_status(
    *,
    local_app_data: Optional[Path] = None,
) -> RagStatusSnapshot:
    manifest_path = resolve_rag_manifest_path(
        local_app_data=local_app_data
    )
    sqlite_path = resolve_rag_sqlite_path(
        local_app_data=local_app_data
    )
    qdrant_base = None
    if local_app_data is not None:
        qdrant_base = (
            Path(local_app_data)
            / "CodeBridge"
            / "rag"
            / "qdrant"
        )
    qdrant_path = resolve_qdrant_local_path(qdrant_base)

    manifest = _load_manifest_if_present(manifest_path)
    sqlite_projects, last_indexed_at = _read_index_state(sqlite_path)
    projects = _merge_project_state(
        manifest,
        sqlite_projects,
    )

    if any(
        project.get("index_state") == "ERROR"
        for project in projects
    ):
        overall_state = "ERROR"
    elif any(
        project.get("index_state") == "INDEXING"
        for project in projects
    ):
        overall_state = "INDEXING"
    elif any(
        project.get("index_state") == "STALE"
        for project in projects
    ):
        overall_state = "STALE"
    elif manifest.entries or projects:
        # READY requires all three durable stores and a positive SQLite project
        # state, not only the existence of a manifest or incomplete write.
        ready_projects = {
            item["project_id"] for item in sqlite_projects
            if item.get("index_state") == "READY"
        }
        declared = {entry.project_id for entry in manifest.entries}
        if (
            manifest_path.is_file()
            and sqlite_path.is_file()
            and qdrant_path.is_dir()
            and declared
            and declared.issubset(ready_projects)
        ):
            overall_state = "READY"
        else:
            overall_state = "STALE"
    else:
        overall_state = "EMPTY"

    return RagStatusSnapshot(
        index={
            "state": overall_state,
            "manifest_path": str(manifest_path),
            "manifest_exists": manifest_path.is_file(),
            "manifest_entries": len(manifest.entries),
            "sqlite_path": str(sqlite_path),
            "sqlite_exists": sqlite_path.is_file(),
            "qdrant_path": str(qdrant_path),
            "qdrant_exists": qdrant_path.exists(),
        },
        projects=projects,
        models=_model_statuses(
            local_app_data=local_app_data
        ),
        backend={
            "vector": SELECTED_VECTOR_BACKEND.value,
            "package": SELECTED_VECTOR_PACKAGE,
            "package_version": SELECTED_VECTOR_PACKAGE_VERSION,
            "mode": "PERSISTED_LOCAL",
            "external_server_required": False,
        },
        last_indexed_at=last_indexed_at,
    )
