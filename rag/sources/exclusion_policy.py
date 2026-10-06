"""Central RAG source denylist for RAG-002-E.

The denylist is evaluated before document/code allowlists.
This module classifies repository-style paths only and has no filesystem I/O.
"""

from __future__ import annotations

from enum import Enum
from pathlib import PurePosixPath
import re
from typing import Optional


class DenyReason(str, Enum):
    GIT_OBJECTS = "GIT_OBJECTS"
    VIRTUAL_ENV = "VIRTUAL_ENV"
    NODE_MODULES = "NODE_MODULES"
    BUILD_OUTPUT = "BUILD_OUTPUT"
    CACHE = "CACHE"
    BINARY = "BINARY"
    BACKUP = "BACKUP"
    TEMPORARY = "TEMPORARY"
    CREDENTIAL = "CREDENTIAL"
    ENV_FILE = "ENV_FILE"
    PRIVATE_KEY = "PRIVATE_KEY"
    TOKEN = "TOKEN"
    PATH_TRAVERSAL = "PATH_TRAVERSAL"


_DENIED_DIRECTORY_NAMES = {
    ".venv": DenyReason.VIRTUAL_ENV,
    "venv": DenyReason.VIRTUAL_ENV,
    "node_modules": DenyReason.NODE_MODULES,
    "build": DenyReason.BUILD_OUTPUT,
    "dist": DenyReason.BUILD_OUTPUT,
    "__pycache__": DenyReason.CACHE,
    ".pytest_cache": DenyReason.CACHE,
    ".mypy_cache": DenyReason.CACHE,
    ".ruff_cache": DenyReason.CACHE,
    ".cache": DenyReason.CACHE,
    "cache": DenyReason.CACHE,
    "caches": DenyReason.CACHE,
    "backup": DenyReason.BACKUP,
    "backups": DenyReason.BACKUP,
    ".backup": DenyReason.BACKUP,
    ".backups": DenyReason.BACKUP,
    "tmp": DenyReason.TEMPORARY,
    "temp": DenyReason.TEMPORARY,
    ".tmp": DenyReason.TEMPORARY,
    ".temp": DenyReason.TEMPORARY,
}

_BINARY_EXTENSIONS = {
    ".exe", ".dll", ".so", ".dylib", ".bin",
    ".o", ".obj", ".a", ".lib", ".class", ".jar",
    ".pyc", ".pyo", ".wasm",
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".ico",
    ".mp3", ".wav", ".ogg", ".flac", ".mp4", ".avi", ".mov", ".mkv",
    ".zip", ".7z", ".rar", ".tar", ".gz", ".bz2", ".xz",
}

_PRIVATE_KEY_EXTENSIONS = {
    ".pem", ".key", ".p12", ".pfx", ".jks", ".keystore", ".kdbx",
}

_BACKUP_EXTENSIONS = {
    ".bak", ".backup", ".old", ".orig", ".save",
}

_TEMP_EXTENSIONS = {
    ".tmp", ".temp", ".swp", ".swo",
}

_EXACT_CREDENTIAL_NAMES = {
    "credentials.json",
    "credential.json",
    "credentials.yaml",
    "credentials.yml",
    "secrets.json",
    "secret.json",
    "secrets.yaml",
    "secrets.yml",
    ".netrc",
    "_netrc",
}

_EXACT_PRIVATE_KEY_NAMES = {
    "id_rsa",
    "id_dsa",
    "id_ecdsa",
    "id_ed25519",
}

_ENV_RE = re.compile(r"^\.env(?:\..+)?$", re.IGNORECASE)
_CREDENTIAL_RE = re.compile(
    r"(?:^|[._-])(credential|credentials|secret|secrets)(?:$|[._-])",
    re.IGNORECASE,
)
_TOKEN_RE = re.compile(
    r"(?:^|[._-])(token|tokens|api[_-]?key|access[_-]?key|refresh[_-]?token)(?:$|[._-])",
    re.IGNORECASE,
)


def _normalize_path(value: str) -> PurePosixPath:
    text = str(value or "").strip().replace("\\", "/")
    if not text:
        raise ValueError("path must be a non-empty repository path")
    while text.startswith("./"):
        text = text[2:]
    return PurePosixPath(text)


def classify_denied_path(path: str) -> Optional[DenyReason]:
    repo_path = _normalize_path(path)
    parts = tuple(part for part in repo_path.parts if part not in ("", "."))

    if ".." in parts:
        return DenyReason.PATH_TRAVERSAL

    lower_parts = tuple(part.lower() for part in parts)

    for index, part in enumerate(lower_parts):
        if part == ".git" and index + 1 < len(lower_parts):
            if lower_parts[index + 1] == "objects":
                return DenyReason.GIT_OBJECTS

    for part in lower_parts[:-1]:
        reason = _DENIED_DIRECTORY_NAMES.get(part)
        if reason is not None:
            return reason

    name = lower_parts[-1] if lower_parts else ""
    suffix = repo_path.suffix.lower()

    if _ENV_RE.fullmatch(name):
        return DenyReason.ENV_FILE

    if name in _EXACT_PRIVATE_KEY_NAMES or suffix in _PRIVATE_KEY_EXTENSIONS:
        return DenyReason.PRIVATE_KEY

    if name in _EXACT_CREDENTIAL_NAMES or _CREDENTIAL_RE.search(name):
        return DenyReason.CREDENTIAL

    if _TOKEN_RE.search(name):
        return DenyReason.TOKEN

    if suffix in _BACKUP_EXTENSIONS or name.endswith("~"):
        return DenyReason.BACKUP

    if suffix in _TEMP_EXTENSIONS:
        return DenyReason.TEMPORARY

    if suffix in _BINARY_EXTENSIONS:
        return DenyReason.BINARY

    return None


def is_denied_path(path: str) -> bool:
    return classify_denied_path(path) is not None
