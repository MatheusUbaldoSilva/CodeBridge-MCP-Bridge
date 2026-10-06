"""Deterministic code/config source classification for RAG-002-B.

This module classifies repository-style paths only.
It does not read source contents, parse syntax, create chunks, index data,
load embedding models, or execute commands.
"""

from __future__ import annotations

from enum import Enum
from pathlib import PurePosixPath
from typing import Optional


class CodeSourceKind(str, Enum):
    CODE = "CODE"
    CONFIG = "CONFIG"
    WEB = "WEB"
    INSTALLER = "INSTALLER"
    DEPENDENCY_MANIFEST = "DEPENDENCY_MANIFEST"


CODE_EXTENSIONS = frozenset({
    ".c",
    ".cc",
    ".cpp",
    ".h",
    ".hpp",
    ".py",
    ".ps1",
    ".bat",
    ".cmd",
    ".sh",
})

WEB_EXTENSIONS = frozenset({
    ".js",
    ".ts",
    ".html",
    ".css",
})

CONFIG_EXTENSIONS = frozenset({
    ".json",
    ".yaml",
    ".yml",
    ".toml",
})

INSTALLER_EXTENSIONS = frozenset({
    ".nsi",
    ".nsh",
})

DEPENDENCY_MANIFEST_NAMES = frozenset({
    "requirements.txt",
})

ALLOWED_CODE_EXTENSIONS = frozenset().union(
    CODE_EXTENSIONS,
    WEB_EXTENSIONS,
    CONFIG_EXTENSIONS,
    INSTALLER_EXTENSIONS,
)


def _repo_path(value: str) -> PurePosixPath:
    text = str(value or "").strip().replace("\\", "/")
    if not text:
        raise ValueError("path must be a non-empty repository path")
    return PurePosixPath(text)


def classify_code_path(path: str) -> Optional[CodeSourceKind]:
    """Classify an approved RAG code/config source path."""

    repo_path = _repo_path(path)
    name = repo_path.name.lower()
    suffix = repo_path.suffix.lower()

    if name in DEPENDENCY_MANIFEST_NAMES:
        return CodeSourceKind.DEPENDENCY_MANIFEST
    if suffix in CODE_EXTENSIONS:
        return CodeSourceKind.CODE
    if suffix in WEB_EXTENSIONS:
        return CodeSourceKind.WEB
    if suffix in CONFIG_EXTENSIONS:
        return CodeSourceKind.CONFIG
    if suffix in INSTALLER_EXTENSIONS:
        return CodeSourceKind.INSTALLER
    return None


def is_code_source(path: str) -> bool:
    return classify_code_path(path) is not None
