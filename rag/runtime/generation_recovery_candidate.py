"""Manual recovery candidate inspection for isolated RAG generations.

No activation and no deletion. Refuses ambiguous or unvalidated restoration.
"""
from __future__ import annotations
from pathlib import Path
import re
from rag.runtime.incremental_bundle_validate import validate_incremental_bundle

_NAME = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}$")


class RecoveryCandidateError(RuntimeError):
    pass


def verify_recovery_candidate(test_root, name):
    root = Path(test_root).resolve()
    if "codebridge-rag-generation-test" not in {part.lower() for part in root.parts}:
        raise RecoveryCandidateError("test directory required")
    if not isinstance(name, str) or not _NAME.fullmatch(name):
        raise RecoveryCandidateError("invalid generation name")
    base = (root / "generations").resolve()
    candidate = (base / name).resolve()
    if candidate.parent != base or not candidate.is_dir():
        raise RecoveryCandidateError("candidate unavailable or outside generation root")
    try:
        report = validate_incremental_bundle(candidate)
    except Exception as exc:
        raise RecoveryCandidateError("candidate failed cross-store validation") from exc
    return {"state": "VALIDATED_CANDIDATE_NOT_ACTIVATED",
            "generation": name, "report": report, "path": str(candidate)}


def inspect_recovery_candidates(test_root):
    root = Path(test_root).resolve()
    if "codebridge-rag-generation-test" not in {part.lower() for part in root.parts}:
        raise RecoveryCandidateError("test directory required")
    base = root / "generations"
    if not base.exists():
        return {"validated": [], "rejected": []}
    validated, rejected = [], []
    for folder in sorted(base.iterdir()):
        if not folder.is_dir():
            continue
        try:
            validated.append(verify_recovery_candidate(root, folder.name))
        except RecoveryCandidateError:
            rejected.append(folder.name)
    return {"validated": validated, "rejected": rejected,
            "selected": None, "automatic_recovery": False}
