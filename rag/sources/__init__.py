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
]
