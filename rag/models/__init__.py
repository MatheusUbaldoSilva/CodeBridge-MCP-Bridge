"""Model lifecycle and backend policy for CodeBridge RAG.

Importing this package must remain side-effect free.
"""

from .backend_policy import (
    BACKEND_EVALUATIONS,
    SELECTED_TEXT_BACKEND,
    TEXT_MODEL_FAMILY,
    TEXT_MODEL_LICENSE,
    TEXT_RETRIEVAL_REPOSITORY,
    BackendEvaluation,
    DistributionMode,
    InferenceBackend,
    ModelArtifactPin,
    TextEmbeddingBackendPolicy,
    selected_backend_evaluation,
)

__all__ = [
    "BACKEND_EVALUATIONS",
    "SELECTED_TEXT_BACKEND",
    "TEXT_MODEL_FAMILY",
    "TEXT_MODEL_LICENSE",
    "TEXT_RETRIEVAL_REPOSITORY",
    "BackendEvaluation",
    "DistributionMode",
    "InferenceBackend",
    "ModelArtifactPin",
    "TextEmbeddingBackendPolicy",
    "selected_backend_evaluation",
]
