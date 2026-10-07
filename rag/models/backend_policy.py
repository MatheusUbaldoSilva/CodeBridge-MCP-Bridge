"""Inference backend decision for Jina v5 text retrieval — RAG-006-A.

This module is policy only.
Importing it must not discover hardware, start a process, open a socket,
install a package, or download a model.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple


class InferenceBackend(str, Enum):
    LLAMA_CPP_HTTP = "LLAMA_CPP_HTTP"
    PYTORCH_SENTENCE_TRANSFORMERS = "PYTORCH_SENTENCE_TRANSFORMERS"
    ONNX_RUNTIME_OPTIMUM = "ONNX_RUNTIME_OPTIMUM"


class DistributionMode(str, Enum):
    BUNDLED_SIDECAR = "BUNDLED_SIDECAR"
    PYTHON_ENVIRONMENT = "PYTHON_ENVIRONMENT"


@dataclass(frozen=True)
class BackendEvaluation:
    backend: InferenceBackend
    gpu_supported: bool
    cpu_supported: bool
    windows_supported: bool
    distributable_with_codebridge: bool
    requires_python_ml_stack: bool
    selected: bool
    rationale: str

    def __post_init__(self) -> None:
        if not isinstance(self.backend, InferenceBackend):
            raise ValueError("backend must be InferenceBackend")
        if not isinstance(self.rationale, str) or not self.rationale.strip():
            raise ValueError("rationale must be non-empty")


@dataclass(frozen=True)
class ModelArtifactPin:
    revision: Optional[str] = None
    filename: Optional[str] = None
    sha256: Optional[str] = None
    size_bytes: Optional[int] = None
    download_allowed: bool = False

    def __post_init__(self) -> None:
        if self.size_bytes is not None and self.size_bytes < 1:
            raise ValueError("size_bytes must be >= 1 when provided")
        if self.sha256 is not None and len(self.sha256) != 64:
            raise ValueError("sha256 must contain exactly 64 characters")


@dataclass(frozen=True)
class TextEmbeddingBackendPolicy:
    backend: InferenceBackend
    distribution_mode: DistributionMode
    model_family: str
    model_repository: str
    task: str
    artifact_format: str
    transport: str
    host: str
    embeddings_endpoint: str
    health_endpoint: str
    pooling: str
    query_prefix: str
    document_prefix: str
    gpu_preferred: bool
    cpu_fallback_required: bool
    windows_required: bool
    auto_download_allowed: bool
    model_bundling_allowed: bool
    model_license: str
    commercial_license_review_required: bool
    artifact_pin: ModelArtifactPin

    def __post_init__(self) -> None:
        if not isinstance(self.backend, InferenceBackend):
            raise ValueError("backend must be InferenceBackend")
        if not isinstance(self.distribution_mode, DistributionMode):
            raise ValueError("distribution_mode must be DistributionMode")
        for field_name in (
            "model_family",
            "model_repository",
            "task",
            "artifact_format",
            "transport",
            "host",
            "embeddings_endpoint",
            "health_endpoint",
            "pooling",
            "query_prefix",
            "document_prefix",
            "model_license",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value:
                raise ValueError(f"{field_name} must be non-empty")
        if not isinstance(self.artifact_pin, ModelArtifactPin):
            raise ValueError("artifact_pin must be ModelArtifactPin")


TEXT_MODEL_FAMILY = "jinaai/jina-embeddings-v5-text-small"
TEXT_RETRIEVAL_REPOSITORY = (
    "jinaai/jina-embeddings-v5-text-small-retrieval"
)
TEXT_MODEL_LICENSE = "CC-BY-NC-4.0"

BACKEND_EVALUATIONS: Tuple[BackendEvaluation, ...] = (
    BackendEvaluation(
        backend=InferenceBackend.LLAMA_CPP_HTTP,
        gpu_supported=True,
        cpu_supported=True,
        windows_supported=True,
        distributable_with_codebridge=True,
        requires_python_ml_stack=False,
        selected=True,
        rationale=(
            "Official Jina retrieval GGUF support plus llama.cpp local HTTP "
            "embeddings keeps inference outside the CodeBridge Python runtime, "
            "supports CPU/GPU execution, and fits a bundled Windows sidecar."
        ),
    ),
    BackendEvaluation(
        backend=InferenceBackend.PYTORCH_SENTENCE_TRANSFORMERS,
        gpu_supported=True,
        cpu_supported=True,
        windows_supported=True,
        distributable_with_codebridge=True,
        requires_python_ml_stack=True,
        selected=False,
        rationale=(
            "Official model path and strongest reference implementation, "
            "but it adds torch, transformers, PEFT and optional "
            "sentence-transformers to the application environment."
        ),
    ),
    BackendEvaluation(
        backend=InferenceBackend.ONNX_RUNTIME_OPTIMUM,
        gpu_supported=True,
        cpu_supported=True,
        windows_supported=True,
        distributable_with_codebridge=True,
        requires_python_ml_stack=True,
        selected=False,
        rationale=(
            "Official task-specific ONNX artifacts are available, but the "
            "Optimum path adds provider and CUDA/cuDNN packaging complexity "
            "without a clear advantage before benchmarking."
        ),
    ),
)


SELECTED_TEXT_BACKEND = TextEmbeddingBackendPolicy(
    backend=InferenceBackend.LLAMA_CPP_HTTP,
    distribution_mode=DistributionMode.BUNDLED_SIDECAR,
    model_family=TEXT_MODEL_FAMILY,
    model_repository=TEXT_RETRIEVAL_REPOSITORY,
    task="retrieval",
    artifact_format="GGUF",
    transport="HTTP_OPENAI_COMPATIBLE",
    host="127.0.0.1",
    embeddings_endpoint="/v1/embeddings",
    health_endpoint="/health",
    pooling="last",
    query_prefix="Query: ",
    document_prefix="Document: ",
    gpu_preferred=True,
    cpu_fallback_required=True,
    windows_required=True,
    auto_download_allowed=False,
    model_bundling_allowed=False,
    model_license=TEXT_MODEL_LICENSE,
    commercial_license_review_required=True,
    artifact_pin=ModelArtifactPin(),
)


def selected_backend_evaluation() -> BackendEvaluation:
    selected = tuple(
        item
        for item in BACKEND_EVALUATIONS
        if item.selected
    )
    if len(selected) != 1:
        raise RuntimeError(
            "exactly one inference backend must be selected"
        )
    return selected[0]
