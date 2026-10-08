"""Runtime orchestration helpers for the CodeBridge RAG layer.

Imports in this package must remain side effect free.
"""

from .errors import (
    RagPublicError,
    RagPublicErrorType,
    RagStaleResultError,
    classify_rag_error,
)
from .context_service import (
    GetContextResult,
    RagContextIndexUnavailableError,
    RagContextInvalidScopeError,
    RagContextSourceMissingError,
    RetrievedContext,
    get_context,
)
from .index_request import (
    RagIndexAction,
    RagIndexCandidate,
    RagIndexExecutionUnavailableError,
    RagIndexOperationResult,
    RagIndexPlan,
    RagIndexScope,
    plan_rag_index,
    run_explicit_rag_index,
)
from .model_manager import (
    ExclusiveModelManager,
    ManagedModel,
    ManagedRuntime,
    ModelManagerErrorType,
    ModelManagerOperation,
    ModelManagerOperationResult,
    ModelManagerSnapshot,
)
from .query_classifier import (
    QueryClassification,
    QueryRoute,
    classify_query,
)
from .search_service import (
    RagSearchContextResult,
    RagSearchIndexUnavailableError,
    search_context,
    search_result_to_dict,
    source_metadata_to_dict,
)
from .status import (
    ModelRuntimeStatus,
    RagStatusSnapshot,
    build_rag_status,
    resolve_rag_manifest_path,
    resolve_rag_sqlite_path,
    resolve_rag_state_directory,
)

__all__ = [
    "RagPublicError",
    "RagPublicErrorType",
    "RagStaleResultError",
    "classify_rag_error",
    "GetContextResult",
    "RagContextIndexUnavailableError",
    "RagContextInvalidScopeError",
    "RagContextSourceMissingError",
    "RetrievedContext",
    "get_context",
    "RagIndexAction",
    "RagIndexCandidate",
    "RagIndexExecutionUnavailableError",
    "RagIndexOperationResult",
    "RagIndexPlan",
    "RagIndexScope",
    "plan_rag_index",
    "run_explicit_rag_index",
    "ExclusiveModelManager",
    "ManagedModel",
    "ManagedRuntime",
    "ModelManagerErrorType",
    "ModelManagerOperation",
    "ModelManagerOperationResult",
    "ModelManagerSnapshot",
    "QueryClassification",
    "QueryRoute",
    "classify_query",
    "RagSearchContextResult",
    "RagSearchIndexUnavailableError",
    "search_context",
    "search_result_to_dict",
    "source_metadata_to_dict",
    "ModelRuntimeStatus",
    "RagStatusSnapshot",
    "build_rag_status",
    "resolve_rag_manifest_path",
    "resolve_rag_sqlite_path",
    "resolve_rag_state_directory",
]
