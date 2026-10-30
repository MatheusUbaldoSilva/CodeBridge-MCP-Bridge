"""RAG-DEL read-only lineage proof: baseline - selection == candidate."""
from __future__ import annotations
from hashlib import sha256
import json
from pathlib import Path
from rag.index.manifest import load_index_manifest

class DeletionLineageError(ValueError):
    pass

def verify_survivor_lineage(baseline_manifest: str | Path,
                            candidate_manifest: str | Path,
                            preview: dict) -> dict:
    if (not isinstance(preview,dict)
            or preview.get("mode")!="READ_ONLY_REMOVAL_PREVIEW"
            or preview.get("deletion_authorized") is not False
            or preview.get("project_id")=="codebridge"
            or not isinstance(preview.get("project_id"),str)
            or not isinstance(preview.get("selected_paths"),list)
            or not preview["selected_paths"]):
        raise DeletionLineageError("untrusted deletion preview")
    project=preview["project_id"]
    selected=preview["selected_paths"]
    if selected != sorted(set(selected)):
        raise DeletionLineageError("noncanonical selection")
    def inventory(location):
        path=Path(location)
        if not path.is_file() or path.is_symlink():
            raise DeletionLineageError("unavailable or redirected manifest")
        rows=load_index_manifest(path).entries
        if any(row.project_id!=project for row in rows):
            raise DeletionLineageError("foreign project in manifest")
        result={row.path:row for row in rows}
        if len(result)!=len(rows):
            raise DeletionLineageError("duplicate manifest source")
        return result
    old=inventory(baseline_manifest)
    new=inventory(candidate_manifest)
    if not set(selected)<=set(old) or set(new)!=set(old)-set(selected):
        raise DeletionLineageError("candidate diverged from selected removal")
    for path,entry in new.items():
        original=old[path]
        if (entry.sha256!=original.sha256
                or entry.index_kind!=original.index_kind
                or tuple(entry.chunk_ids)!=tuple(original.chunk_ids)
                or entry.model_version!=original.model_version
                or entry.size!=original.size):
            raise DeletionLineageError("preserved content changed")
    removed_chunks=sum(len(old[p].chunk_ids) for p in selected)
    kept_chunks=sum(len(entry.chunk_ids) for entry in new.values())
    if (removed_chunks!=preview.get("chunks_to_remove")
            or kept_chunks!=preview.get("chunks_to_preserve")
            or len(new)!=preview.get("documents_to_preserve")
            or len(selected)!=preview.get("documents_to_remove")):
        raise DeletionLineageError("preview count or generation drift")
    identity={
        "project_id":project,"baseline_generation":preview.get("generation"),
        "baseline_revision":preview.get("source_revision"),
        "selected_paths":selected,
        "survivor_paths":sorted(new),
        "survivor_chunks":kept_chunks,
        "preview_sha256":preview.get("review_sha256"),
    }
    digest=sha256(json.dumps(identity,sort_keys=True,ensure_ascii=False,separators=(",",":")).encode()).hexdigest()
    return {"state":"SURVIVOR_LINEAGE_VERIFIED","lineage_sha256":digest,
            "preserved_documents":len(new),"preserved_chunks":kept_chunks,
            "activation_authorized":False,"source_files_modified":False}
