"""Source inventory helpers for CodeBridge RAG."""

from .code_inventory import (
    ALLOWED_CODE_EXTENSIONS,
    CodeSourceKind,
    classify_code_path,
    is_code_source,
)
from .document_inventory import (
    DocumentCategory,
    classify_document_path,
    is_document_source,
)
from .execution_inventory import (
    FORBIDDEN_EXECUTION_CONTENT_FIELDS,
    INDEXABLE_EXECUTION_FIELDS,
    SUMMARY_METADATA_FIELDS,
    build_execution_index_record,
)
from .exclusion_policy import (
    DenyReason,
    classify_denied_path,
    is_denied_path,
)
from .git_inventory import (
    GIT_FACET_FIELDS,
    READ_ONLY_GIT_OPERATIONS,
    GitFacet,
    fields_for_git_facet,
    is_read_only_git_operation,
)
from .git_state import (
    GitHeadState,
    GitStateError,
    attach_git_head_state_to_chunk,
    attach_git_head_state_to_metadata,
    capture_git_head_state,
)
from .git_provenance import (
    GitFileProvenance,
    GitProvenanceError,
    attach_git_provenance_to_chunk,
    attach_git_provenance_to_metadata,
    capture_git_file_provenance,
)
from .git_worktree import (
    GitPathState,
    GitPathStatus,
    GitWorktreeError,
    attach_git_path_state_to_chunk,
    attach_git_path_state_to_metadata,
    capture_git_path_state,
)
from .staleness import (
    StalenessEvaluation,
    StalenessStatus,
    evaluate_source_staleness,
    mark_search_result_staleness,
)

__all__ = [
    "ALLOWED_CODE_EXTENSIONS",
    "CodeSourceKind",
    "classify_code_path",
    "is_code_source",
    "DocumentCategory",
    "classify_document_path",
    "is_document_source",
    "FORBIDDEN_EXECUTION_CONTENT_FIELDS",
    "INDEXABLE_EXECUTION_FIELDS",
    "SUMMARY_METADATA_FIELDS",
    "build_execution_index_record",
    "DenyReason",
    "classify_denied_path",
    "is_denied_path",
    "GIT_FACET_FIELDS",
    "READ_ONLY_GIT_OPERATIONS",
    "GitFacet",
    "fields_for_git_facet",
    "is_read_only_git_operation",
    "GitHeadState",
    "GitStateError",
    "attach_git_head_state_to_chunk",
    "attach_git_head_state_to_metadata",
    "capture_git_head_state",
    "GitFileProvenance",
    "GitProvenanceError",
    "attach_git_provenance_to_chunk",
    "attach_git_provenance_to_metadata",
    "capture_git_file_provenance",
    "GitPathState",
    "GitPathStatus",
    "GitWorktreeError",
    "attach_git_path_state_to_chunk",
    "attach_git_path_state_to_metadata",
    "capture_git_path_state",
    "StalenessEvaluation",
    "StalenessStatus",
    "evaluate_source_staleness",
    "mark_search_result_staleness",
]
