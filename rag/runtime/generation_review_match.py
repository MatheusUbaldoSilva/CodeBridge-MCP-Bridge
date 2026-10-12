"""Read-only approval-to-generation check for isolated test generations.

Fail closed unless every changed document belongs to the reviewed file set.
Does not switch pointers, create backups, or touch production.
"""
from pathlib import Path

from rag.index.manifest import load_index_manifest
from rag.runtime.generation_transition_journal import _test_root
from rag.runtime.incremental_bundle_validate import validate_incremental_bundle
from rag.runtime.incremental_review_contract import verify_review_contract


class GenerationReviewMismatch(ValueError):
    pass


def validate_generation_against_review(root, previous, candidate, snapshot,
                                       project, folder, review_contract):
    test_root = _test_root(root)
    reviewed = verify_review_contract(snapshot, project, folder, review_contract)
    generations = (test_root / "generations").resolve()
    directories = []
    for name in (previous, candidate):
        if not isinstance(name, str) or not name.isidentifier():
            raise GenerationReviewMismatch("unsafe generation identifier")
        directory = (generations / name).resolve()
        if directory.parent != generations or not directory.is_dir():
            raise GenerationReviewMismatch("generation unavailable")
        directories.append(directory)
    if directories[0] == directories[1]:
        raise GenerationReviewMismatch("generation must change")
    for directory in directories:
        validate_incremental_bundle(directory)
    old = load_index_manifest(directories[0] / "rag-index-manifest.json")
    new = load_index_manifest(directories[1] / "rag-index-manifest.json")
    old_entries = {(e.project_id, e.index_kind, e.path): e for e in old.entries}
    new_entries = {(e.project_id, e.index_kind, e.path): e for e in new.entries}
    if old_entries.keys() - new_entries.keys():
        raise GenerationReviewMismatch("candidate removed indexed documents")
    reviewed_hashes = snapshot["sha256"]
    candidate_paths = {}
    changed = set()
    for key, entry in new_entries.items():
        preceding = old_entries.get(key)
        if entry.project_id != project:
            if entry != preceding:
                raise GenerationReviewMismatch("other project was modified")
            continue
        if entry.path in candidate_paths:
            raise GenerationReviewMismatch("duplicate file path in selected project")
        candidate_paths[entry.path] = entry.sha256
        if entry != preceding:
            changed.add(entry.path)
    if changed == set():
        raise GenerationReviewMismatch("candidate has no reviewed changes")
    if not changed.issubset(reviewed_hashes):
        raise GenerationReviewMismatch("candidate contains unreviewed changes")
    if any(candidate_paths.get(path) != digest for path, digest in reviewed_hashes.items()):
        raise GenerationReviewMismatch("candidate does not match reviewed file hashes")
    verify_review_contract(snapshot, project, folder, review_contract)
    return {"state": "TEST_CANDIDATE_MATCHES_REVIEW_NOT_PUBLISHED",
            "project": project, "review_sha256": reviewed["review_sha256"],
            "reviewed_files": reviewed["files_checked"],
            "changed_files": len(changed)}
