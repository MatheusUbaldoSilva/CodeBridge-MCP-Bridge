"""Create a merged RAG manifest in a NEW destination; never publish it."""
from pathlib import Path
from rag.index.manifest import IndexManifest, load_index_manifest, save_index_manifest


class IncrementalManifestError(RuntimeError):
    pass


def stage_incremental_manifest(existing, incoming, destination, project_id):
    original = Path(existing).resolve()
    addition = Path(incoming).resolve()
    output = Path(destination).resolve()
    if len({original, addition, output}) != 3 or output.exists():
        raise IncrementalManifestError("destination must be new and distinct")
    if not original.is_file() or not addition.is_file():
        raise IncrementalManifestError("both manifests are required")
    previous = load_index_manifest(original)
    staged = load_index_manifest(addition)
    if not staged.entries or any(item.project_id != project_id for item in staged.entries):
        raise IncrementalManifestError("staged manifest must contain only the requested project")
    merged = previous
    replaced = 0
    for entry in staged.entries:
        if merged.get(entry.project_id, entry.index_kind, entry.path) is not None:
            replaced += 1
        merged = merged.upsert(entry)
    save_index_manifest(output, merged)
    if load_index_manifest(output) != merged:
        output.unlink(missing_ok=True)
        raise IncrementalManifestError("merged manifest verification failed")
    return {
        "state": "MANIFEST_STAGED_NOT_PUBLISHED",
        "added": len(staged.entries) - replaced,
        "replaced": replaced,
        "total": len(merged.entries),
        "destination": str(output),
    }
