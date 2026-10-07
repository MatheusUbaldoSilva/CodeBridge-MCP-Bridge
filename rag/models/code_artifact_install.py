"""Controlled installation for the pinned Jina Code GGUF — RAG-007-B."""

from __future__ import annotations

import os
from pathlib import Path
from typing import BinaryIO, Callable, Optional
from urllib.request import urlopen

from .artifact_install import (
    ModelInstallResult,
    install_verified_artifact,
)
from .code_backend_policy import (
    CODE_GGUF_REPOSITORY,
    SELECTED_CODE_BACKEND,
)


DEFAULT_CODE_MODEL_SUBDIR = Path(
    "CodeBridge",
    "models",
    "jina-code-embeddings-1.5b",
)


def resolve_code_model_directory(
    *,
    local_app_data: Optional[Path] = None,
) -> Path:
    root = local_app_data
    if root is None:
        value = os.environ.get("LOCALAPPDATA")
        if not value:
            raise RuntimeError(
                "LOCALAPPDATA is required to resolve the code model directory"
            )
        root = Path(value)

    revision = SELECTED_CODE_BACKEND.artifact_pin.revision
    if not revision:
        raise RuntimeError("selected code model artifact is not pinned")

    return (
        Path(root)
        / DEFAULT_CODE_MODEL_SUBDIR
        / revision
    )


def resolve_selected_code_model_path(
    *,
    local_app_data: Optional[Path] = None,
) -> Path:
    filename = SELECTED_CODE_BACKEND.artifact_pin.filename
    if not filename:
        raise RuntimeError("selected code model filename is not pinned")

    return (
        resolve_code_model_directory(
            local_app_data=local_app_data,
        )
        / filename
    )


def install_selected_code_model(
    *,
    allow_download: bool,
    license_acknowledged: bool,
    local_app_data: Optional[Path] = None,
    opener: Callable[..., BinaryIO] = urlopen,
    timeout_seconds: int = 600,
) -> ModelInstallResult:
    return install_verified_artifact(
        repository=CODE_GGUF_REPOSITORY,
        artifact=SELECTED_CODE_BACKEND.artifact_pin,
        destination=resolve_selected_code_model_path(
            local_app_data=local_app_data,
        ),
        allow_download=allow_download,
        license_acknowledged=license_acknowledged,
        opener=opener,
        timeout_seconds=timeout_seconds,
    )
