"""Structural code units for RAG-004-B.

This layer prefers class, function, method, and logical-block boundaries.
It does not expose symbol names yet; symbol extraction belongs to RAG-004-C.
No token-count slicing is used.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from enum import Enum
import re
from typing import Dict, List, Set, Tuple

from .code_parser import (
    CodeLanguage,
    parse_code_source,
)


class CodeUnitKind(str, Enum):
    CLASS = "CLASS"
    FUNCTION = "FUNCTION"
    METHOD = "METHOD"
    LOGICAL_BLOCK = "LOGICAL_BLOCK"


@dataclass(frozen=True)
class CodeUnitDraft:
    ordinal: int
    content: str
    language: CodeLanguage
    kind: CodeUnitKind
    line_start: int
    line_end: int

    def __post_init__(self) -> None:
        if self.ordinal < 0:
            raise ValueError("ordinal must be >= 0")
        if not isinstance(self.content, str) or not self.content.strip():
            raise ValueError("content must be a non-empty string")
        if not isinstance(self.language, CodeLanguage):
            raise ValueError("language must be CodeLanguage")
        if not isinstance(self.kind, CodeUnitKind):
            raise ValueError("kind must be CodeUnitKind")
        if self.line_start < 1:
            raise ValueError("line_start must be >= 1")
        if self.line_end < self.line_start:
            raise ValueError("line_end must be >= line_start")


@dataclass(frozen=True)
class _Span:
    start: int
    end: int
    kind: CodeUnitKind


@dataclass(frozen=True)
class _ClassRange:
    start: int
    open_line: int
    end: int


_CONTROL_PREFIX_RE = re.compile(
    r"^\s*(?:if|for|foreach|while|switch|catch|with|else|do|try)\b",
    re.IGNORECASE,
)
_PS_FUNCTION_RE = re.compile(
    r"^\s*(?:function|filter)\s+\S+",
    re.IGNORECASE,
)
_PS_CLASS_RE = re.compile(
    r"^\s*class\s+[A-Za-z_][\w-]*",
    re.IGNORECASE,
)
_PS_METHOD_RE = re.compile(
    r"^\s*(?:static\s+)?(?:\[[^\]]+\]\s+)?[A-Za-z_][\w-]*\s*\(",
    re.IGNORECASE,
)
_JS_CLASS_RE = re.compile(
    r"^\s*(?:(?:export\s+default|export)\s+)?class\s+[A-Za-z_$][\w$]*"
)
_JS_FUNCTION_RE = re.compile(
    r"^\s*(?:(?:export\s+default|export)\s+)?(?:async\s+)?function\b"
)
_JS_ARROW_RE = re.compile(
    r"^\s*(?:(?:export)\s+)?(?:const|let|var)\s+"
    r"[A-Za-z_$][\w$]*\s*=\s*(?:async\s*)?.*=>"
)
_JS_METHOD_RE = re.compile(
    r"^\s*(?:static\s+)?(?:async\s+)?(?:get\s+|set\s+)?"
    r"[#A-Za-z_$][\w$#]*\s*\("
)
_CPP_CLASS_RE = re.compile(
    r"^\s*(?:template\s*<.*>\s*)?(?:class|struct)\s+[A-Za-z_]\w*"
)
_CPP_CONTROL_RE = re.compile(
    r"^\s*(?:if|for|while|switch|catch|return|sizeof|alignof|static_assert)\b"
)
_CPP_CALLABLE_RE = re.compile(
    r"^\s*(?:template\s*<.*>\s*)?(?!#).*\([^;{}]*\)"
)


def _source_slice(
    lines: List[str],
    start: int,
    end: int,
) -> str:
    return "\n".join(lines[start - 1:end]).strip("\n")


def _mask_source(
    text: str,
    language: CodeLanguage,
) -> List[str]:
    lines = text.splitlines()
    output: List[str] = []
    state = "NORMAL"

    for line in lines:
        chars = list(line)
        masked = [" "] * len(chars)
        stripped = line.lstrip()

        if state == "PS_HERE_SINGLE":
            if stripped.rstrip() == "'@":
                state = "NORMAL"
            output.append("".join(masked))
            continue

        if state == "PS_HERE_DOUBLE":
            if stripped.rstrip() == '"@':
                state = "NORMAL"
            output.append("".join(masked))
            continue

        index = 0
        escaped = False

        while index < len(chars):
            char = chars[index]
            next_char = chars[index + 1] if index + 1 < len(chars) else ""

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
                    index = len(chars)
                    continue
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

            masked[index] = char
            index += 1

        output.append("".join(masked))

    return output


def _brace_pairs(
    masked_lines: List[str],
) -> Dict[Tuple[int, int], Tuple[int, int]]:
    stack: List[Tuple[int, int]] = []
    pairs: Dict[Tuple[int, int], Tuple[int, int]] = {}

    for line_no, line in enumerate(masked_lines, 1):
        for column, char in enumerate(line, 1):
            if char == "{":
                stack.append((line_no, column))
            elif char == "}" and stack:
                opener = stack.pop()
                pairs[opener] = (line_no, column)

    return pairs


def _find_opening_block(
    masked_lines: List[str],
    pairs: Dict[Tuple[int, int], Tuple[int, int]],
    start_line: int,
    *,
    lookahead: int = 8,
) -> Tuple[Tuple[int, int], Tuple[int, int]] | None:
    end_line = min(
        len(masked_lines),
        start_line + lookahead - 1,
    )

    for line_no in range(start_line, end_line + 1):
        line = masked_lines[line_no - 1]
        semicolon = line.find(";")
        brace = line.find("{")

        if brace >= 0 and (semicolon < 0 or brace < semicolon):
            opener = (line_no, brace + 1)
            if opener in pairs:
                return opener, pairs[opener]

        if semicolon >= 0 and brace < 0:
            return None

    return None


def _inside_class(
    line_no: int,
    class_range: _ClassRange,
) -> bool:
    return class_range.start <= line_no <= class_range.end


def _innermost_class(
    line_no: int,
    classes: List[_ClassRange],
) -> _ClassRange | None:
    containing = [
        item
        for item in classes
        if _inside_class(line_no, item)
    ]
    if not containing:
        return None
    return min(
        containing,
        key=lambda item: item.end - item.start,
    )


def _python_spans(text: str) -> List[_Span]:
    tree = ast.parse(text)
    spans: List[_Span] = []

    def node_start(node: ast.AST) -> int:
        decorators = getattr(node, "decorator_list", ())
        return min(
            [node.lineno]
            + [decorator.lineno for decorator in decorators]
        )

    def add_class(node: ast.ClassDef) -> None:
        structural_children = [
            child
            for child in node.body
            if isinstance(
                child,
                (
                    ast.FunctionDef,
                    ast.AsyncFunctionDef,
                    ast.ClassDef,
                ),
            )
        ]
        start = node_start(node)

        if not structural_children:
            spans.append(
                _Span(
                    start,
                    node.end_lineno,
                    CodeUnitKind.CLASS,
                )
            )
            return

        first_body_line = (
            min(child.lineno for child in node.body)
            if node.body
            else node.end_lineno
        )
        spans.append(
            _Span(
                start,
                max(node.lineno, first_body_line - 1),
                CodeUnitKind.CLASS,
            )
        )

        for child in node.body:
            if isinstance(
                child,
                (ast.FunctionDef, ast.AsyncFunctionDef),
            ):
                spans.append(
                    _Span(
                        node_start(child),
                        child.end_lineno,
                        CodeUnitKind.METHOD,
                    )
                )
            elif isinstance(child, ast.ClassDef):
                add_class(child)

    for node in tree.body:
        if isinstance(
            node,
            (ast.FunctionDef, ast.AsyncFunctionDef),
        ):
            spans.append(
                _Span(
                    node_start(node),
                    node.end_lineno,
                    CodeUnitKind.FUNCTION,
                )
            )
        elif isinstance(node, ast.ClassDef):
            add_class(node)

    return spans


def _lexical_spans(
    text: str,
    language: CodeLanguage,
) -> Tuple[List[_Span], List[_ClassRange]]:
    masked_lines = _mask_source(text, language)
    pairs = _brace_pairs(masked_lines)
    classes: List[_ClassRange] = []

    class_pattern = {
        CodeLanguage.POWERSHELL: _PS_CLASS_RE,
        CodeLanguage.JAVASCRIPT: _JS_CLASS_RE,
        CodeLanguage.TYPESCRIPT: _JS_CLASS_RE,
        CodeLanguage.C_CPP: _CPP_CLASS_RE,
    }[language]

    for line_no, line in enumerate(masked_lines, 1):
        if not class_pattern.match(line):
            continue

        block = _find_opening_block(
            masked_lines,
            pairs,
            line_no,
        )
        if block is None:
            continue

        (open_line, _), (close_line, _) = block
        classes.append(
            _ClassRange(
                start=line_no,
                open_line=open_line,
                end=close_line,
            )
        )

    spans: List[_Span] = []
    methods_by_class: Dict[_ClassRange, List[_Span]] = {
        item: []
        for item in classes
    }

    for line_no, line in enumerate(masked_lines, 1):
        class_range = _innermost_class(
            line_no,
            classes,
        )
        if class_range is None or line_no == class_range.start:
            continue

        if language is CodeLanguage.POWERSHELL:
            candidate = bool(
                _PS_METHOD_RE.match(line)
            ) and not _CONTROL_PREFIX_RE.match(line)
        elif language in (
            CodeLanguage.JAVASCRIPT,
            CodeLanguage.TYPESCRIPT,
        ):
            candidate = bool(
                _JS_METHOD_RE.match(line)
            ) and not _CONTROL_PREFIX_RE.match(line)
        else:
            candidate = bool(
                _CPP_CALLABLE_RE.match(line)
            ) and not _CPP_CONTROL_RE.match(line)

        if not candidate:
            continue

        block = _find_opening_block(
            masked_lines,
            pairs,
            line_no,
        )
        if block is None:
            continue

        (_, _), (close_line, _) = block
        if close_line > class_range.end:
            continue

        methods_by_class[class_range].append(
            _Span(
                line_no,
                close_line,
                CodeUnitKind.METHOD,
            )
        )

    for class_range in classes:
        methods = methods_by_class[class_range]
        if methods:
            spans.append(
                _Span(
                    class_range.start,
                    class_range.open_line,
                    CodeUnitKind.CLASS,
                )
            )
            spans.extend(methods)
        else:
            spans.append(
                _Span(
                    class_range.start,
                    class_range.end,
                    CodeUnitKind.CLASS,
                )
            )

    for line_no, line in enumerate(masked_lines, 1):
        if _innermost_class(line_no, classes) is not None:
            continue

        expression_only = False

        if language is CodeLanguage.POWERSHELL:
            candidate = bool(
                _PS_FUNCTION_RE.match(line)
            )
        elif language in (
            CodeLanguage.JAVASCRIPT,
            CodeLanguage.TYPESCRIPT,
        ):
            arrow = bool(_JS_ARROW_RE.match(line))
            candidate = bool(
                _JS_FUNCTION_RE.match(line)
            ) or arrow
            expression_only = arrow and "{" not in line
        else:
            candidate = bool(
                _CPP_CALLABLE_RE.match(line)
            ) and not _CPP_CONTROL_RE.match(line)

        if not candidate:
            continue

        block = _find_opening_block(
            masked_lines,
            pairs,
            line_no,
        )
        if block is not None:
            (_, _), (close_line, _) = block
            spans.append(
                _Span(
                    line_no,
                    close_line,
                    CodeUnitKind.FUNCTION,
                )
            )
        elif expression_only:
            spans.append(
                _Span(
                    line_no,
                    line_no,
                    CodeUnitKind.FUNCTION,
                )
            )

    unique_spans = sorted(
        set(spans),
        key=lambda item: (
            item.start,
            item.end,
            item.kind.value,
        ),
    )

    accepted: List[_Span] = []
    for span in unique_spans:
        overlaps = any(
            not (
                span.end < existing.start
                or span.start > existing.end
            )
            for existing in accepted
        )
        if not overlaps:
            accepted.append(span)

    return accepted, classes


def _is_meaningful_logical_line(line: str) -> bool:
    stripped = line.strip()
    return bool(stripped) and not bool(
        re.fullmatch(
            r"[{}()\[\];,]+",
            stripped,
        )
    )


def _logical_spans(
    lines: List[str],
    covered: Set[int],
) -> List[_Span]:
    spans: List[_Span] = []
    line_no = 1

    while line_no <= len(lines):
        while (
            line_no <= len(lines)
            and (
                line_no in covered
                or not _is_meaningful_logical_line(
                    lines[line_no - 1]
                )
            )
        ):
            line_no += 1

        if line_no > len(lines):
            break

        start = line_no
        end = line_no
        line_no += 1

        while (
            line_no <= len(lines)
            and line_no not in covered
        ):
            if _is_meaningful_logical_line(
                lines[line_no - 1]
            ):
                end = line_no
            line_no += 1

        spans.append(
            _Span(
                start,
                end,
                CodeUnitKind.LOGICAL_BLOCK,
            )
        )

    return spans


def chunk_code_units(
    text: str,
    *,
    path: str,
) -> Tuple[CodeUnitDraft, ...]:
    """Create structural, non-token-based code units."""

    if not isinstance(text, str):
        raise ValueError("text must be a string")

    parse_result = parse_code_source(
        text,
        path=path,
    )
    lines = text.splitlines()

    if not lines or not any(line.strip() for line in lines):
        return ()

    if parse_result.language is CodeLanguage.PYTHON:
        structural = _python_spans(text)
        classes: List[_ClassRange] = []
    else:
        structural, classes = _lexical_spans(
            text,
            parse_result.language,
        )

    covered: Set[int] = set()
    for span in structural:
        covered.update(
            range(
                span.start,
                span.end + 1,
            )
        )

    for class_range in classes:
        if (
            class_range.end <= len(lines)
            and not _is_meaningful_logical_line(
                lines[class_range.end - 1]
            )
        ):
            covered.add(class_range.end)

    spans = structural + _logical_spans(
        lines,
        covered,
    )
    spans.sort(
        key=lambda item: (
            item.start,
            item.end,
            item.kind.value,
        )
    )

    chunks: List[CodeUnitDraft] = []
    for ordinal, span in enumerate(spans):
        content = _source_slice(
            lines,
            span.start,
            span.end,
        )
        if not content.strip():
            continue

        chunks.append(
            CodeUnitDraft(
                ordinal=ordinal,
                content=content,
                language=parse_result.language,
                kind=span.kind,
                line_start=span.start,
                line_end=span.end,
            )
        )

    return tuple(chunks)
