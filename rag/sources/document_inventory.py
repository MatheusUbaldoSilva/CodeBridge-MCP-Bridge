"""Deterministic document-source classification for RAG-002-A.

This module only classifies repository-style paths.
It does not read files, index content, create chunks, load models, or execute shell.
"""

from __future__ import annotations

from enum import Enum
from pathlib import PurePosixPath
import re
from typing import Optional


class DocumentCategory(str, Enum):
    README = "README"
    DOCUMENTATION = "DOCUMENTATION"
    HANDOFF = "HANDOFF"
    ROADMAP = "ROADMAP"
    PATCH_NOTE = "PATCH_NOTE"
    AUDIT = "AUDIT"


_MARKDOWN_EXTENSIONS = {".md", ".markdown", ".rst", ".adoc"}
_TEXT_EXTENSIONS = {".txt"}

_DEPENDENCY_MANIFEST_NAMES = {
    "requirements.txt",
}

_PATCH_RE = re.compile(
    r"(?:^|[_\-. ])PATCH(?:[_\-. ]?NOTES?)?(?:$|[_\-. ])",
    re.IGNORECASE,
)
_AUDIT_RE = re.compile(
    r"(?:^|[_\-. ])(?:AUDIT|AUDITORIA)(?:$|[_\-. ])",
    re.IGNORECASE,
)


def _repo_path(value: str) -> PurePosixPath:
    text = str(value or "").strip().replace("\\", "/")
    if not text:
        raise ValueError("path must be a non-empty repository path")
    return PurePosixPath(text)


def classify_document_path(path: str) -> Optional[DocumentCategory]:
    """Classify a repository path as a RAG documentary source.

    RAG-002-A rules:
    - README files are documentary sources anywhere
    - handoff, roadmap, patch-note, and audit files are recognized by name
    - Markdown/RST/AsciiDoc files are documentary sources
    - TXT is accepted only for explicit documentary categories or under docs/
    - dependency manifests such as requirements.txt are not documentation
    """

    repo_path = _repo_path(path)
    name = repo_path.name
    lower_name = name.lower()
    stem_upper = repo_path.stem.upper()
    suffix = repo_path.suffix.lower()

    if lower_name in _DEPENDENCY_MANIFEST_NAMES:
        return None

    if lower_name.startswith("readme.") or lower_name == "readme":
        return DocumentCategory.README

    if "HANDOFF" in stem_upper:
        return DocumentCategory.HANDOFF

    if "ROADMAP" in stem_upper:
        return DocumentCategory.ROADMAP

    if _PATCH_RE.search(repo_path.stem):
        return DocumentCategory.PATCH_NOTE

    if _AUDIT_RE.search(repo_path.stem):
        return DocumentCategory.AUDIT

    if suffix in _MARKDOWN_EXTENSIONS:
        return DocumentCategory.DOCUMENTATION

    if suffix in _TEXT_EXTENSIONS and repo_path.parts:
        if repo_path.parts[0].lower() == "docs":
            return DocumentCategory.DOCUMENTATION

    return None


def is_document_source(path: str) -> bool:
    return classify_document_path(path) is not None
