"""Read-only file-level classification before incremental RAG indexing.

This module never opens production SQLite in write mode or changes vectors.
"""
from __future__ import annotations

import sqlite3
import subprocess
from pathlib import Path

from rag.chunking.provenance import source_sha256
from rag.runtime.status import resolve_rag_sqlite_path


def assess_incremental_plan(plan: dict, *, database: Path | None = None, full_inventory: bool = False) -> dict:
    if not isinstance(plan, dict):
        raise ValueError("invalid index plan")
    project = plan.get("project_id")
    if not isinstance(project, str) or not project:
        raise ValueError("project_id is required")
    candidates = plan.get("candidates")
    root_value = plan.get("project_root")
    if not isinstance(candidates, list):
        raise ValueError("candidates must be a list")
    # Existing tests and integrations may supply a plan without a project root:
    # in that case only name-based classification is possible.
    root = Path(root_value).resolve() if isinstance(root_value, str) and root_value else None
    db = Path(database) if database is not None else resolve_rag_sqlite_path()
    existing: dict[str, str | None] = {}
    if db.exists():
        connection = sqlite3.connect(f"{db.resolve().as_uri()}?mode=ro", uri=True)
        try:
            existing = {
                str(row[0]): row[1]
                for row in connection.execute(
                    "SELECT path, sha256 FROM rag_documents "
                    "WHERE project_id=? AND path IS NOT NULL", (project,)
                )
            }
        finally:
            connection.close()

    fresh, unchanged, modified, unknown = [], [], [], []
    seen = set()
    for item in candidates:
        if not isinstance(item, dict) or not isinstance(item.get("path"), str):
            raise ValueError("invalid candidate")
        path = item["path"]
        if not path or path in seen:
            raise ValueError("empty or duplicate candidate path")
        seen.add(path)
        if path not in existing:
            fresh.append(path)
            continue
        if root is None or not existing[path]:
            unknown.append(path)
            continue
        file = (root / path).resolve()
        if not file.is_relative_to(root) or not file.is_file():
            raise ValueError("candidate missing or outside project root")
        digest = source_sha256(file.read_text(encoding="utf-8", errors="replace"))
        (unchanged if digest == existing[path] else modified).append(path)
    # Only a complete BOTH-scope scan can distinguish removal from an
    # intentionally limited request. Report candidates; never delete data.
    removed: list[str] = []
    rename_candidates: list[dict[str, str]] = []
    if full_inventory:
        if root is None or plan.get("scope") != "BOTH":
            raise ValueError("removal detection requires complete BOTH project inventory")
        for old_path in sorted(existing):
            if old_path in seen:
                continue
            previous = (root / old_path).resolve()
            if not previous.is_relative_to(root):
                continue
            # Existing files excluded by policy or source selection are not
            # considered deleted.
            if not previous.exists():
                removed.append(old_path)
        new_by_sha: dict[str, list[str]] = {}
        for new_path in fresh:
            current = (root / new_path).resolve()
            if not current.is_relative_to(root) or not current.is_file():
                raise ValueError("new candidate missing or outside project root")
            digest = source_sha256(current.read_text(encoding="utf-8", errors="replace"))
            new_by_sha.setdefault(digest, []).append(new_path)
        old_by_sha: dict[str, list[str]] = {}
        for old_path in removed:
            digest = existing[old_path]
            if digest:
                old_by_sha.setdefault(digest, []).append(old_path)
        for digest, former_paths in old_by_sha.items():
            successors = new_by_sha.get(digest, [])
            if len(former_paths) == len(successors) == 1:
                rename_candidates.append(
                    {"from": former_paths[0], "to": successors[0], "sha256": digest}
                )
    # Git provenance is independent from SQLite staleness: dirty sources
    # must not be attributed to the last committed HEAD.
    git_head = None
    git_status = "UNAVAILABLE"
    git_modified: list[str] = []
    git_untracked: list[str] = []
    if root is not None and (root / ".git").exists():
        try:
            head = subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=root,
                capture_output=True, timeout=10, check=False,
            )
            dirty = subprocess.run(
                ["git", "status", "--porcelain=v1", "-z", "--untracked-files=all"],
                cwd=root, capture_output=True, timeout=15, check=False,
            )
            if head.returncode == 0 and dirty.returncode == 0:
                git_head = head.stdout.decode("ascii", errors="replace").strip()
                git_status = "AVAILABLE"
                records = dirty.stdout.split(b"\x00")
                offset = 0
                while offset < len(records) and records[offset]:
                    item = records[offset].decode("utf-8", errors="replace")
                    flag, path = item[:2], item[3:].replace("\\", "/")
                    if path in seen:
                        if flag == "??":
                            git_untracked.append(path)
                        else:
                            git_modified.append(path)
                    # -z emits an extra source name for a rename/copy.
                    if "R" in flag or "C" in flag:
                        offset += 1
                    offset += 1
        except (OSError, subprocess.TimeoutExpired):
            git_status = "UNAVAILABLE"
    return {
        "project_id": project,
        "new_count": len(fresh),
        "existing_count": len(unchanged) + len(modified) + len(unknown),
        "unchanged_count": len(unchanged),
        "modified_count": len(modified),
        "unknown_count": len(unknown),
        "new_files": fresh,
        "existing_files": unchanged + modified + unknown,
        "unchanged_files": unchanged,
        "modified_files": modified,
        "unknown_files": unknown,
        "removed_count": len(removed),
        "removed_files": removed,
        "rename_candidates": rename_candidates,
        "full_inventory": full_inventory,
        "git_status": git_status,
        "git_head": git_head,
        "git_modified_files": sorted(git_modified),
        "git_untracked_files": sorted(git_untracked),
        "safe_to_publish": False,
        "reason": "A publicacao incremental ainda nao foi implementada e validada.",
    }
