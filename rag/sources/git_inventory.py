"""Git source inventory contract for RAG-002-C.

This module defines which Git facets may become RAG context.
It performs no Git command, repository mutation, indexing, or model loading.
"""

from __future__ import annotations

from enum import Enum
from typing import Tuple


class GitFacet(str, Enum):
    BRANCH = "BRANCH"
    HEAD = "HEAD"
    COMMIT = "COMMIT"
    MESSAGE = "MESSAGE"
    FILE = "FILE"
    DIFF = "DIFF"
    HISTORY = "HISTORY"


GIT_FACET_FIELDS = {
    GitFacet.BRANCH: (
        "repository",
        "branch",
        "detached",
    ),
    GitFacet.HEAD: (
        "repository",
        "head_commit",
    ),
    GitFacet.COMMIT: (
        "repository",
        "commit",
        "parent_commits",
        "authored_at",
        "committed_at",
    ),
    GitFacet.MESSAGE: (
        "repository",
        "commit",
        "message",
    ),
    GitFacet.FILE: (
        "repository",
        "commit",
        "path",
        "change_type",
        "blob_sha",
    ),
    GitFacet.DIFF: (
        "repository",
        "base_commit",
        "head_commit",
        "path",
        "patch",
    ),
    GitFacet.HISTORY: (
        "repository",
        "scope",
        "commit_refs",
    ),
}


READ_ONLY_GIT_OPERATIONS = frozenset({
    "status",
    "branch-show-current",
    "rev-parse",
    "log",
    "show",
    "diff",
})


def fields_for_git_facet(facet: GitFacet) -> Tuple[str, ...]:
    if not isinstance(facet, GitFacet):
        raise ValueError("facet must be a GitFacet")
    return GIT_FACET_FIELDS[facet]


def is_read_only_git_operation(operation: str) -> bool:
    value = str(operation or "").strip().lower()
    return value in READ_ONLY_GIT_OPERATIONS
