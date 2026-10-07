"""Incremental file snapshot helpers — RAG-012-B."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path, PurePosixPath

from .manifest import ManifestEntry


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
