"""Code symbol extraction for RAG-004-C.

Symbols are a separate layer over the parser/chunker contracts from 004-A/B.
Extraction is deterministic and best-effort for lexical languages.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from enum import Enum
from pathlib import PurePosixPath
import re
from typing import List, Optional, Sequence, Tuple

from .code_parser import CodeLanguage, parse_code_source
from .code_units import (
    _brace_pairs,
    _find_opening_block,
    _mask_source,
)


class CodeSymbolKind(str, Enum):
    CLASS = "CLASS"
    FUNCTION = "FUNCTION"
    METHOD = "METHOD"
    CONSTANT = "CONSTANT"
    MODULE = "MODULE"
    NAMESPACE = "NAMESPACE"


@dataclass(frozen=True)
class CodeSymbol:
    ordinal: int
    name: str
    qualified_name: str
    kind: CodeSymbolKind
    language: CodeLanguage
    line_start: int
    line_end: int
    parent: Optional[str] = None

    def __post_init__(self) -> None:
        if self.ordinal < 0:
            raise ValueError("ordinal must be >= 0")
        if not self.name.strip():
            raise ValueError("name must be non-empty")
        if not self.qualified_name.strip():
            raise ValueError("qualified_name must be non-empty")
        if not isinstance(self.kind, CodeSymbolKind):
            raise ValueError("kind must be CodeSymbolKind")
        if not isinstance(self.language, CodeLanguage):
            raise ValueError("language must be CodeLanguage")
        if self.line_start < 1:
            raise ValueError("line_start must be >= 1")
        if self.line_end < self.line_start:
            raise ValueError("line_end must be >= line_start")


@dataclass(frozen=True)
class _Scope:
    kind: CodeSymbolKind
    name: str
    start: int
    end: int


_PS_CLASS_RE = re.compile(
    r"^\s*class\s+([A-Za-z_][\w-]*)",
    re.IGNORECASE,
)
_PS_FUNCTION_RE = re.compile(
    r"^\s*(?:function|filter)\s+([^\s({]+)",
    re.IGNORECASE,
)
_PS_METHOD_RE = re.compile(
    r"^\s*(?:static\s+)?(?:\[[^\]]+\]\s+)?"
    r"([A-Za-z_][\w-]*)\s*\(",
    re.IGNORECASE,
)
_PS_CONSTANT_RE = re.compile(
    r"^\s*Set-Variable\b.*?-Name\s+['\"]?([^\s'\"]+)"
    r"['\"]?.*?-Option\s+Constant\b",
    re.IGNORECASE,
)

_JS_CLASS_RE = re.compile(
    r"^\s*(?:(?:export\s+default|export)\s+)?"
    r"class\s+([A-Za-z_$][\w$]*)"
)
_JS_FUNCTION_RE = re.compile(
    r"^\s*(?:(?:export\s+default|export)\s+)?"
    r"(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\s*\("
)
_JS_ARROW_RE = re.compile(
    r"^\s*(?:(?:export)\s+)?(?:const|let|var)\s+"
    r"([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?.*=>"
)
_JS_METHOD_RE = re.compile(
    r"^\s*(?:static\s+)?(?:async\s+)?(?:get\s+|set\s+)?"
    r"([#A-Za-z_$][\w$#]*)\s*\("
)
_JS_CONSTANT_RE = re.compile(
    r"^\s*(?:(?:export)\s+)?const\s+([A-Za-z_$][\w$]*)\b"
)
_TS_NAMESPACE_RE = re.compile(
    r"^\s*(?:(?:export|declare)\s+)?"
    r"(?:namespace|module)\s+([A-Za-z_$][\w$]*)\b"
)

_CPP_CLASS_RE = re.compile(
    r"^\s*(?:template\s*<.*>\s*)?"
    r"(?:class|struct)\s+([A-Za-z_]\w*)"
)
_CPP_NAMESPACE_RE = re.compile(
    r"^\s*namespace\s+([A-Za-z_]\w*)\b"
)
_CPP_CALLABLE_RE = re.compile(
    r"^\s*(?:template\s*<.*>\s*)?"
    r"(?!if\b|for\b|while\b|switch\b|catch\b|return\b)"
    r".*?([~A-Za-z_]\w*(?:::[~A-Za-z_]\w*)*)\s*\("
)
_CPP_CONST_RE = re.compile(
    r"^\s*(?:(?:static|inline)\s+)*"
    r"(?:constexpr|const)\b[^;()]*?\b([A-Za-z_]\w*)\s*(?:=|;|\{)"
)
_CPP_DEFINE_RE = re.compile(
    r"^\s*#\s*define\s+([A-Za-z_]\w*)\b"
)


def _normalize_path(path: str) -> str:
    value = str(path or "").strip().replace("\\", "/")
    if not value:
        raise ValueError("path must be a non-empty repository path")
    return str(PurePosixPath(value))


def _module_name(path: str, language: CodeLanguage) -> str:
    normalized = _normalize_path(path)
    pure = PurePosixPath(normalized)

    if language is CodeLanguage.PYTHON:
        parts = list(pure.with_suffix("").parts)
        if parts and parts[-1] == "__init__":
            parts.pop()
        return ".".join(parts) or pure.stem

    return pure.stem


def _node_start(node: ast.AST) -> int:
    decorators = getattr(node, "decorator_list", ())
    return min(
        [node.lineno]
        + [decorator.lineno for decorator in decorators]
    )


def _assignment_names(node: ast.AST) -> Tuple[str, ...]:
    targets: List[ast.AST] = []
    if isinstance(node, ast.Assign):
        targets.extend(node.targets)
    elif isinstance(node, ast.AnnAssign):
        targets.append(node.target)

    names: List[str] = []
    for target in targets:
        if isinstance(target, ast.Name) and target.id.isupper():
            names.append(target.id)
    return tuple(names)


def _python_symbols(
    text: str,
    *,
    module_name: str,
) -> List[Tuple[str, str, CodeSymbolKind, int, int, Optional[str]]]:
    tree = ast.parse(text)
    found: List[
        Tuple[str, str, CodeSymbolKind, int, int, Optional[str]]
    ] = []

    def qualify(parent: str, name: str) -> str:
        return f"{parent}.{name}" if parent else name

    def walk_class(node: ast.ClassDef, parent: str) -> None:
        class_qualified = qualify(parent, node.name)
        found.append(
            (
                node.name,
                class_qualified,
                CodeSymbolKind.CLASS,
                _node_start(node),
                node.end_lineno,
                parent,
            )
        )

        for child in node.body:
            if isinstance(
                child,
                (ast.FunctionDef, ast.AsyncFunctionDef),
            ):
                found.append(
                    (
                        child.name,
                        qualify(class_qualified, child.name),
                        CodeSymbolKind.METHOD,
                        _node_start(child),
                        child.end_lineno,
                        class_qualified,
                    )
                )
            elif isinstance(child, ast.ClassDef):
                walk_class(child, class_qualified)
            else:
                for name in _assignment_names(child):
                    found.append(
                        (
                            name,
                            qualify(class_qualified, name),
                            CodeSymbolKind.CONSTANT,
                            child.lineno,
                            getattr(child, "end_lineno", child.lineno),
                            class_qualified,
                        )
                    )

    for node in tree.body:
        if isinstance(
            node,
            (ast.FunctionDef, ast.AsyncFunctionDef),
        ):
            found.append(
                (
                    node.name,
                    f"{module_name}.{node.name}",
                    CodeSymbolKind.FUNCTION,
                    _node_start(node),
                    node.end_lineno,
                    module_name,
                )
            )
        elif isinstance(node, ast.ClassDef):
            walk_class(node, module_name)
        else:
            for name in _assignment_names(node):
                found.append(
                    (
                        name,
                        f"{module_name}.{name}",
                        CodeSymbolKind.CONSTANT,
                        node.lineno,
                        getattr(node, "end_lineno", node.lineno),
                        module_name,
                    )
                )

    return found


def _scope_patterns(
    language: CodeLanguage,
) -> Sequence[Tuple[re.Pattern[str], CodeSymbolKind]]:
    if language is CodeLanguage.POWERSHELL:
        return ((_PS_CLASS_RE, CodeSymbolKind.CLASS),)
    if language is CodeLanguage.TYPESCRIPT:
        return (
            (_TS_NAMESPACE_RE, CodeSymbolKind.NAMESPACE),
            (_JS_CLASS_RE, CodeSymbolKind.CLASS),
        )
    if language is CodeLanguage.JAVASCRIPT:
        return ((_JS_CLASS_RE, CodeSymbolKind.CLASS),)
    return (
        (_CPP_NAMESPACE_RE, CodeSymbolKind.NAMESPACE),
        (_CPP_CLASS_RE, CodeSymbolKind.CLASS),
    )


def _collect_scopes(
    masked_lines: List[str],
    language: CodeLanguage,
) -> List[_Scope]:
    pairs = _brace_pairs(masked_lines)
    scopes: List[_Scope] = []

    for line_no, line in enumerate(masked_lines, 1):
        for pattern, kind in _scope_patterns(language):
            match = pattern.match(line)
            if not match:
                continue

            block = _find_opening_block(
                masked_lines,
                pairs,
                line_no,
            )
            if block is None:
                continue

            (_, _), (close_line, _) = block
            scopes.append(
                _Scope(
                    kind=kind,
                    name=match.group(1),
                    start=line_no,
                    end=close_line,
                )
            )
            break

    return sorted(
        scopes,
        key=lambda item: (
            item.start,
            -item.end,
            item.kind.value,
            item.name,
        ),
    )


def _containing_scopes(
    line_start: int,
    line_end: int,
    scopes: Sequence[_Scope],
    *,
    exclude: Optional[_Scope] = None,
) -> List[_Scope]:
    items = [
        scope
        for scope in scopes
        if scope is not exclude
        and scope.start <= line_start
        and line_end <= scope.end
    ]
    return sorted(
        items,
        key=lambda item: (
            item.start,
            -item.end,
        ),
    )


def _qualified(
    module_name: str,
    scopes: Sequence[_Scope],
    name: str,
) -> Tuple[str, str]:
    parts = [module_name]
    parts.extend(scope.name for scope in scopes)
    parent = ".".join(parts)
    return f"{parent}.{name}", parent


def _callable_name(
    line: str,
    language: CodeLanguage,
    *,
    inside_class: bool,
) -> Optional[str]:
    if language is CodeLanguage.POWERSHELL:
        match = (
            _PS_METHOD_RE.match(line)
            if inside_class
            else _PS_FUNCTION_RE.match(line)
        )
        return match.group(1) if match else None

    if language in (
        CodeLanguage.JAVASCRIPT,
        CodeLanguage.TYPESCRIPT,
    ):
        if inside_class:
            match = _JS_METHOD_RE.match(line)
        else:
            match = _JS_FUNCTION_RE.match(line)
            if not match:
                match = _JS_ARROW_RE.match(line)
        return match.group(1) if match else None

    match = _CPP_CALLABLE_RE.match(line)
    return match.group(1) if match else None


def _lexical_symbols(
    text: str,
    *,
    language: CodeLanguage,
    module_name: str,
) -> List[Tuple[str, str, CodeSymbolKind, int, int, Optional[str]]]:
    masked_lines = _mask_source(text, language)
    pairs = _brace_pairs(masked_lines)
    scopes = _collect_scopes(
        masked_lines,
        language,
    )
    found: List[
        Tuple[str, str, CodeSymbolKind, int, int, Optional[str]]
    ] = []
    callable_ranges: List[Tuple[int, int]] = []

    for scope in scopes:
        parents = _containing_scopes(
            scope.start,
            scope.end,
            scopes,
            exclude=scope,
        )
        qualified, parent = _qualified(
            module_name,
            parents,
            scope.name,
        )
        found.append(
            (
                scope.name,
                qualified,
                scope.kind,
                scope.start,
                scope.end,
                parent,
            )
        )

    for line_no, line in enumerate(masked_lines, 1):
        containing = _containing_scopes(
            line_no,
            line_no,
            scopes,
        )
        classes = [
            scope
            for scope in containing
            if scope.kind is CodeSymbolKind.CLASS
        ]
        inside_class = bool(classes)

        name = _callable_name(
            line,
            language,
            inside_class=inside_class,
        )
        if not name:
            continue

        if any(
            scope.start == line_no
            for scope in scopes
        ):
            continue

        block = _find_opening_block(
            masked_lines,
            pairs,
            line_no,
        )

        expression_arrow = (
            language
            in (CodeLanguage.JAVASCRIPT, CodeLanguage.TYPESCRIPT)
            and bool(_JS_ARROW_RE.match(line))
            and "{" not in line
        )

        if block is None and not expression_arrow:
            continue

        if block is None:
            end_line = line_no
        else:
            (_, _), (end_line, _) = block

        if language is CodeLanguage.C_CPP and "::" in name:
            native_parts = [
                part.lstrip("~")
                for part in name.split("::")
                if part
            ]
            leaf = native_parts[-1]
            explicit_parent = native_parts[:-1]
            parent_parts = [module_name] + explicit_parent
            parent = ".".join(parent_parts)
            qualified = f"{parent}.{leaf}"
            kind = (
                CodeSymbolKind.METHOD
                if explicit_parent
                else CodeSymbolKind.FUNCTION
            )
            clean_name = leaf
        else:
            scope_chain = _containing_scopes(
                line_no,
                end_line,
                scopes,
            )
            qualified, parent = _qualified(
                module_name,
                scope_chain,
                name,
            )
            kind = (
                CodeSymbolKind.METHOD
                if any(
                    scope.kind is CodeSymbolKind.CLASS
                    for scope in scope_chain
                )
                else CodeSymbolKind.FUNCTION
            )
            clean_name = name

        found.append(
            (
                clean_name,
                qualified,
                kind,
                line_no,
                end_line,
                parent,
            )
        )
        callable_ranges.append(
            (line_no, end_line)
        )

    def inside_callable(line_no: int) -> bool:
        return any(
            start <= line_no <= end
            for start, end in callable_ranges
        )

    for line_no, line in enumerate(masked_lines, 1):
        if inside_callable(line_no):
            continue

        name: Optional[str] = None

        if language is CodeLanguage.POWERSHELL:
            match = _PS_CONSTANT_RE.match(line)
            if match:
                name = match.group(1)
        elif language in (
            CodeLanguage.JAVASCRIPT,
            CodeLanguage.TYPESCRIPT,
        ):
            match = _JS_CONSTANT_RE.match(line)
            if match and not _JS_ARROW_RE.match(line):
                name = match.group(1)
        else:
            match = _CPP_DEFINE_RE.match(line)
            if not match:
                match = _CPP_CONST_RE.match(line)
            if match:
                name = match.group(1)

        if not name:
            continue

        scope_chain = _containing_scopes(
            line_no,
            line_no,
            scopes,
        )
        qualified, parent = _qualified(
            module_name,
            scope_chain,
            name,
        )
        found.append(
            (
                name,
                qualified,
                CodeSymbolKind.CONSTANT,
                line_no,
                line_no,
                parent,
            )
        )

    return found


def extract_code_symbols(
    text: str,
    *,
    path: str,
) -> Tuple[CodeSymbol, ...]:
    """Extract symbols without changing source or chunk boundaries."""

    if not isinstance(text, str):
        raise ValueError("text must be a string")

    parse_result = parse_code_source(
        text,
        path=path,
    )
    module_name = _module_name(
        parse_result.path,
        parse_result.language,
    )
    line_count = len(text.splitlines())

    raw: List[
        Tuple[str, str, CodeSymbolKind, int, int, Optional[str]]
    ] = [
        (
            module_name,
            module_name,
            CodeSymbolKind.MODULE,
            1,
            max(1, line_count),
            None,
        )
    ]

    if parse_result.language is CodeLanguage.PYTHON:
        raw.extend(
            _python_symbols(
                text,
                module_name=module_name,
            )
        )
    else:
        raw.extend(
            _lexical_symbols(
                text,
                language=parse_result.language,
                module_name=module_name,
            )
        )

    module = raw[0]
    rest = sorted(
        set(raw[1:]),
        key=lambda item: (
            item[3],
            item[4],
            item[2].value,
            item[1],
        ),
    )
    ordered = [module] + rest

    return tuple(
        CodeSymbol(
            ordinal=ordinal,
            name=name,
            qualified_name=qualified_name,
            kind=kind,
            language=parse_result.language,
            line_start=line_start,
            line_end=line_end,
            parent=parent,
        )
        for ordinal, (
            name,
            qualified_name,
            kind,
            line_start,
            line_end,
            parent,
        ) in enumerate(ordered)
    )
