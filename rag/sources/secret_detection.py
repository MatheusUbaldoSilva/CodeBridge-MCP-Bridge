"""High-confidence content secret detection for RAG-015-A.

The scanner is intentionally conservative. It detects credential material that
should never enter the RAG index while avoiding broad entropy heuristics that
would flag ordinary source code or documentation.

Findings never retain or return the raw secret value.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import re
from typing import Tuple


class SensitiveContentKind(str, Enum):
    PRIVATE_KEY = "PRIVATE_KEY"
    OPENAI_KEY = "OPENAI_KEY"
    GITHUB_TOKEN = "GITHUB_TOKEN"
    AWS_ACCESS_KEY = "AWS_ACCESS_KEY"
    GOOGLE_API_KEY = "GOOGLE_API_KEY"
    SLACK_TOKEN = "SLACK_TOKEN"
    SECRET_ASSIGNMENT = "SECRET_ASSIGNMENT"


@dataclass(frozen=True)
class SensitiveContentFinding:
    kind: SensitiveContentKind
    line_number: int
    fingerprint: str

    def __post_init__(self) -> None:
        if not isinstance(self.kind, SensitiveContentKind):
            raise ValueError("kind must be SensitiveContentKind")
        if not isinstance(self.line_number, int) or self.line_number < 1:
            raise ValueError("line_number must be >= 1")
        if not isinstance(self.fingerprint, str) or not re.fullmatch(
            r"[0-9a-f]{12}",
            self.fingerprint,
        ):
            raise ValueError("fingerprint must be 12 lowercase hex characters")

    def to_dict(self) -> dict[str, object]:
        return {
            "kind": self.kind.value,
            "line_number": self.line_number,
            "fingerprint": self.fingerprint,
        }


@dataclass(frozen=True)
class SensitiveContentScan:
    sensitive: bool
    findings: Tuple[SensitiveContentFinding, ...]

    def __post_init__(self) -> None:
        if self.sensitive != bool(self.findings):
            raise ValueError("sensitive must match whether findings exist")

    def to_dict(self) -> dict[str, object]:
        return {
            "sensitive": self.sensitive,
            "finding_count": len(self.findings),
            "findings": [item.to_dict() for item in self.findings],
        }


_PATTERN_RULES = (
    (
        SensitiveContentKind.PRIVATE_KEY,
        re.compile(
            r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----",
            re.IGNORECASE,
        ),
    ),
    (
        SensitiveContentKind.OPENAI_KEY,
        re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    ),
    (
        SensitiveContentKind.GITHUB_TOKEN,
        re.compile(
            r"\b(?:gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{22,})\b"
        ),
    ),
    (
        SensitiveContentKind.AWS_ACCESS_KEY,
        re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    ),
    (
        SensitiveContentKind.GOOGLE_API_KEY,
        re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"),
    ),
    (
        SensitiveContentKind.SLACK_TOKEN,
        re.compile(r"\bxox[baprs]-[0-9A-Za-z-]{20,}\b"),
    ),
)

_SECRET_NAME = (
    r"(?:password|passwd|pwd|api[_-]?key|access[_-]?token|refresh[_-]?token|"
    r"auth[_-]?token|client[_-]?secret|secret[_-]?key|private[_-]?key|"
    r"credential|credentials)"
)

_QUOTED_ASSIGNMENT_RE = re.compile(
    rf"""(?ix)
    (?P<name>\b{_SECRET_NAME}\b)
    \s*(?:=|:|=>)\s*
    (?P<quote>["'])
    (?P<value>[^"'\r\n]{{8,}})
    (?P=quote)
    """,
)

_BARE_ASSIGNMENT_RE = re.compile(
    rf"""(?ix)
    (?P<name>\b{_SECRET_NAME}\b)
    \s*(?:=|:|=>)\s*
    (?P<value>[A-Za-z0-9_+/@:=.-]{{12,}})
    (?=$|\s|[,;#}}\]])
    """,
)

_PLACEHOLDER_EXACT = {
    "changeme",
    "change-me",
    "change_me",
    "dummy",
    "example",
    "example123",
    "fake",
    "placeholder",
    "credential",
    "credentials",
    "token",
    "private_key",
    "client_secret",
    "api_key",
    "password",
    "none",
    "null",
    "redacted",
    "replace-me",
    "replace_me",
    "secret",
    "test",
    "test1234",
    "todo",
    "your-key",
    "your_key",
    "your-token",
    "your_token",
}


def _fingerprint(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()[:12]


def _line_number(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def _looks_like_placeholder(value: str) -> bool:
    raw = value.strip().strip("\"'").strip()
    lowered = raw.lower()

    if not raw:
        return True
    if lowered in _PLACEHOLDER_EXACT:
        return True
    if lowered.startswith(
        (
            "<",
            "$" + "{",
            "{{",
            "your_",
            "your-",
            "example_",
            "example-",
            "dummy_",
            "dummy-",
            "fake_",
            "fake-",
            "test_",
            "test-",
            "redacted",
            "os.getenv(",
            "os.environ",
            "getenv(",
            "process.env",
            "settings.",
            "config.",
        )
    ):
        return True
    if raw.endswith(">") and raw.startswith("<"):
        return True
    if raw.startswith("$(") or (raw.startswith("%") and raw.endswith("%")):
        return True
    if len(set(raw)) <= 2 and set(raw) <= {"*", "x", "X", "-", "_"}:
        return True
    return False


def scan_sensitive_content(
    content: str,
    *,
    max_findings: int = 20,
) -> SensitiveContentScan:
    if not isinstance(content, str):
        raise ValueError("content must be a string")
    if not isinstance(max_findings, int) or max_findings < 1:
        raise ValueError("max_findings must be >= 1")

    findings: list[SensitiveContentFinding] = []
    seen = set()

    def add(kind: SensitiveContentKind, start: int, raw_value: str) -> None:
        key = (kind, start)
        if key in seen or len(findings) >= max_findings:
            return
        seen.add(key)
        findings.append(
            SensitiveContentFinding(
                kind=kind,
                line_number=_line_number(content, start),
                fingerprint=_fingerprint(raw_value),
            )
        )

    for kind, pattern in _PATTERN_RULES:
        for match in pattern.finditer(content):
            add(kind, match.start(), match.group(0))
            if len(findings) >= max_findings:
                break
        if len(findings) >= max_findings:
            break

    if len(findings) < max_findings:
        assignment_matches = list(_QUOTED_ASSIGNMENT_RE.finditer(content))
        assignment_matches.extend(_BARE_ASSIGNMENT_RE.finditer(content))
        assignment_matches.sort(key=lambda item: item.start())

        for match in assignment_matches:
            value = match.group("value")
            if _looks_like_placeholder(value):
                continue
            if match.re is _BARE_ASSIGNMENT_RE:
                if not (re.search(r"[A-Za-z]", value) and re.search(r"\d", value)):
                    continue
            add(
                SensitiveContentKind.SECRET_ASSIGNMENT,
                match.start(),
                value,
            )
            if len(findings) >= max_findings:
                break

    findings.sort(key=lambda item: (item.line_number, item.kind.value))
    return SensitiveContentScan(
        sensitive=bool(findings),
        findings=tuple(findings),
    )


def contains_sensitive_content(content: str) -> bool:
    return scan_sensitive_content(content, max_findings=1).sensitive
