"""Project namespace contract for the vector index — RAG-009-C.

Namespaces isolate project payloads inside the shared text and code collections.

This module validates namespace identifiers and builds Qdrant payload filters
without opening storage or loading a model.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Mapping


PROJECT_NAMESPACE_PAYLOAD_KEY = "project_namespace"
PROJECT_NAMESPACE_PATTERN = re.compile(
    r"^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$"
)

EXAMPLE_PROJECT_NAMESPACES = (
    "codebridge",
    "new-world-pvp",
    "drones",
    "outros",
)


@dataclass(frozen=True)
class ProjectNamespace:
    value: str

    def __post_init__(self) -> None:
        require_project_namespace(self.value)

    def as_payload(self) -> dict[str, str]:
        return {PROJECT_NAMESPACE_PAYLOAD_KEY: self.value}


def require_project_namespace(project_id: str) -> str:
    if not isinstance(project_id, str):
        raise ValueError("project_id must be a string")
    if not project_id:
        raise ValueError("project_id must not be empty")
    if project_id != project_id.strip():
        raise ValueError("project_id must not contain surrounding whitespace")
    if not PROJECT_NAMESPACE_PATTERN.fullmatch(project_id):
        raise ValueError(
            "project_id must be a canonical lowercase namespace using "
            "letters digits and hyphens with length 1..64"
        )
    if "--" in project_id:
        raise ValueError("project_id must not contain consecutive hyphens")
    return project_id


def vector_payload_with_namespace(
    project_id: str,
    payload: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    namespace = require_project_namespace(project_id)
    result = dict(payload or {})

    existing = result.get(PROJECT_NAMESPACE_PAYLOAD_KEY)
    if existing is not None and existing != namespace:
        raise ValueError(
            "payload project_namespace conflicts with project_id"
        )

    result[PROJECT_NAMESPACE_PAYLOAD_KEY] = namespace
    return result


def build_project_namespace_filter(project_id: str) -> Any:
    namespace = require_project_namespace(project_id)

    try:
        from qdrant_client import models
    except Exception as exc:
        raise RuntimeError(
            "qdrant-client is required to build a namespace filter"
        ) from exc

    return models.Filter(
        must=[
            models.FieldCondition(
                key=PROJECT_NAMESPACE_PAYLOAD_KEY,
                match=models.MatchValue(value=namespace),
            )
        ]
    )
