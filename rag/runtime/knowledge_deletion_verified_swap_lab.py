"""RAG-DEL-01.04: verified lab-only transition, no operational catalog support."""
from pathlib import Path
from rag.runtime.knowledge_deletion_generation import verify_deletion_generation
from rag.runtime.knowledge_deletion_swap_lab import (
    laboratory_swap, DeletionSwapError,
)

def laboratory_verified_swap(project_id:str,old_revision:str,candidate:dict,
                             *,catalog_file:Path,public_pointer:Path,
                             operator_approved:bool=False,laboratory_mode:bool=False,
                             _fail_at:str|None=None)->dict:
    if operator_approved is not True or laboratory_mode is not True:
        raise PermissionError("explicit laboratory approval required")
    if candidate.get("project_id")!=project_id or candidate.get("index_family")!="RAG_DEL_01":
        raise DeletionSwapError("invalid deletion candidate")
    generation=Path(candidate.get("generation_directory",""))
    snapshot=Path(candidate.get("source_directory",""))
    revision=candidate.get("source_revision")
    if not generation.is_absolute() or not snapshot.is_absolute():
        raise DeletionSwapError("absolute generation and snapshot required")
    # An unverified arbitrary row must never reach catalog_swap.
    verify_deletion_generation(candidate,project_id,generation,snapshot,revision)
    def _recheck_closed_candidate_under_catalog_mutex():
        verify_deletion_generation(candidate,project_id,generation,snapshot,revision)
    return laboratory_swap(
        project_id,old_revision,candidate,
        catalog_file=catalog_file,public_pointer=public_pointer,
        operator_approved=True,laboratory_mode=True,_fail_at=_fail_at,
        _locked_validation=_recheck_closed_candidate_under_catalog_mutex,
    )
