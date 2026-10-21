"""Fail-closed selection of an existing immutable RAG candidate for supervised cutover."""
from __future__ import annotations

import json
from pathlib import Path


def select_incremental_generation(generations_dir: str | Path) -> dict:
    root = Path(generations_dir)
    matches = []
    issues = []
    if not root.is_dir():
        return {"state": "BLOCKED", "issues": ["GENERATIONS_DIRECTORY_MISSING"],
                "candidate": None, "activation_authorized": False}
    for folder in sorted(root.glob("v1_delta_*")):
        try:
            receipt = json.loads((folder / "generation-receipt.json").read_text(encoding="utf-8"))
            validation = receipt["validation"]
            if (receipt.get("status") == "VERSIONED_GENERATION_VALIDATED_NOT_ACTIVE"
                    and receipt.get("generation") == folder.name
                    and receipt.get("activation_permitted") is False
                    and validation.get("documents") == 211
                    and validation.get("chunks") == 8763
                    and validation.get("vectors") == 8763
                    and validation.get("manifest_entries") == 211):
                # A matching receipt is not enough: verify immutable files,
                # SQLite and vector identity with the existing production verifier.
                from rag.runtime.production_cutover_gate import _verify_versioned
                from rag.runtime.status import resolve_rag_sqlite_path
                official = resolve_rag_sqlite_path().resolve().parent
                if root.resolve() != (official / "generations").resolve():
                    raise ValueError("generation selector outside official RAG root")
                verified = _verify_versioned(official, folder.name, "delta")
                if verified.get("validation") != validation or not verified.get("sha_verified"):
                    raise ValueError("versioned candidate receipt unverified")
                matches.append(folder.name)
        except (OSError, ValueError, KeyError, TypeError):
            issues.append("INVALID_GENERATION_RECEIPT")
    if len(matches) != 1:
        issues.append("EXPECTED_UNIQUE_8763_GENERATION_NOT_FOUND")
    return {
        "state": "MATCHED_NOT_AUTHORIZED" if not issues else "BLOCKED",
        "issues": sorted(set(issues)),
        "candidate": matches[0] if len(matches) == 1 and not issues else None,
        "matching_generations": matches,
        "activation_authorized": False,
        "safe_to_publish": False,
    }
