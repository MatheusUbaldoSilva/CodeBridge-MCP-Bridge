"""Incremental file snapshot helpers — RAG-012-B."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
from pathlib import Path, PurePosixPath
from typing import Callable, Iterable, Tuple

from .manifest import IndexManifest, ManifestEntry, ManifestIndexKind


@dataclass(frozen=True)
class SourceFileSnapshot:
    path: str
    size: int
    mtime_ns: int
    sha256: str

    def __post_init__(self) -> None:
        if not isinstance(self.path, str) or not self.path.strip():
            raise ValueError("path must be non-empty")
        if not isinstance(self.size, int) or self.size < 0:
            raise ValueError("size must be >= 0")
        if not isinstance(self.mtime_ns, int) or self.mtime_ns < 0:
            raise ValueError("mtime_ns must be >= 0")
        if (
            not isinstance(self.sha256, str)
            or len(self.sha256) != 64
        ):
            raise ValueError("sha256 must contain 64 hexadecimal characters")
        try:
            int(self.sha256, 16)
        except ValueError as exc:
            raise ValueError(
                "sha256 must contain 64 hexadecimal characters"
            ) from exc


def _canonical_relative_path(path: str) -> str:
    if not isinstance(path, str) or not path.strip():
        raise ValueError("path must be non-empty")
    raw = path.strip().replace("\\", "/")
    while raw.startswith("./"):
        raw = raw[2:]
    candidate = PurePosixPath(raw)
    if candidate.is_absolute():
        raise ValueError("path must be relative")
    parts = tuple(part for part in candidate.parts if part != ".")
    if not parts or any(part == ".." for part in parts):
        raise ValueError("path must stay inside project_root")
    return "/".join(parts)


def capture_source_file_snapshot(
    project_root: str | Path,
    path: str,
) -> SourceFileSnapshot:
    root = Path(project_root).expanduser().resolve()
    relative = _canonical_relative_path(path)
    source = (root / relative).resolve()
    try:
        source.relative_to(root)
    except ValueError as exc:
        raise ValueError("path must stay inside project_root") from exc

    if not source.is_file():
        raise FileNotFoundError(str(source))

    stat = source.stat()
    digest = hashlib.sha256(source.read_bytes()).hexdigest()

    return SourceFileSnapshot(
        path=relative,
        size=int(stat.st_size),
        mtime_ns=int(stat.st_mtime_ns),
        sha256=digest,
    )


def manifest_entry_content_unchanged(
    entry: ManifestEntry,
    snapshot: SourceFileSnapshot,
) -> bool:
    if not isinstance(entry, ManifestEntry):
        raise ValueError("entry must be ManifestEntry")
    if not isinstance(snapshot, SourceFileSnapshot):
        raise ValueError("snapshot must be SourceFileSnapshot")
    if entry.path != snapshot.path:
        raise ValueError("entry and snapshot paths must match")

    return entry.sha256 == snapshot.sha256


def should_skip_file_reprocessing(
    entry: ManifestEntry,
    snapshot: SourceFileSnapshot,
) -> bool:
    """Return True only when the authoritative content SHA is unchanged."""

    return manifest_entry_content_unchanged(entry, snapshot)


@dataclass(frozen=True)
class ChangedFileReindexOutcome:
    manifest: IndexManifest
    entry: ManifestEntry
    retired_chunk_ids: Tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.manifest, IndexManifest):
            raise ValueError("manifest must be IndexManifest")
        if not isinstance(self.entry, ManifestEntry):
            raise ValueError("entry must be ManifestEntry")
        if any(
            not isinstance(item, str) or not item
            for item in self.retired_chunk_ids
        ):
            raise ValueError("retired_chunk_ids must contain non-empty strings")


RechunkCallback = Callable[[SourceFileSnapshot], Iterable[str]]
ReembedCallback = Callable[
    [SourceFileSnapshot, Tuple[str, ...], ManifestIndexKind, str],
    None,
]


def reindex_changed_file(
    manifest: IndexManifest,
    previous_entry: ManifestEntry,
    snapshot: SourceFileSnapshot,
    *,
    model_version: str,
    rechunk: RechunkCallback,
    reembed: ReembedCallback,
) -> ChangedFileReindexOutcome:
    """Rechunk and reembed exactly one changed manifest entry."""

    if not isinstance(manifest, IndexManifest):
        raise ValueError("manifest must be IndexManifest")
    if not isinstance(previous_entry, ManifestEntry):
        raise ValueError("previous_entry must be ManifestEntry")
    if not isinstance(snapshot, SourceFileSnapshot):
        raise ValueError("snapshot must be SourceFileSnapshot")
    if previous_entry.path != snapshot.path:
        raise ValueError("previous_entry and snapshot paths must match")
    if previous_entry.sha256 == snapshot.sha256:
        raise ValueError("reindex_changed_file requires changed content SHA")
    if not isinstance(model_version, str) or not model_version.strip():
        raise ValueError("model_version must be non-empty")
    if not callable(rechunk):
        raise ValueError("rechunk must be callable")
    if not callable(reembed):
        raise ValueError("reembed must be callable")

    new_chunk_ids = tuple(rechunk(snapshot))
    if any(
        not isinstance(item, str) or not item.strip()
        for item in new_chunk_ids
    ):
        raise ValueError("rechunk must return non-empty chunk ids")
    if len(set(new_chunk_ids)) != len(new_chunk_ids):
        raise ValueError("rechunk must return unique chunk ids")

    reembed(
        snapshot,
        new_chunk_ids,
        previous_entry.index_kind,
        model_version.strip(),
    )

    updated_entry = ManifestEntry(
        project_id=previous_entry.project_id,
        index_kind=previous_entry.index_kind,
        path=snapshot.path,
        size=snapshot.size,
        mtime_ns=snapshot.mtime_ns,
        sha256=snapshot.sha256,
        chunk_ids=new_chunk_ids,
        model_version=model_version.strip(),
    )

    retired = tuple(
        chunk_id
        for chunk_id in previous_entry.chunk_ids
        if chunk_id not in set(new_chunk_ids)
    )

    return ChangedFileReindexOutcome(
        manifest=manifest.upsert(updated_entry),
        entry=updated_entry,
        retired_chunk_ids=retired,
    )


@dataclass(frozen=True)
class RemovedFileOutcome:
    manifest: IndexManifest
    removed_entry: ManifestEntry
    removed_chunk_ids: Tuple[str, ...]


DeleteChunksCallback = Callable[
    [str, ManifestIndexKind, Tuple[str, ...]],
    None,
]


def remove_missing_file(
    manifest: IndexManifest,
    entry: ManifestEntry,
    *,
    project_root: str | Path,
    delete_chunks: DeleteChunksCallback,
) -> RemovedFileOutcome:
    """Remove one missing file entry and its orphaned chunk ids."""

    if not isinstance(manifest, IndexManifest):
        raise ValueError("manifest must be IndexManifest")
    if not isinstance(entry, ManifestEntry):
        raise ValueError("entry must be ManifestEntry")
    if not callable(delete_chunks):
        raise ValueError("delete_chunks must be callable")

    registered = manifest.get(
        entry.project_id,
        entry.index_kind,
        entry.path,
    )
    if registered != entry:
        raise ValueError("entry must match the manifest state")

    root = Path(project_root).expanduser().resolve()
    source = (root / entry.path).resolve()
    try:
        source.relative_to(root)
    except ValueError as exc:
        raise ValueError("entry path must stay inside project_root") from exc

    if source.exists():
        raise ValueError("remove_missing_file requires a missing source file")

    removed_chunk_ids = tuple(entry.chunk_ids)
    if removed_chunk_ids:
        delete_chunks(
            entry.project_id,
            entry.index_kind,
            removed_chunk_ids,
        )

    updated_manifest = manifest.remove(
        entry.project_id,
        entry.index_kind,
        entry.path,
    )

    return RemovedFileOutcome(
        manifest=updated_manifest,
        removed_entry=entry,
        removed_chunk_ids=removed_chunk_ids,
    )


@dataclass(frozen=True)
class ModelInvalidationOutcome:
    manifest: IndexManifest
    invalidated_entries: Tuple[ManifestEntry, ...]
    removed_chunk_ids: Tuple[str, ...]


ModelDeleteChunksCallback = Callable[
    [str, ManifestIndexKind, Tuple[str, ...]],
    None,
]


def invalidate_model_version(
    manifest: IndexManifest,
    *,
    project_id: str,
    index_kind: ManifestIndexKind,
    current_model_version: str,
    delete_chunks: ModelDeleteChunksCallback,
) -> ModelInvalidationOutcome:
    """Invalidate only entries in one embedding space with stale model version."""

    if not isinstance(manifest, IndexManifest):
        raise ValueError("manifest must be IndexManifest")
    if not isinstance(index_kind, ManifestIndexKind):
        raise ValueError("index_kind must be ManifestIndexKind")
    if not isinstance(current_model_version, str) or not current_model_version.strip():
        raise ValueError("current_model_version must be non-empty")
    if not callable(delete_chunks):
        raise ValueError("delete_chunks must be callable")

    target_version = current_model_version.strip()
    invalidated = tuple(
        entry
        for entry in manifest.entries
        if entry.project_id == project_id
        and entry.index_kind is index_kind
        and entry.model_version != target_version
    )

    removed_chunks = []
    updated = manifest

    for entry in invalidated:
        chunks = tuple(entry.chunk_ids)
        if chunks:
            delete_chunks(
                entry.project_id,
                entry.index_kind,
                chunks,
            )
            removed_chunks.extend(chunks)
        updated = updated.remove(
            entry.project_id,
            entry.index_kind,
            entry.path,
        )

    return ModelInvalidationOutcome(
        manifest=updated,
        invalidated_entries=invalidated,
        removed_chunk_ids=tuple(removed_chunks),
    )


class ExistingFileAction(str, Enum):
    UNCHANGED = "UNCHANGED"
    REINDEXED = "REINDEXED"


@dataclass(frozen=True)
class ExistingFileReconcileOutcome:
    action: ExistingFileAction
    manifest: IndexManifest
    entry: ManifestEntry
    retired_chunk_ids: Tuple[str, ...] = ()


def reconcile_existing_file(
    manifest: IndexManifest,
    entry: ManifestEntry,
    snapshot: SourceFileSnapshot,
    *,
    current_model_version: str,
    rechunk: RechunkCallback,
    reembed: ReembedCallback,
) -> ExistingFileReconcileOutcome:
    """Reconcile one existing file without repeating unchanged work."""

    if not isinstance(current_model_version, str) or not current_model_version.strip():
        raise ValueError("current_model_version must be non-empty")
    version = current_model_version.strip()
    if entry.model_version != version:
        raise ValueError(
            "model version mismatch must be invalidated before file reconciliation"
        )

    if should_skip_file_reprocessing(entry, snapshot):
        return ExistingFileReconcileOutcome(
            action=ExistingFileAction.UNCHANGED,
            manifest=manifest,
            entry=entry,
            retired_chunk_ids=(),
        )

    changed = reindex_changed_file(
        manifest,
        entry,
        snapshot,
        model_version=version,
        rechunk=rechunk,
        reembed=reembed,
    )
    return ExistingFileReconcileOutcome(
        action=ExistingFileAction.REINDEXED,
        manifest=changed.manifest,
        entry=changed.entry,
        retired_chunk_ids=changed.retired_chunk_ids,
    )
