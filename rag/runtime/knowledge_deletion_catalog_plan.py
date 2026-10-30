"""RAG-DEL-01.04-A: read-only compare-and-swap planning for private catalog.

This module never writes the catalog, backup, journal, or public pointer.
A future audited executor must validate the fully verified candidate itself.
"""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

from rag.runtime.auto_index_canary import _catalog_bytes,_parse_catalog,_read_pointer


class DeletionCatalogSwapPlanError(ValueError):
    pass


def plan_private_generation_replacement(catalog_file: Path, public_pointer: Path,
                                         project_id: str, expected_old_revision: str,
                                         candidate: dict) -> dict:
    if (not isinstance(project_id,str) or project_id=="codebridge"
            or not isinstance(expected_old_revision,str)
            or not expected_old_revision):
        raise DeletionCatalogSwapPlanError("public or invalid project replacement")
    catalog=Path(catalog_file)
    pointer=Path(public_pointer)
    if (catalog.name!="project-indexes.json" or not catalog.is_file()
            or catalog.is_symlink() or pointer.is_symlink()):
        raise DeletionCatalogSwapPlanError("unsafe private catalog location")
    previous=_catalog_bytes(catalog)
    data=_parse_catalog(previous)
    old=data["projects"].get(project_id)
    if (not isinstance(old,dict) or old.get("enabled") is not True
            or old.get("project_id")!=project_id
            or old.get("source_revision")!=expected_old_revision):
        raise DeletionCatalogSwapPlanError("active project revision does not match")
    if (not isinstance(candidate,dict)
            or candidate.get("enabled") is not True
            or candidate.get("project_id")!=project_id
            or not isinstance(candidate.get("source_revision"),str)
            or not candidate["source_revision"]
            or candidate.get("generation_directory")==old.get("generation_directory")):
        raise DeletionCatalogSwapPlanError("candidate not distinct or invalid")
    # A candidate row proposed here is NOT accepted as verified by this planner.
    pointer_bytes=_read_pointer(pointer)
    updated={"schema_version":1,"projects":dict(data["projects"])}
    updated["projects"][project_id]=candidate
    encoded=(json.dumps(updated,sort_keys=True,indent=2,ensure_ascii=False)+"\n").encode("utf-8")
    return {
        "mode":"PRIVATE_CATALOG_SWAP_PLAN_ONLY",
        "project_id":project_id,
        "old_catalog_sha256":sha256(previous).hexdigest(),
        "proposed_catalog_sha256":sha256(encoded).hexdigest(),
        "public_pointer_sha256":sha256(pointer_bytes).hexdigest(),
        "prior_source_revision":expected_old_revision,
        "candidate_source_revision":candidate["source_revision"],
        "project_entries_unchanged":len(data["projects"])-1,
        "candidate_integrity_verified":False,
        "backup_written":False,
        "journal_written":False,
        "catalog_modified":False,
        "activation_authorized":False,
        "public_pointer_updated":False,
    }
