"""Read-only revalidation of a preview before simulated user confirmation.

Never produces a publish authorization and never writes index storage.
"""
from __future__ import annotations
import hashlib
from pathlib import Path


def snapshot_preview(project, folder, rows):
    root = Path(folder).resolve(strict=True)
    if not root.is_dir() or not isinstance(project, str) or not project:
        raise ValueError("invalid preview scope")
    if not isinstance(rows, list) or not rows:
        raise ValueError("no preview candidates")
    signatures = {}
    for item in rows:
        relative = item.get("path") if isinstance(item, dict) else None
        if not isinstance(relative, str) or not relative or relative in signatures:
            raise ValueError("invalid or duplicate preview path")
        candidate = (root / relative).resolve(strict=True)
        if not candidate.is_relative_to(root) or not candidate.is_file():
            raise ValueError("file outside selected folder")
        before = candidate.stat()
        digest = hashlib.sha256(candidate.read_bytes()).hexdigest()
        after = candidate.stat()
        if (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (after.st_size, after.st_mtime_ns, after.st_ctime_ns):
            raise ValueError("file changed during preview; generate a new preview")
        signatures[relative] = digest
    return {"project": project, "folder": str(root), "sha256": signatures}


def revalidate_preview(snapshot, project, folder):
    if not isinstance(snapshot, dict) or project != snapshot.get("project"):
        raise ValueError("project changed; generate a new preview")
    if Path(folder).resolve() != Path(snapshot["folder"]):
        raise ValueError("selected folder changed; generate a new preview")
    previous = snapshot.get("sha256")
    if not isinstance(previous, dict) or not previous:
        raise ValueError("missing preview signatures")
    current = snapshot_preview(project, folder, [{"path": path} for path in previous])
    if current["sha256"] != previous:
        raise ValueError("files changed; generate a new preview")
    return {"state": "PREVIEW_REVALIDATED_ONLY", "publish_enabled": False,
            "files_checked": len(previous)}
