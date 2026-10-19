"""Read-only source freshness for a versioned CodeBridge RAG manifest.

Compare provenance using the same text SHA contract as the indexer. A Windows
CRLF checkout is not a content change when the stored source was normalized to
LF before hashing. This never indexes or mutates the source/active index.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath

from rag.chunking.provenance import source_sha256


def assess_generation_source_freshness(
    generation_directory: Path,
    project_root: Path,
) -> dict:
    root = Path(project_root).resolve(strict=True)
    if root.name != "CodeBridge-MCP-Bridge" or not (root / ".git").exists():
        raise ValueError("not the approved CodeBridge source checkout")
    manifest = Path(generation_directory).resolve(strict=True) / "rag-index-manifest.json"
    content = json.loads(manifest.read_text(encoding="utf-8"))
    entries = content.get("entries")
    if not isinstance(entries, list):
        raise ValueError("generation manifest entries must be an array")

    counts = {
        "byte_exact": 0, "newline_only": 0,
        "content_changed": 0, "missing": 0,
    }
    changed_paths: list[str] = []
    missing_paths: list[str] = []
    seen: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("invalid manifest entry")
        path = entry.get("path")
        expected = entry.get("sha256")
        if not isinstance(path, str) or not isinstance(expected, str):
            raise ValueError("source path/SHA missing")
        normalized = PurePosixPath(path)
        if (
            normalized.is_absolute() or ".." in normalized.parts
            or normalized.as_posix() != path or not path or path in seen
            or entry.get("project_id") != "codebridge"
        ):
            raise ValueError("invalid/outside/duplicate CodeBridge source path")
        seen.add(path)
        file = (root / Path(*normalized.parts)).resolve()
        if not file.is_relative_to(root):
            raise ValueError("indexed source escapes approved Git root")
        if not file.is_file():
            counts["missing"] += 1
            missing_paths.append(path)
            continue
        raw = file.read_bytes()
        if hashlib.sha256(raw).hexdigest() == expected:
            counts["byte_exact"] += 1
            continue
        # The indexer hashes decoded source_text (universal newlines); do not
        # incorrectly mark CRLF checkouts stale on Windows.
        decoded = raw.decode("utf-8", errors="replace")
        canonical = decoded.replace("\r\n", "\n").replace("\r", "\n")
        if source_sha256(canonical) == expected:
            counts["newline_only"] += 1
            continue
        counts["content_changed"] += 1
        changed_paths.append(path)
    count = sum(counts.values())
    if count != len(entries):
        raise RuntimeError("indexed source enumeration lost a manifest entry")
    return {
        "state": "SOURCE_SNAPSHOT_CURRENT"
                 if not changed_paths and not missing_paths
                 else "SOURCE_SNAPSHOT_DRIFT",
        "project_id": "codebridge",
        "indexed_entries_checked": count,
        "byte_exact": counts["byte_exact"],
        "newline_only": counts["newline_only"],
        "content_changed": counts["content_changed"],
        "missing": counts["missing"],
        "content_changed_paths": changed_paths,
        "missing_paths": missing_paths,
        "new_unindexed_sources_assessed": False,
        "read_only": True,
        "safe_to_activate": False,
    }
