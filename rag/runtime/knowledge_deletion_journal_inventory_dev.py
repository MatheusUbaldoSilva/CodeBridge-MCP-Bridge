"""DQ-E-F-2: strict read-only deletion journal inventory, never recovery."""
from __future__ import annotations
import json
from pathlib import Path
from hashlib import sha256
from rag.runtime.knowledge_deletion_swap_lab import _validate_journal, DeletionSwapError

def inspect_deletion_journals_read_only(catalog_directory: Path) -> dict:
    directory = Path(catalog_directory)
    result = dict(state="DELETION_JOURNAL_REVIEW_BLOCKED", read_only=True,
                  activation_authorized=False, operational_use_allowed=False,
                  journal_count=0, backup_count=0, unresolved=0, blockers=[])
    if not directory.is_absolute() or not directory.is_dir() or directory.is_symlink() or (
        hasattr(directory, "is_junction") and directory.is_junction()
    ):
        result["blockers"].append("INVALID_CATALOG_DIRECTORY")
        return result
    if any(p.is_symlink() or (hasattr(p, "is_junction") and p.is_junction())
           for p in directory.parents if p.exists()):
        result["blockers"].append("REDIRECTED_PARENT")
        return result
    journals = sorted(directory.glob("rag-del-*.journal.json"))
    backups = sorted(directory.glob("rag-del-*.previous.json"))
    result["journal_count"],result["backup_count"]=len(journals),len(backups)
    linked = set()
    for journal in journals:
        tid = journal.name.removeprefix("rag-del-").removesuffix(".journal.json")
        if len(tid)!=32 or any(c not in "0123456789abcdef" for c in tid):
            result["blockers"].append("INVALID_TRANSACTION_ID")
            continue
        backup=directory/("rag-del-"+tid+".previous.json")
        if (journal.is_symlink() or not journal.is_file()
                or backup.is_symlink() or not backup.is_file()):
            result["blockers"].append("JOURNAL_BACKUP_MISSING_OR_REDIRECTED")
            continue
        linked.add(backup.name)
        try:
            entry=json.loads(journal.read_text(encoding="utf-8"))
            _validate_journal(entry)
            if (entry.get("schema_version")!=1 or entry.get("transaction")!=tid
                    or entry.get("catalog")!=str(directory/"project-indexes.json")
                    or entry.get("backup")!=str(backup)
                    or sha256(backup.read_bytes()).hexdigest()!=entry.get("old_sha256")
                    or entry.get("state") not in ("PREPARED","ACTIVE","ROLLED_BACK")):
                raise ValueError("invalid journal identity")
            if entry["state"]!="ROLLED_BACK":
                result["unresolved"]+=1
                result["blockers"].append("UNRESOLVED_TRANSACTION")
        except (OSError, ValueError, TypeError, KeyError, DeletionSwapError):
            result["blockers"].append("INVALID_JOURNAL_EVIDENCE")
    if any(b.name not in linked or b.is_symlink() for b in backups):
        result["blockers"].append("ORPHAN_BACKUP")
    if not result["blockers"]:
        result["state"]="DELETION_JOURNAL_INVENTORY_READ_ONLY_CLEAN"
    return result
