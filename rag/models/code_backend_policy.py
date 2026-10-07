"""Backend contract for Jina Code Embeddings 1.5B — RAG-007-A.

Importing this module has no network, model-download, or process side effects.
The exact downloadable GGUF artifact is intentionally NOT pinned in RAG-007-A.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
import subprocess
from typing import Callable, Mapping, Optional, Tuple

from .backend_policy import (
    DistributionMode,
    InferenceBackend,
    ModelArtifactPin,
)


CODE_MODEL_FAMILY = "jinaai/jina-code-embeddings-1.5b"
CODE_GGUF_REPOSITORY = "jinaai/jina-code-embeddings-1.5b-GGUF"
CODE_BASE_MODEL = "Qwen/Qwen2.5-Coder-1.5B"
CODE_MODEL_LICENSE = "CC-BY-NC-4.0"

CODE_REFERENCE_EMBEDDING_DIMENSION = 1536
CODE_LLAMA_CPP_DOCUMENTED_DIMENSION = 896
CODE_MAX_CONTEXT_TOKENS = 32768
CODE_RECOMMENDED_CONTEXT_TOKENS = 8192
CODE_RECOMMENDED_UBATCH_SIZE = 8192

REQUIRED_LLAMA_CPP_CODE_FLAGS: Tuple[str, ...] = (
    "--embedding",
    "--pooling",
    "--ctx-size",
    "--ubatch-size",
    "--hf-repo",
    "--hf-file",
    "--device",
    "--gpu-layers",
)


class CodeRetrievalTask(str, Enum):
    NL2CODE = "nl2code"
    QA = "qa"
    CODE2CODE = "code2code"
    CODE2NL = "code2nl"
    CODE2COMPLETION = "code2completion"


@dataclass(frozen=True)
class CodeTaskInstruction:
    query_prefix: str
    passage_prefix: str

    def __post_init__(self) -> None:
        if not self.query_prefix:
            raise ValueError("query_prefix must be non-empty")
        if not self.passage_prefix:
            raise ValueError("passage_prefix must be non-empty")


CODE_TASK_INSTRUCTIONS: Mapping[
    CodeRetrievalTask,
    CodeTaskInstruction,
] = {
    CodeRetrievalTask.NL2CODE: CodeTaskInstruction(
        query_prefix=(
            "Find the most relevant code snippet given the following query:\n"
        ),
        passage_prefix="Candidate code snippet:\n",
    ),
    CodeRetrievalTask.QA: CodeTaskInstruction(
        query_prefix=(
            "Find the most relevant answer given the following question:\n"
        ),
        passage_prefix="Candidate answer:\n",
    ),
    CodeRetrievalTask.CODE2CODE: CodeTaskInstruction(
        query_prefix=(
            "Find an equivalent code snippet given the following code snippet:\n"
        ),
        passage_prefix="Candidate code snippet:\n",
    ),
    CodeRetrievalTask.CODE2NL: CodeTaskInstruction(
        query_prefix=(
            "Find the most relevant comment given the following code snippet:\n"
        ),
        passage_prefix="Candidate comment:\n",
    ),
    CodeRetrievalTask.CODE2COMPLETION: CodeTaskInstruction(
        query_prefix=(
            "Find the most relevant completion given the following start "
            "of code snippet:\n"
        ),
        passage_prefix="Candidate completion:\n",
    ),
}


@dataclass(frozen=True)
class CodeEmbeddingBackendPolicy:
    backend: InferenceBackend
    distribution_mode: DistributionMode
    model_family: str
    model_repository: str
    base_model: str
    artifact_format: str
    transport: str
    host: str
    embeddings_endpoint: str
    health_endpoint: str
    pooling: str
    max_context_tokens: int
    recommended_context_tokens: int
    recommended_ubatch_size: int
    reference_embedding_dimension: int
    llama_cpp_documented_dimension: int
    dimension_probe_required: bool
    gpu_preferred: bool
    cpu_fallback_required: bool
    windows_required: bool
    auto_download_allowed: bool
    model_bundling_allowed: bool
    model_license: str
    commercial_license_review_required: bool
    artifact_pin: ModelArtifactPin

    def __post_init__(self) -> None:
        if self.backend is not InferenceBackend.LLAMA_CPP_HTTP:
            raise ValueError("RAG-007-A currently selects LLAMA_CPP_HTTP")
        if self.distribution_mode is not DistributionMode.BUNDLED_SIDECAR:
            raise ValueError("code model must use bundled sidecar mode")
        for field_name in (
            "model_family",
            "model_repository",
            "base_model",
            "artifact_format",
            "transport",
            "host",
            "embeddings_endpoint",
            "health_endpoint",
            "pooling",
            "model_license",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value:
                raise ValueError(f"{field_name} must be non-empty")
        for field_name in (
            "max_context_tokens",
            "recommended_context_tokens",
            "recommended_ubatch_size",
            "reference_embedding_dimension",
            "llama_cpp_documented_dimension",
        ):
            if int(getattr(self, field_name)) < 1:
                raise ValueError(f"{field_name} must be >= 1")
        if self.recommended_context_tokens > self.max_context_tokens:
            raise ValueError(
                "recommended_context_tokens cannot exceed max_context_tokens"
            )
        if not isinstance(self.artifact_pin, ModelArtifactPin):
            raise ValueError("artifact_pin must be ModelArtifactPin")


SELECTED_CODE_BACKEND = CodeEmbeddingBackendPolicy(
    backend=InferenceBackend.LLAMA_CPP_HTTP,
    distribution_mode=DistributionMode.BUNDLED_SIDECAR,
    model_family=CODE_MODEL_FAMILY,
    model_repository=CODE_GGUF_REPOSITORY,
    base_model=CODE_BASE_MODEL,
    artifact_format="GGUF",
    transport="HTTP_OPENAI_COMPATIBLE",
    host="127.0.0.1",
    embeddings_endpoint="/v1/embeddings",
    health_endpoint="/health",
    pooling="last",
    max_context_tokens=CODE_MAX_CONTEXT_TOKENS,
    recommended_context_tokens=CODE_RECOMMENDED_CONTEXT_TOKENS,
    recommended_ubatch_size=CODE_RECOMMENDED_UBATCH_SIZE,
    reference_embedding_dimension=CODE_REFERENCE_EMBEDDING_DIMENSION,
    llama_cpp_documented_dimension=CODE_LLAMA_CPP_DOCUMENTED_DIMENSION,
    dimension_probe_required=True,
    gpu_preferred=True,
    cpu_fallback_required=True,
    windows_required=True,
    auto_download_allowed=False,
    model_bundling_allowed=False,
    model_license=CODE_MODEL_LICENSE,
    commercial_license_review_required=True,
    artifact_pin=ModelArtifactPin(
        download_allowed=False,
    ),
)


@dataclass(frozen=True)
class LlamaCppCodeBackendProbe:
    executable_path: Path
    version_text: str
    supported_flags: Tuple[str, ...]
    missing_flags: Tuple[str, ...]

    @property
    def compatible(self) -> bool:
        return not self.missing_flags


Runner = Callable[..., subprocess.CompletedProcess]


def probe_llama_cpp_code_backend(
    executable_path: Path,
    *,
    runner: Runner = subprocess.run,
    timeout_seconds: float = 15.0,
) -> LlamaCppCodeBackendProbe:
    path = Path(executable_path)
    if not path.is_file():
        raise RuntimeError("llama-server executable does not exist")
    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be > 0")

    common = dict(
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        shell=False,
    )

    try:
        version = runner(
            [str(path), "--version"],
            **common,
        )
        help_result = runner(
            [str(path), "--help"],
            **common,
        )
    except Exception as exc:
        raise RuntimeError(
            f"llama.cpp backend probe failed: {exc}"
        ) from exc

    if int(version.returncode) != 0:
        raise RuntimeError(
            "llama.cpp --version failed "
            f"(exit_code={version.returncode})"
        )
    if int(help_result.returncode) != 0:
        raise RuntimeError(
            "llama.cpp --help failed "
            f"(exit_code={help_result.returncode})"
        )

    version_text = (
        (version.stdout or "")
        + "\n"
        + (version.stderr or "")
    ).strip()
    help_text = (
        (help_result.stdout or "")
        + "\n"
        + (help_result.stderr or "")
    )

    supported = tuple(
        flag
        for flag in REQUIRED_LLAMA_CPP_CODE_FLAGS
        if flag in help_text
    )
    missing = tuple(
        flag
        for flag in REQUIRED_LLAMA_CPP_CODE_FLAGS
        if flag not in help_text
    )

    return LlamaCppCodeBackendProbe(
        executable_path=path,
        version_text=version_text,
        supported_flags=supported,
        missing_flags=missing,
    )
