"""Prepare versioned CodeBridge RAG generations from validated closed bundles.

Only creates new generations. Never overwrites the legacy active index,
alters an active pointer, retires an old generation or kills a running reader.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
from uuid import uuid4

from rag.runtime.status import resolve_rag_sqlite_path
from rag.runtime.incremental_bundle_validate import validate_incremental_bundle


class GenerationPreparationError(RuntimeError):
    pass


def _hash(data: Path) -> str:
    digest = hashlib.sha256()
    with data.open("rb") as stream:
        for part in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(part)
    return digest.hexdigest()


def prepare_versioned_generation(source: Path, *, label: str) -> dict:
    state = resolve_rag_sqlite_path().resolve().parent
    staging = (state / "staging").resolve()
    bundle = Path(source).resolve(strict=True)
    if bundle.parent != staging or label not in ("base", "delta"):
        raise GenerationPreparationError("source must be an approved closed staging artifact")
    if label == "base":
        receipt_file = bundle / "baseline-receipt.json"
        if not bundle.name.startswith("baseline-"):
            raise GenerationPreparationError("base receipt does not match source")
        expected = "CLOSED_BASELINE_VALIDATED_NOT_PUBLISHED"
    else:
        receipt_file = bundle / "merged-receipt.json"
        if not bundle.name.startswith("merged-"):
            raise GenerationPreparationError("candidate receipt does not match source")
        expected = "MERGED_VALIDATED_NOT_PUBLISHED"
    if not receipt_file.is_file():
        raise GenerationPreparationError("signed provenance receipt missing")
    receipt = json.loads(receipt_file.read_text(encoding="utf-8"))
    if (receipt.get("status", receipt.get("state")) != expected
            or receipt.get("activation_permitted") is not False):
        raise GenerationPreparationError("unverified generation receipt")

    before = validate_incremental_bundle(bundle)
    files = [
        "rag_index.sqlite3", "rag-index-manifest.json",
        "qdrant/meta.json",
        "qdrant/collection/text/storage.sqlite",
        "qdrant/collection/code/storage.sqlite",
    ]
    hashes = {name: _hash(bundle / name) for name in files}

    directory = state / "generations" / ("v1_" + label + "_" + uuid4().hex[:14])
    if directory.exists():
        raise GenerationPreparationError("generation already exists")
    directory.parent.mkdir(parents=True, exist_ok=True)
    try:
        shutil.copytree(
            bundle, directory,
            ignore=shutil.ignore_patterns(".lock"),
        )
        after = validate_incremental_bundle(directory)
        if after != before or any(_hash(directory / name) != sha
                                  for name, sha in hashes.items()):
            raise GenerationPreparationError("versioned generation is not identical")
        if any(_hash(bundle / name) != sha for name, sha in hashes.items()):
            raise GenerationPreparationError("source staging changed during copying")
        payload = {
            "status": "VERSIONED_GENERATION_VALIDATED_NOT_ACTIVE",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "label": label,
            "generation": directory.name,
            "source": str(bundle),
            "directory": str(directory),
            "validation": after,
            "file_sha256": hashes,
            "active_pointer_updated": False,
            "activation_permitted": False,
        }
        (directory / "generation-receipt.json").write_text(
            json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8",
        )
        return payload
    except BaseException as exc:
        (directory / "PREPARATION_FAILED.txt").write_text(
            type(exc).__name__ + ": " + str(exc), encoding="utf-8",
        )
        raise
