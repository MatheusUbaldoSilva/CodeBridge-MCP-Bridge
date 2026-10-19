"""Isolated real CodeBridge RAG delta merge; never activates production.

Inputs are verified closed staging artifacts. Active source drift invalidates the
baseline, and every merged output must pass all cross-store integrity checks.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from uuid import uuid4

from rag.runtime.status import resolve_rag_sqlite_path
from rag.runtime.incremental_bundle_validate import validate_incremental_bundle
from rag.runtime.incremental_sqlite_stage import stage_incremental_sqlite
from rag.runtime.incremental_qdrant_stage import stage_incremental_qdrant
from rag.runtime.incremental_manifest_stage import stage_incremental_manifest


class ControlledMergeError(RuntimeError):
    pass


def _approved_stage(path: Path, staging: Path) -> Path:
    candidate = Path(path).resolve(strict=True)
    if candidate.parent != staging or not candidate.is_dir():
        raise ControlledMergeError("bundle must be directly inside the real RAG staging root")
    return candidate


def merge_closed_bundles(baseline_path: Path, incoming_path: Path) -> dict:
    state = resolve_rag_sqlite_path().resolve().parent
    staging = (state / "staging").resolve()
    if not staging.is_dir():
        raise ControlledMergeError("RAG staging root unavailable")
    old = _approved_stage(baseline_path, staging)
    incoming = _approved_stage(incoming_path, staging)
    if old == incoming or not old.name.startswith("baseline-") or not incoming.name.startswith("build-"):
        raise ControlledMergeError("unexpected baseline or candidate identity")

    receipt_path = old / "baseline-receipt.json"
    if not receipt_path.is_file():
        raise ControlledMergeError("baseline receipt required")
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    if (receipt.get("status") != "CLOSED_BASELINE_VALIDATED_NOT_PUBLISHED"
            or Path(receipt["snapshot_root"]).resolve() != old
            or receipt.get("activation_permitted") is not False):
        raise ControlledMergeError("baseline is not approved for isolated processing")

    # A source change since the capture demands a new consistent baseline.
    for source, fingerprint in receipt["source_fingerprint"].items():
        path = Path(source).resolve()
        if not path.is_relative_to(state):
            raise ControlledMergeError("baseline fingerprint references outside storage")
        stat = path.stat()
        if (stat.st_size != fingerprint["size"]
                or stat.st_mtime_ns != fingerprint["mtime_ns"]):
            raise ControlledMergeError("live source changed since baseline snapshot")

    before = validate_incremental_bundle(old)
    delta = validate_incremental_bundle(incoming)
    if delta["documents"] != 1 or delta["chunks"] < 1:
        raise ControlledMergeError("first live delta must contain exactly one document")

    output = staging / ("merged-" + uuid4().hex)
    output.mkdir(parents=True, exist_ok=False)
    try:
        sql = stage_incremental_sqlite(
            old / "rag_index.sqlite3", incoming / "rag_index.sqlite3",
            output / "rag_index.sqlite3", "codebridge",
        )
        manifest = stage_incremental_manifest(
            old / "rag-index-manifest.json", incoming / "rag-index-manifest.json",
            output / "rag-index-manifest.json", "codebridge",
        )
        vectors = stage_incremental_qdrant(
            old / "qdrant", incoming / "qdrant", output / "qdrant", "codebridge",
        )
        final = validate_incremental_bundle(output)
        expected_count = before["chunks"] + delta["chunks"]
        if (sql["added"] != delta["documents"] or sql["replaced"] != 0
                or manifest["added"] != delta["documents"]
                or final["documents"] != before["documents"] + delta["documents"]
                or final["chunks"] != expected_count
                or final["vectors"] != expected_count):
            raise ControlledMergeError("unexpected merged counts")
        # Verify that original source storage has not drifted during merge.
        for source, fingerprint in receipt["source_fingerprint"].items():
            stat = Path(source).stat()
            if (stat.st_size != fingerprint["size"] or stat.st_mtime_ns != fingerprint["mtime_ns"]):
                raise ControlledMergeError("live source changed during merge")
        result = {
            "state": "MERGED_VALIDATED_NOT_PUBLISHED",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "baseline": str(old),
            "candidate": str(incoming),
            "directory": str(output),
            "merged": final,
            "source_documents": before["documents"],
            "added_documents": delta["documents"],
            "sqlite": sql,
            "manifest": manifest,
            "qdrant": vectors,
            "activation_permitted": False,
        }
        (output / "merged-receipt.json").write_text(
            json.dumps(result, indent=2, ensure_ascii=True), encoding="utf-8",
        )
        return result
    except BaseException as exc:
        (output / "MERGE_FAILED.txt").write_text(
            type(exc).__name__ + ": " + str(exc), encoding="utf-8",
        )
        raise


def inspect_completed_merge(path: Path) -> dict:
    """Verify a retained candidate by receipt and cross-store contents, read-only."""
    state = resolve_rag_sqlite_path().resolve().parent
    target = _approved_stage(path, (state / "staging").resolve())
    if not target.name.startswith("merged-"):
        raise ControlledMergeError("not a controlled merged generation")
    receipt_file = target / "merged-receipt.json"
    if not receipt_file.is_file():
        raise ControlledMergeError("merged receipt required")
    receipt = json.loads(receipt_file.read_text(encoding="utf-8"))
    if (receipt.get("state") != "MERGED_VALIDATED_NOT_PUBLISHED"
            or receipt.get("activation_permitted") is not False
            or Path(receipt["directory"]).resolve() != target):
        raise ControlledMergeError("invalid merge proof or unexpected activation flag")
    integrity = validate_incremental_bundle(target)
    if integrity != receipt.get("validation", receipt.get("merged")):
        raise ControlledMergeError("merged contents differ from validated receipt")
    baseline = _approved_stage(receipt["baseline"], (state / "staging").resolve())
    addition = _approved_stage(receipt["candidate"], (state / "staging").resolve())
    if (integrity["documents"] != validate_incremental_bundle(baseline)["documents"]
            + validate_incremental_bundle(addition)["documents"]):
        raise ControlledMergeError("merged count no longer matches sources")
    return {
        "state": "MERGED_REVERIFIED_NOT_PUBLISHED",
        "read_only": True,
        "activation_permitted": False,
        "root": str(target),
        "validation": integrity,
    }
