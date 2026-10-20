"""Read-only comparison of immutable RAG candidate source content.

A digest or diff is evidence for a human review, NOT a publication signature.
This module cannot authorize, publish, roll back, or touch active indexes.
"""
from __future__ import annotations

import difflib
from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3

from rag.chunking.provenance import source_sha256
from rag.index.manifest import load_index_manifest


def _closed_source(folder: Path) -> dict[str, tuple[str, str]]:
    database = folder / "rag_index.sqlite3"
    if not database.is_file():
        raise ValueError("missing closed SQLite document source")
    with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)) as connection:
        connection.execute("PRAGMA query_only=ON")
        rows = connection.execute(
            "SELECT path,content,sha256 FROM rag_documents "
            "WHERE project_id='codebridge'"
        ).fetchall()
    if len({r[0] for r in rows}) != len(rows):
        raise ValueError("duplicate source path in closed SQLite")
    result = {}
    for path, content, sha in rows:
        if source_sha256(content) != sha:
            raise ValueError("indexed source SHA mismatched: " + path)
        result[path] = (content, sha)
    return result


def summarize_versioned_source_review(base_dir: Path, candidate_dir: Path) -> dict:
    base = Path(base_dir).resolve(strict=True)
    candidate = Path(candidate_dir).resolve(strict=True)
    if (base == candidate or base.parent != candidate.parent
            or base.parent.name != "generations"
            or not base.name.startswith("v1_base_")
            or not candidate.name.startswith("v1_delta_")):
        raise ValueError("only distinct immutable CodeBridge generations permitted")
    old_manifest = load_index_manifest(base / "rag-index-manifest.json")
    new_manifest = load_index_manifest(candidate / "rag-index-manifest.json")
    old_entries = {e.path: e for e in old_manifest.entries if e.project_id == "codebridge"}
    new_entries = {e.path: e for e in new_manifest.entries if e.project_id == "codebridge"}
    if len(old_entries) != len(old_manifest.entries) or len(new_entries) != len(new_manifest.entries):
        raise ValueError("unexpected project in versioned manifest")
    old_sources = _closed_source(base)
    new_sources = _closed_source(candidate)
    if old_entries.keys() != old_sources.keys() or new_entries.keys() != new_sources.keys():
        raise ValueError("SQLite sources differ from their manifests")
    for path, entry in old_entries.items():
        if entry.sha256 != old_sources[path][1]:
            raise ValueError("old manifest source hash mismatch: " + path)
    for path, entry in new_entries.items():
        if entry.sha256 != new_sources[path][1]:
            raise ValueError("new manifest source hash mismatch: " + path)

    added = sorted(new_entries.keys() - old_entries.keys())
    removed = sorted(old_entries.keys() - new_entries.keys())
    changed = sorted(
        path for path in old_entries.keys() & new_entries.keys()
        if (old_entries[path].sha256 != new_entries[path].sha256
            or old_entries[path].chunk_ids != new_entries[path].chunk_ids)
    )
    detail = []
    for path in added + changed + removed:
        before = old_sources.get(path)
        after = new_sources.get(path)
        lines_before = before[0].splitlines() if before else []
        lines_after = after[0].splitlines() if after else []
        edits = [
            (kind, a, b, c, d)
            for kind, a, b, c, d in difflib.SequenceMatcher(
                a=lines_before, b=lines_after, autojunk=False,
            ).get_opcodes() if kind != "equal"
        ]
        detail.append({
            "path": path,
            "action": "ADDED" if path in added else ("REMOVED" if path in removed else "MODIFIED"),
            "old_sha256": before[1] if before else None,
            "candidate_sha256": after[1] if after else None,
            "old_chunk_count": len(old_entries[path].chunk_ids) if before else 0,
            "candidate_chunk_count": len(new_entries[path].chunk_ids) if after else 0,
            "old_lines": len(lines_before),
            "candidate_lines": len(lines_after),
            "added_lines": sum(d - c for _, a, b, c, d in edits),
            "removed_lines": sum(b - a for _, a, b, c, d in edits),
            "edit_hunks": len(edits),
            "candidate_line_ranges": [
                [c + 1, d] for kind, a, b, c, d in edits if d > c
            ][:20],
        })
    result = {
        "state": "CONTENT_COMPARISON_ONLY_NOT_APPROVED",
        "baseline": base.name,
        "candidate": candidate.name,
        "base_entries": len(old_entries),
        "candidate_entries": len(new_entries),
        "added_paths": added, "modified_paths": changed, "removed_paths": removed,
        "unchanged_count": len(old_entries.keys() & new_entries.keys()) - len(changed),
        "details": detail,
        "operator_content_review_attested": False,
        "safe_to_activate": False,
        "read_only": True,
    }
    checksum = json.dumps(result, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    result["evidence_sha256_not_signature"] = hashlib.sha256(checksum.encode()).hexdigest()
    return result
