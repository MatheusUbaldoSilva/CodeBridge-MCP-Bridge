"""Language-aware source parser adapters for RAG-004-A.

This phase selects a parser by file extension and validates source structure.
It intentionally does not choose chunk units or extract symbols; those belong
to RAG-004-B and RAG-004-C.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from enum import Enum
from pathlib import PurePosixPath
from typing import List, Optional, Tuple


class CodeLanguage(str, Enum):
    PYTHON = "PYTHON"
    POWERSHELL = "POWERSHELL"
    JAVASCRIPT = "JAVASCRIPT"
    TYPESCRIPT = "TYPESCRIPT"
    C_CPP = "C_CPP"


class ParserBackend(str, Enum):
    PYTHON_AST = "PYTHON_AST"
    POWERSHELL_LEXICAL = "POWERSHELL_LEXICAL"
    ECMASCRIPT_LEXICAL = "ECMASCRIPT_LEXICAL"
    C_CPP_LEXICAL = "C_CPP_LEXICAL"


@dataclass(frozen=True)
class CodeParseResult:
    language: CodeLanguage
    backend: ParserBackend
    path: str
    line_count: int
    nonempty_line_count: int
    delimiter_pairs: int
    max_delimiter_depth: int

    def __post_init__(self) -> None:
        if not isinstance(self.language, CodeLanguage):
            raise ValueError("language must be CodeLanguage")
        if not isinstance(self.backend, ParserBackend):
            raise ValueError("backend must be ParserBackend")
        if not isinstance(self.path, str) or not self.path.strip():
            raise ValueError("path must be non-empty")
        if self.line_count < 0 or self.nonempty_line_count < 0:
            raise ValueError("line counts must be >= 0")
        if self.nonempty_line_count > self.line_count:
            raise ValueError("nonempty_line_count cannot exceed line_count")
        if self.delimiter_pairs < 0 or self.max_delimiter_depth < 0:
            raise ValueError("delimiter metrics must be >= 0")


class CodeParseError(ValueError):
    def __init__(
        self,
        message: str,
        *,
        language: CodeLanguage,
        line: Optional[int] = None,
        column: Optional[int] = None,
    ) -> None:
        self.language = language
        self.line = line
        self.column = column
        location = ""
        if line is not None:
            location = f" at line {line}"
            if column is not None:
                location += f", column {column}"
        super().__init__(
            f"{language.value} parse error{location}: {message}"
        )


class UnsupportedCodeLanguageError(ValueError):
    pass


_EXTENSION_LANGUAGE = {
    ".py": CodeLanguage.PYTHON,
    ".ps1": CodeLanguage.POWERSHELL,
    ".js": CodeLanguage.JAVASCRIPT,
    ".ts": CodeLanguage.TYPESCRIPT,
    ".c": CodeLanguage.C_CPP,
    ".cc": CodeLanguage.C_CPP,
    ".cpp": CodeLanguage.C_CPP,
    ".h": CodeLanguage.C_CPP,
    ".hpp": CodeLanguage.C_CPP,
}

_LANGUAGE_BACKEND = {
    CodeLanguage.PYTHON: ParserBackend.PYTHON_AST,
    CodeLanguage.POWERSHELL: ParserBackend.POWERSHELL_LEXICAL,
    CodeLanguage.JAVASCRIPT: ParserBackend.ECMASCRIPT_LEXICAL,
    CodeLanguage.TYPESCRIPT: ParserBackend.ECMASCRIPT_LEXICAL,
    CodeLanguage.C_CPP: ParserBackend.C_CPP_LEXICAL,
}


def _normalize_path(value: str) -> str:
    text = str(value or "").strip().replace("\\", "/")
    if not text:
        raise ValueError("path must be a non-empty repository path")
    return str(PurePosixPath(text))


def detect_code_language(path: str) -> Optional[CodeLanguage]:
    normalized = _normalize_path(path)
    return _EXTENSION_LANGUAGE.get(
        PurePosixPath(normalized).suffix.lower()
    )


def _validate_python(text: str) -> Tuple[int, int]:
    try:
        ast.parse(text)
    except SyntaxError as exc:
        raise CodeParseError(
            exc.msg,
            language=CodeLanguage.PYTHON,
            line=exc.lineno,
            column=exc.offset,
        ) from exc
    return 0, 0


def _scan_delimiters(
    text: str,
    *,
    language: CodeLanguage,
) -> Tuple[int, int]:
    open_to_close = {"(": ")", "[": "]", "{": "}"}
    close_to_open = {value: key for key, value in open_to_close.items()}
    stack: List[Tuple[str, int, int]] = []
    pairs = 0
    max_depth = 0

    state = "NORMAL"
    escaped = False
    lines = text.splitlines()

    for line_no, line in enumerate(lines, 1):
        stripped = line.lstrip().rstrip()

        if state == "PS_HERE_SINGLE":
            if stripped == "'@":
                state = "NORMAL"
            continue
        if state == "PS_HERE_DOUBLE":
            if stripped == '"@':
                state = "NORMAL"
            continue

        index = 0
        while index < len(line):
            char = line[index]
            next_char = line[index + 1] if index + 1 < len(line) else ""

            if state == "BLOCK_COMMENT":
                if char == "*" and next_char == "/":
                    state = "NORMAL"
                    index += 2
                    continue
                index += 1
                continue

            if state == "PS_BLOCK_COMMENT":
                if char == "#" and next_char == ">":
                    state = "NORMAL"
                    index += 2
                    continue
                index += 1
                continue

            if state in ("SINGLE", "DOUBLE", "TEMPLATE"):
                if language is CodeLanguage.POWERSHELL:
                    if escaped:
                        escaped = False
                        index += 1
                        continue
                    if char == "`":
                        escaped = True
                        index += 1
                        continue
                elif char == "\\":
                    index += 2
                    continue

                closing = {
                    "SINGLE": "'",
                    "DOUBLE": '"',
                    "TEMPLATE": "`",
                }[state]
                if char == closing:
                    state = "NORMAL"
                index += 1
                continue

            if language is CodeLanguage.POWERSHELL:
                if char == "<" and next_char == "#":
                    state = "PS_BLOCK_COMMENT"
                    index += 2
                    continue
                if char == "#":
                    break
                if char == "@" and next_char in ("'", '"'):
                    state = (
                        "PS_HERE_SINGLE"
                        if next_char == "'"
                        else "PS_HERE_DOUBLE"
                    )
                    break
                if char == "'":
                    state = "SINGLE"
                    index += 1
                    continue
                if char == '"':
                    state = "DOUBLE"
                    index += 1
                    continue
            else:
                if char == "/" and next_char == "/":
                    break
                if char == "/" and next_char == "*":
                    state = "BLOCK_COMMENT"
                    index += 2
                    continue
                if char == "'":
                    state = "SINGLE"
                    index += 1
                    continue
                if char == '"':
                    state = "DOUBLE"
                    index += 1
                    continue
                if (
                    language
                    in (CodeLanguage.JAVASCRIPT, CodeLanguage.TYPESCRIPT)
                    and char == "`"
                ):
                    state = "TEMPLATE"
                    index += 1
                    continue

            if char in open_to_close:
                stack.append((char, line_no, index + 1))
                max_depth = max(max_depth, len(stack))
            elif char in close_to_open:
                if not stack or stack[-1][0] != close_to_open[char]:
                    raise CodeParseError(
                        f"unexpected closing delimiter {char}",
                        language=language,
                        line=line_no,
                        column=index + 1,
                    )
                stack.pop()
                pairs += 1

            index += 1

    if state != "NORMAL":
        raise CodeParseError(
            f"unterminated lexical state {state.lower()}",
            language=language,
            line=len(lines) or 1,
        )

    if stack:
        opener, line_no, column = stack[-1]
        raise CodeParseError(
            f"unclosed delimiter {opener}",
            language=language,
            line=line_no,
            column=column,
        )

    return pairs, max_depth


def parse_code_source(
    text: str,
    *,
    path: str,
) -> CodeParseResult:
    if not isinstance(text, str):
        raise ValueError("text must be a string")

    normalized_path = _normalize_path(path)
    language = detect_code_language(normalized_path)
    if language is None:
        raise UnsupportedCodeLanguageError(
            f"no RAG-004-A parser registered for {normalized_path}"
        )

    if language is CodeLanguage.PYTHON:
        delimiter_pairs, max_depth = _validate_python(text)
    else:
        delimiter_pairs, max_depth = _scan_delimiters(
            text,
            language=language,
        )

    lines = text.splitlines()
    return CodeParseResult(
        language=language,
        backend=_LANGUAGE_BACKEND[language],
        path=normalized_path,
        line_count=len(lines),
        nonempty_line_count=sum(1 for line in lines if line.strip()),
        delimiter_pairs=delimiter_pairs,
        max_delimiter_depth=max_depth,
    )
