"""Deterministic query classifier for the RAG model manager — RAG-008-A.

This module intentionally uses rules only.

It must not load models call an LLM touch an index or execute external commands.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re
from typing import Iterable, Tuple

from rag.contracts import SourceType


class QueryRoute(str, Enum):
    TEXT = "TEXT"
    CODE = "CODE"
    HYBRID = "HYBRID"
    LEXICAL_ONLY = "LEXICAL_ONLY"


@dataclass(frozen=True)
class QueryClassification:
    route: QueryRoute
    reasons: Tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.route, QueryRoute):
            raise ValueError("route must be QueryRoute")
        if not self.reasons:
            raise ValueError("reasons must not be empty")
        if any(not isinstance(reason, str) or not reason.strip() for reason in self.reasons):
            raise ValueError("reasons must contain non-empty strings")


_TEXT_HINTS = (
    "readme",
    "handoff",
    "roadmap",
    "patch note",
    "patchnote",
    "documentacao",
    "documentação",
    "documentation",
    "docs",
    "auditoria",
    "audit",
    "log",
    "commit",
    "git",
    "historico",
    "histórico",
    "history",
    "mensagem de erro",
    "error message",
)

_CODE_HINTS = (
    "codigo",
    "código",
    "code",
    "funcao",
    "função",
    "function",
    "metodo",
    "método",
    "method",
    "classe",
    "class",
    "implementa",
    "implementation",
    "onde controla",
    "where is",
    "where does",
    "cancelamento",
    "ownership",
    "runtime",
)

_CODE_SUFFIXES = (
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
    ".js",
    ".ts",
)

_HASH_RE = re.compile(r"^[0-9a-fA-F]{7,64}$")
_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(?:::[A-Za-z_][A-Za-z0-9_]*)*$")
_CAMEL_OR_CONSTANT_RE = re.compile(
    r"^(?:[A-Z][A-Za-z0-9]*[A-Z][A-Za-z0-9]*|[A-Z][A-Z0-9_]{2,}|[a-z]+[A-Z][A-Za-z0-9]*)$"
)


def _normalize_source_types(source_types: Iterable[SourceType]) -> Tuple[SourceType, ...]:
    result = tuple(source_types)
    if any(not isinstance(item, SourceType) for item in result):
        raise ValueError("source_types must contain only SourceType values")
    return result


def _looks_exact_lexical(query: str) -> bool:
    stripped = query.strip()

    if len(stripped) >= 2 and stripped[0] == stripped[-1] and stripped[0] in {'"', "'"}:
        return True

    if any(char.isspace() for char in stripped):
        return False

    if _HASH_RE.fullmatch(stripped):
        return True

    lowered = stripped.lower()
    if lowered.endswith(_CODE_SUFFIXES):
        return True

    if "/" in stripped or chr(92) in stripped:
        return True

    if "::" in stripped:
        return True

    if _IDENTIFIER_RE.fullmatch(stripped) and _CAMEL_OR_CONSTANT_RE.fullmatch(stripped):
        return True

    return False


def _looks_like_code_snippet(query: str) -> bool:
    lowered = query.lower()
    snippet_markers = (
        "def ",
        "class ",
        "function ",
        "=>",
        "->",
        "::",
        "#include",
        "import ",
        "from ",
    )
    if any(marker in lowered for marker in snippet_markers):
        return True

    if "\n" in query and any(char in query for char in "{}();="):
        return True

    if any(lowered.endswith(suffix) for suffix in _CODE_SUFFIXES):
        return True

    return False


# Match complete words/phrases only: "code" must not match "CodeBridge".
def _contains_hint(text: str, hint: str) -> bool:
    return re.search(r"(?<!\w)" + re.escape(hint.casefold()) + r"(?!\w)", text) is not None


_IMPLEMENTATION_HINTS = (
    "implemented", "implementation", "implements", "generated", "serialized",
    "suppressed", "converted", "removed", "checker", "retriever", "function",
    "method", "handler", "source file", "where does", "where is",
    "onde fica", "onde pega", "onde verifica", "onde acontece", "qual parte",
    "como implementa", "como funciona a funcao",
)


def classify_query(
    query: str,
    *,
    source_types: Iterable[SourceType] = (),
) -> QueryClassification:
    if not isinstance(query, str) or not query.strip():
        raise ValueError("query must be a non-empty string")

    sources = _normalize_source_types(source_types)
    stripped = query.strip()
    lowered = stripped.casefold()

    if _looks_exact_lexical(stripped):
        return QueryClassification(
            route=QueryRoute.LEXICAL_ONLY,
            reasons=("exact_lexical_shape",),
        )

    scoped_code = SourceType.CODE in sources
    scoped_text = any(item is not SourceType.CODE for item in sources)

    if sources:
        if scoped_code and scoped_text:
            return QueryClassification(
                route=QueryRoute.HYBRID,
                reasons=("mixed_source_scope",),
            )
        if scoped_code:
            return QueryClassification(
                route=QueryRoute.CODE,
                reasons=("code_source_scope",),
            )
        return QueryClassification(
            route=QueryRoute.TEXT,
            reasons=("text_source_scope",),
        )

    code_snippet = _looks_like_code_snippet(stripped)
    code_hint = code_snippet or any(_contains_hint(lowered, hint) for hint in _CODE_HINTS)
    text_hint = any(_contains_hint(lowered, hint) for hint in _TEXT_HINTS)
    implementation_hint = any(
        _contains_hint(lowered, hint) for hint in _IMPLEMENTATION_HINTS
    )
    # A direct question about code behavior can be routed to the code model
    # without relying on benchmark-specific queries or document titles.
    code_hint = code_hint or (implementation_hint and not text_hint)

    if code_hint and text_hint:
        return QueryClassification(
            route=QueryRoute.HYBRID,
            reasons=("code_hint", "text_hint"),
        )

    if code_hint:
        return QueryClassification(
            route=QueryRoute.CODE,
            reasons=("code_snippet" if code_snippet else "code_hint",),
        )

    if text_hint:
        return QueryClassification(
            route=QueryRoute.TEXT,
            reasons=("text_hint",),
        )

    return QueryClassification(
        route=QueryRoute.TEXT,
        reasons=("default_text",),
    )
