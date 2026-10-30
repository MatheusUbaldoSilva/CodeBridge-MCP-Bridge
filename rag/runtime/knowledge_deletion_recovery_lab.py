"""RAG-DEL-01.04-B: read-only audit of temporary swap transaction journals.

Does not rollback, repair, or mutate any file.
"""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

from rag.runtime.knowledge_deletion_swap_lab import _lab_paths, _validate_journal, DeletionSwapError


def inspect_laboratory_transactions(catalog_file: Path, public_pointer: Path) -> list[dict]:
    catalog, pointer = _lab_paths(catalog_file, public_pointer)
    if not catalog.is_file() or not pointer.is_file():
        raise DeletionSwapError("laboratory catalog or pointer missing")
    current = catalog.read_bytes()
    pointer_sha = sha256(pointer.read_bytes()).hexdigest()
    records = []
    for journal in sorted(catalog.parent.glob("rag-del-*.journal.json")):
        if not journal.is_file() or journal.is_symlink():
            raise DeletionSwapError("redirected or missing journal")
        name=journal.name
        tid=name[len("rag-del-"):-len(".journal.json")]
        if len(tid)!=32 or any(c not in "0123456789abcdef" for c in tid):
            raise DeletionSwapError("unexpected journal name")
        item=json.loads(journal.read_text(encoding="utf-8"))
        _validate_journal(item)
        backup=catalog.parent/("rag-del-"+tid+".previous.json")
        if (item.get("transaction")!=tid or item.get("catalog")!=str(catalog)
                or item.get("backup")!=str(backup)
                or item.get("state") not in ("PREPARED","ACTIVE","ROLLED_BACK")
                or not backup.is_file() or backup.is_symlink()):
            raise DeletionSwapError("invalid or incomplete transaction")
        if sha256(backup.read_bytes()).hexdigest()!=item.get("old_sha256"):
            raise DeletionSwapError("backup tampered")
        current_digest=sha256(current).hexdigest()
        if pointer_sha != item.get("public_pointer_sha256"):
            disposition="PUBLIC_POINTER_CHANGED_MANUAL_REVIEW"
        elif current_digest==item.get("old_sha256"):
            disposition="CATALOG_AT_OLD_REVISION"
        elif current_digest==item.get("new_sha256"):
            disposition="CATALOG_AT_NEW_REVISION"
        else:
            disposition="CATALOG_CHANGED_MANUAL_REVIEW"
        records.append({
            "transaction":tid,"state":item["state"],
            "disposition":disposition,
            "requires_manual_review":disposition.endswith("MANUAL_REVIEW"),
            "repair_performed":False,"public_pointer_updated":False,
        })
    return records
