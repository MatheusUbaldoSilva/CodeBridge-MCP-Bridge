"""Vector storage backend selection policy — RAG-009-A.

Importing this module must not import a vector database package open storage
or start a local service.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Tuple


class VectorStorageBackend(str, Enum):
    QDRANT_LOCAL = "QDRANT_LOCAL"
    SQLITE_VEC = "SQLITE_VEC"
    LANCEDB_LOCAL = "LANCEDB_LOCAL"


class CandidateDecision(str, Enum):
    SELECTED = "SELECTED"
    REJECTED = "REJECTED"


@dataclass(frozen=True)
class VectorBackendEvaluation:
    backend: VectorStorageBackend
    decision: CandidateDecision
    stability_score: int
    size_score: int
    performance_score: int
    installation_score: int
    backup_score: int
    portability_score: int
    package_name: str
    observed_version: str
    observed_wheel_bytes: int
    wheel_measurement_excludes_dependencies: bool
    persisted_local_mode: bool
    requires_external_server: bool
    auto_install_allowed: bool
    rationale: str

    def __post_init__(self) -> None:
        if not isinstance(self.backend, VectorStorageBackend):
            raise ValueError("backend must be VectorStorageBackend")
        if not isinstance(self.decision, CandidateDecision):
            raise ValueError("decision must be CandidateDecision")
        for field_name in (
            "stability_score",
            "size_score",
            "performance_score",
            "installation_score",
            "backup_score",
            "portability_score",
        ):
            score = int(getattr(self, field_name))
            if score < 1 or score > 5:
                raise ValueError(f"{field_name} must be between 1 and 5")
        if not self.package_name.strip():
            raise ValueError("package_name must be non-empty")
        if not self.observed_version.strip():
            raise ValueError("observed_version must be non-empty")
        if self.observed_wheel_bytes < 1:
            raise ValueError("observed_wheel_bytes must be >= 1")
        if not self.rationale.strip():
            raise ValueError("rationale must be non-empty")


VECTOR_BACKEND_EVALUATIONS: Tuple[VectorBackendEvaluation, ...] = (
    VectorBackendEvaluation(
        backend=VectorStorageBackend.QDRANT_LOCAL,
        decision=CandidateDecision.SELECTED,
        stability_score=4,
        size_score=4,
        performance_score=3,
        installation_score=5,
        backup_score=3,
        portability_score=4,
        package_name="qdrant-client",
        observed_version="1.19.1",
        observed_wheel_bytes=406533,
        wheel_measurement_excludes_dependencies=True,
        persisted_local_mode=True,
        requires_external_server=False,
        auto_install_allowed=False,
        rationale=(
            "Selected for the first local CodeBridge vector index because the "
            "official Python client supports persistent on-disk local mode "
            "without a Qdrant server while preserving a migration path to the "
            "server API. Scope remains a local single-user corpus."
        ),
    ),
    VectorBackendEvaluation(
        backend=VectorStorageBackend.SQLITE_VEC,
        decision=CandidateDecision.REJECTED,
        stability_score=2,
        size_score=5,
        performance_score=3,
        installation_score=5,
        backup_score=5,
        portability_score=5,
        package_name="sqlite-vec",
        observed_version="0.1.9",
        observed_wheel_bytes=292804,
        wheel_measurement_excludes_dependencies=True,
        persisted_local_mode=True,
        requires_external_server=False,
        auto_install_allowed=False,
        rationale=(
            "Excellent footprint and SQLite alignment but the upstream project "
            "still documents itself as pre-v1 with expected breaking changes. "
            "That conflicts with the stability requirement for the frozen "
            "CodeBridge vector index contract."
        ),
    ),
    VectorBackendEvaluation(
        backend=VectorStorageBackend.LANCEDB_LOCAL,
        decision=CandidateDecision.REJECTED,
        stability_score=4,
        size_score=1,
        performance_score=5,
        installation_score=3,
        backup_score=4,
        portability_score=5,
        package_name="lancedb",
        observed_version="0.40.0",
        observed_wheel_bytes=83389723,
        wheel_measurement_excludes_dependencies=True,
        persisted_local_mode=True,
        requires_external_server=False,
        auto_install_allowed=False,
        rationale=(
            "Strong embedded local storage and portability but the observed "
            "Windows wheel alone is much larger than the other candidates. "
            "For the CodeBridge desktop runtime this phase prioritizes a "
            "smaller initial integration surface."
        ),
    ),
)


SELECTED_VECTOR_BACKEND = VectorStorageBackend.QDRANT_LOCAL
SELECTED_VECTOR_PACKAGE = "qdrant-client"
SELECTED_VECTOR_PACKAGE_VERSION = "1.19.1"
VECTOR_BACKEND_AUTO_INSTALL_ALLOWED = False
VECTOR_BACKEND_EXTERNAL_SERVER_REQUIRED = False
VECTOR_BACKEND_PERSISTED_LOCAL_MODE = True
VECTOR_BACKEND_SCOPE = "LOCAL_SINGLE_USER"


def selected_vector_backend_evaluation() -> VectorBackendEvaluation:
    matches = tuple(
        item
        for item in VECTOR_BACKEND_EVALUATIONS
        if item.decision is CandidateDecision.SELECTED
    )
    if len(matches) != 1:
        raise RuntimeError("vector backend policy must contain exactly one selection")
    selected = matches[0]
    if selected.backend is not SELECTED_VECTOR_BACKEND:
        raise RuntimeError("selected vector backend constants are inconsistent")
    return selected
