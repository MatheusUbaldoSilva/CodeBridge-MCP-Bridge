"""Controlled model artifact installation for RAG-006-B.

No download occurs on import.
Every network download requires explicit caller authorization and license
acknowledgement. The final file is published only after size and SHA-256
verification.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
from typing import BinaryIO, Callable, Optional
from urllib.request import urlopen

from .backend_policy import (
    ModelArtifactPin,
    SELECTED_TEXT_BACKEND,
    TEXT_RETRIEVAL_REPOSITORY,
)


DEFAULT_MODEL_SUBDIR = Path(
    "CodeBridge",
    "models",
    "jina-v5-text-small-retrieval",
)


class ModelDownloadConsentError(PermissionError):
    pass


class ModelArtifactIntegrityError(RuntimeError):
    pass


@dataclass(frozen=True)
class ArtifactVerification:
    path: Path
    exists: bool
    valid: bool
    size_bytes: Optional[int]
    sha256: Optional[str]


@dataclass(frozen=True)
class ModelInstallResult:
    path: Path
    downloaded: bool
    size_bytes: int
    sha256: str
    revision: str
    filename: str


def build_huggingface_artifact_url(
    repository: str,
    artifact: ModelArtifactPin,
) -> str:
    if not repository or "/" not in repository:
        raise ValueError("repository must be owner/name")
    if not artifact.is_fully_pinned:
        raise ValueError("artifact must be fully pinned")

    return (
        f"https://huggingface.co/{repository}/resolve/"
        f"{artifact.revision}/{artifact.filename}?download=true"
    )


def resolve_model_directory(
    *,
    local_app_data: Optional[Path] = None,
) -> Path:
    root: Optional[Path] = local_app_data
    if root is None:
        value = os.environ.get("LOCALAPPDATA")
        if not value:
            raise RuntimeError(
                "LOCALAPPDATA is required to resolve the model directory"
            )
        root = Path(value)

    artifact = SELECTED_TEXT_BACKEND.artifact_pin
    if not artifact.revision:
        raise RuntimeError("selected model artifact is not pinned")

    return (
        Path(root)
        / DEFAULT_MODEL_SUBDIR
        / artifact.revision
    )


def resolve_selected_model_path(
    *,
    local_app_data: Optional[Path] = None,
) -> Path:
    artifact = SELECTED_TEXT_BACKEND.artifact_pin
    if not artifact.filename:
        raise RuntimeError("selected model filename is not pinned")
    return (
        resolve_model_directory(
            local_app_data=local_app_data,
        )
        / artifact.filename
    )


def verify_model_artifact(
    path: Path,
    artifact: ModelArtifactPin,
    *,
    chunk_size: int = 1024 * 1024,
) -> ArtifactVerification:
    candidate = Path(path)
    if chunk_size < 1:
        raise ValueError("chunk_size must be >= 1")
    if not artifact.is_fully_pinned:
        raise ValueError("artifact must be fully pinned")

    if not candidate.is_file():
        return ArtifactVerification(
            path=candidate,
            exists=False,
            valid=False,
            size_bytes=None,
            sha256=None,
        )

    size = candidate.stat().st_size
    digest = hashlib.sha256()

    with candidate.open("rb") as handle:
        while True:
            block = handle.read(chunk_size)
            if not block:
                break
            digest.update(block)

    sha256 = digest.hexdigest()
    valid = (
        size == artifact.size_bytes
        and sha256 == artifact.sha256
    )

    return ArtifactVerification(
        path=candidate,
        exists=True,
        valid=valid,
        size_bytes=size,
        sha256=sha256,
    )


def _copy_stream_verified(
    source: BinaryIO,
    destination: Path,
    artifact: ModelArtifactPin,
    *,
    chunk_size: int,
) -> ArtifactVerification:
    digest = hashlib.sha256()
    written = 0

    with destination.open("wb") as handle:
        while True:
            block = source.read(chunk_size)
            if not block:
                break

            written += len(block)
            if written > artifact.size_bytes:
                raise ModelArtifactIntegrityError(
                    "download exceeded the pinned artifact size"
                )

            digest.update(block)
            handle.write(block)

        handle.flush()
        os.fsync(handle.fileno())

    sha256 = digest.hexdigest()
    valid = (
        written == artifact.size_bytes
        and sha256 == artifact.sha256
    )
    if not valid:
        raise ModelArtifactIntegrityError(
            "downloaded artifact failed size or SHA-256 verification"
        )

    return ArtifactVerification(
        path=destination,
        exists=True,
        valid=True,
        size_bytes=written,
        sha256=sha256,
    )


def install_verified_artifact(
    *,
    repository: str,
    artifact: ModelArtifactPin,
    destination: Path,
    allow_download: bool,
    license_acknowledged: bool,
    opener: Callable[..., BinaryIO] = urlopen,
    timeout_seconds: int = 120,
    chunk_size: int = 1024 * 1024,
) -> ModelInstallResult:
    """Install one pinned artifact atomically.

    Existing valid files are reused without network access.
    Existing invalid files are never overwritten silently.
    """

    target = Path(destination)

    existing = verify_model_artifact(
        target,
        artifact,
        chunk_size=chunk_size,
    )
    if existing.valid:
        return ModelInstallResult(
            path=target,
            downloaded=False,
            size_bytes=int(existing.size_bytes),
            sha256=str(existing.sha256),
            revision=str(artifact.revision),
            filename=str(artifact.filename),
        )
    if existing.exists:
        raise ModelArtifactIntegrityError(
            "existing model artifact does not match the pinned manifest"
        )

    if not allow_download:
        raise ModelDownloadConsentError(
            "model download requires explicit allow_download=True"
        )
    if not license_acknowledged:
        raise ModelDownloadConsentError(
            "model license must be acknowledged before download"
        )
    if timeout_seconds < 1:
        raise ValueError("timeout_seconds must be >= 1")
    if chunk_size < 1:
        raise ValueError("chunk_size must be >= 1")

    url = build_huggingface_artifact_url(
        repository,
        artifact,
    )
    target.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    partial = target.with_name(
        target.name + ".partial"
    )

    if partial.exists():
        partial.unlink()

    try:
        with opener(
            url,
            timeout=timeout_seconds,
        ) as response:
            verification = _copy_stream_verified(
                response,
                partial,
                artifact,
                chunk_size=chunk_size,
            )

        os.replace(
            partial,
            target,
        )
    except Exception:
        if partial.exists():
            partial.unlink()
        raise

    return ModelInstallResult(
        path=target,
        downloaded=True,
        size_bytes=int(verification.size_bytes),
        sha256=str(verification.sha256),
        revision=str(artifact.revision),
        filename=str(artifact.filename),
    )


def install_selected_text_model(
    *,
    allow_download: bool,
    license_acknowledged: bool,
    local_app_data: Optional[Path] = None,
    opener: Callable[..., BinaryIO] = urlopen,
) -> ModelInstallResult:
    artifact = SELECTED_TEXT_BACKEND.artifact_pin
    return install_verified_artifact(
        repository=TEXT_RETRIEVAL_REPOSITORY,
        artifact=artifact,
        destination=resolve_selected_model_path(
            local_app_data=local_app_data,
        ),
        allow_download=allow_download,
        license_acknowledged=license_acknowledged,
        opener=opener,
    )
