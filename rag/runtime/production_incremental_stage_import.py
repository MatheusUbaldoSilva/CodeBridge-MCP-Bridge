"""Import a previously verified closed incremental bundle into official staging.

No active index access, no pointer modification and no release authorization.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
from uuid import uuid4

from rag.runtime.incremental_bundle_validate import validate_incremental_bundle
from rag.runtime.production_incremental_candidate_review import assess_offline_incremental_candidate
from rag.runtime.status import resolve_rag_sqlite_path

_FILES = ("rag_index.sqlite3", "rag-index-manifest.json", "qdrant/meta.json",
          "qdrant/collection/text/storage.sqlite", "qdrant/collection/code/storage.sqlite")


def _digest(folder: Path) -> dict[str, str]:
    return {name: hashlib.sha256((folder / name).read_bytes()).hexdigest()
            for name in _FILES}


def import_verified_closed_candidate(baseline, candidate, expected_source_sha256: str) -> dict:
    state = resolve_rag_sqlite_path().resolve().parent
    old, source = Path(baseline).resolve(strict=True), Path(candidate).resolve(strict=True)
    # Only the already-established P2 closed snapshot is accepted.
    origin = (Path.home() / "AppData" / "Local" / "Temp" /
              "codebridge-rag-p2-closed-baseline").resolve()
    if old != origin / "legacy" or source != origin / "candidate-merged-211":
        raise ValueError("unapproved closed P2 source directories")
    proof = assess_offline_incremental_candidate(old, source, expected_source_sha256)
    if proof["state"] != "P3_OFFLINE_VERIFIED_NOT_AUTHORIZED":
        raise ValueError("closed P2 candidate failed P3 cross-store review")
    initial = _digest(source)
    target = state / "staging" / ("merged-" + uuid4().hex)
    if target.exists():
        raise ValueError("staging target unexpectedly exists")
    try:
        shutil.copytree(source, target)
        validation = validate_incremental_bundle(target)
        if (validation != proof["cross_store"]["candidate"]
                or _digest(target) != initial or _digest(source) != initial):
            raise ValueError("staged candidate content differs from approved P2 source")
        receipt = {
            "state": "MERGED_VALIDATED_NOT_PUBLISHED",
            "status": "MERGED_VALIDATED_NOT_PUBLISHED",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "directory": str(target), "baseline": str(old), "candidate": str(source),
            "merged": validation, "file_sha256": initial,
            "approved_source_sha256": expected_source_sha256,
            "source_review": proof["source_review"]["details"],
            "activation_permitted": False, "active_pointer_updated": False,
            "imported_from_verified_closed_p2": True,
        }
        (target / "merged-receipt.json").write_text(
            json.dumps(receipt, indent=2, sort_keys=True), encoding="utf-8")
        return {"state": receipt["state"], "staging": str(target),
                "validation": validation, "activation_permitted": False}
    except BaseException:
        if target.exists():
            shutil.rmtree(target)
        raise
