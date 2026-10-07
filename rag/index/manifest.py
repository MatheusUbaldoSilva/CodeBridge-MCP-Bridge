"""Persistent incremental-index manifest for RAG-012-A."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json
from pathlib import Path, PurePosixPath
import tempfile
from typing import Iterable, Optional, Tuple

from .vector_namespace import require_project_namespace


MANIFEST_SCHEMA_VERSION = 1
DEFAULT_MANIFEST_FILENAME = "rag-index-manifest.json"


class ManifestError(RuntimeError):
    pass


class ManifestIndexKind(str, Enum):
    TEXT = "TEXT"
    CODE = "CODE"


def _canonical_relative_path(path: str) -> str:
    if not isinstance(path, str) or not path.strip():
        raise ValueError("path must be a non-empty string")
    raw = path.strip().replace("\\", "/")
    while raw.startswith("./"):
        raw = raw[2:]
    candidate = PurePosixPath(raw)
    if candidate.is_absolute():
        raise ValueError("manifest path must be relative")
    parts = tuple(part for part in candidate.parts if part != ".")
    if not parts or any(part == ".." for part in parts):
        raise ValueError("manifest path must stay inside the project")
    return "/".join(parts)


def _require_sha256(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("sha256 must be a string")
    normalized = value.lower()
    if len(normalized) != 64:
        raise ValueError("sha256 must contain 64 hexadecimal characters")
    try:
        int(normalized, 16)
    except ValueError as exc:
        raise ValueError(
            "sha256 must contain 64 hexadecimal characters"
        ) from exc
    return normalized


def _require_chunk_ids(values: Iterable[str]) -> Tuple[str, ...]:
    result = tuple(values)
    if any(not isinstance(item, str) or not item.strip() for item in result):
        raise ValueError("chunk_ids must contain non-empty strings")
    if len(set(result)) != len(result):
        raise ValueError("chunk_ids must be unique")
    return result


@dataclass(frozen=True)
class ManifestEntry:
    project_id: str
    index_kind: ManifestIndexKind
    path: str
    size: int
    mtime_ns: int
    sha256: str
    chunk_ids: Tuple[str, ...]
    model_version: str

    def __post_init__(self) -> None:
        require_project_namespace(self.project_id)
        if not isinstance(self.index_kind, ManifestIndexKind):
            raise ValueError("index_kind must be ManifestIndexKind")
        canonical_path = _canonical_relative_path(self.path)
        object.__setattr__(self, "path", canonical_path)

        if not isinstance(self.size, int) or self.size < 0:
            raise ValueError("size must be an integer >= 0")
        if not isinstance(self.mtime_ns, int) or self.mtime_ns < 0:
            raise ValueError("mtime_ns must be an integer >= 0")

        object.__setattr__(self, "sha256", _require_sha256(self.sha256))
        object.__setattr__(
            self,
            "chunk_ids",
            _require_chunk_ids(self.chunk_ids),
        )

        if not isinstance(self.model_version, str) or not self.model_version.strip():
            raise ValueError("model_version must be non-empty")
        object.__setattr__(
            self,
            "model_version",
            self.model_version.strip(),
        )

    @property
    def key(self) -> str:
        return manifest_entry_key(
            self.project_id,
            self.index_kind,
            self.path,
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "project_id": self.project_id,
            "index_kind": self.index_kind.value,
            "path": self.path,
            "size": self.size,
            "mtime_ns": self.mtime_ns,
            "sha256": self.sha256,
            "chunk_ids": list(self.chunk_ids),
            "model_version": self.model_version,
        }

    @classmethod
    def from_dict(cls, data: object) -> "ManifestEntry":
        if not isinstance(data, dict):
            raise ManifestError("manifest entry must be an object")
        try:
            return cls(
                project_id=data["project_id"],
                index_kind=ManifestIndexKind(data["index_kind"]),
                path=data["path"],
                size=data["size"],
                mtime_ns=data["mtime_ns"],
                sha256=data["sha256"],
                chunk_ids=tuple(data["chunk_ids"]),
                model_version=data["model_version"],
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ManifestError(
                f"invalid manifest entry: {type(exc).__name__}: {exc}"
            ) from exc


@dataclass(frozen=True)
class IndexManifest:
    entries: Tuple[ManifestEntry, ...] = ()

    def __post_init__(self) -> None:
        normalized = tuple(self.entries)
        if any(not isinstance(item, ManifestEntry) for item in normalized):
            raise ValueError("entries must contain ManifestEntry values")
        keys = [item.key for item in normalized]
        if len(set(keys)) != len(keys):
            raise ValueError("manifest entry keys must be unique")
        object.__setattr__(
            self,
            "entries",
            tuple(sorted(normalized, key=lambda item: item.key)),
        )

    def get(
        self,
        project_id: str,
        index_kind: ManifestIndexKind,
        path: str,
    ) -> Optional[ManifestEntry]:
        key = manifest_entry_key(project_id, index_kind, path)
        for entry in self.entries:
            if entry.key == key:
                return entry
        return None

    def upsert(self, entry: ManifestEntry) -> "IndexManifest":
        if not isinstance(entry, ManifestEntry):
            raise ValueError("entry must be ManifestEntry")
        kept = [
            item
            for item in self.entries
            if item.key != entry.key
        ]
        kept.append(entry)
        return IndexManifest(entries=tuple(kept))

    def remove(
        self,
        project_id: str,
        index_kind: ManifestIndexKind,
        path: str,
    ) -> "IndexManifest":
        key = manifest_entry_key(project_id, index_kind, path)
        return IndexManifest(
            entries=tuple(
                item
                for item in self.entries
                if item.key != key
            )
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": MANIFEST_SCHEMA_VERSION,
            "entries": [
                item.to_dict()
                for item in self.entries
            ],
        }


def manifest_entry_key(
    project_id: str,
    index_kind: ManifestIndexKind,
    path: str,
) -> str:
    namespace = require_project_namespace(project_id)
    if not isinstance(index_kind, ManifestIndexKind):
        raise ValueError("index_kind must be ManifestIndexKind")
    canonical_path = _canonical_relative_path(path)
    raw = (
        f"v{MANIFEST_SCHEMA_VERSION}|"
        f"{namespace}|{index_kind.value}|{canonical_path}"
    )
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return f"manifest:{digest}"


def load_index_manifest(path: str | Path) -> IndexManifest:
    manifest_path = Path(path)
    if not manifest_path.exists():
        return IndexManifest()

    try:
        payload = json.loads(
            manifest_path.read_text(encoding="utf-8")
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ManifestError(
            f"failed to load manifest {manifest_path}: "
            f"{type(exc).__name__}: {exc}"
        ) from exc

    if not isinstance(payload, dict):
        raise ManifestError("manifest root must be an object")

    version = payload.get("schema_version")
    if version != MANIFEST_SCHEMA_VERSION:
        raise ManifestError(
            f"unsupported manifest schema_version {version!r}"
        )

    raw_entries = payload.get("entries")
    if not isinstance(raw_entries, list):
        raise ManifestError("manifest entries must be a list")

    entries = tuple(
        ManifestEntry.from_dict(item)
        for item in raw_entries
    )

    try:
        return IndexManifest(entries=entries)
    except ValueError as exc:
        raise ManifestError(str(exc)) from exc


def save_index_manifest(
    path: str | Path,
    manifest: IndexManifest,
) -> None:
    if not isinstance(manifest, IndexManifest):
        raise ValueError("manifest must be IndexManifest")

    manifest_path = Path(path)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    payload = json.dumps(
        manifest.to_dict(),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ) + "\n"

    temporary_name: Optional[str] = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=str(manifest_path.parent),
            prefix=f".{manifest_path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            handle.write(payload)
            handle.flush()
            temporary_name = handle.name

        Path(temporary_name).replace(manifest_path)
    except OSError as exc:
        if temporary_name is not None:
            try:
                Path(temporary_name).unlink(missing_ok=True)
            except OSError:
                pass
        raise ManifestError(
            f"failed to save manifest {manifest_path}: "
            f"{type(exc).__name__}: {exc}"
        ) from exc
