"""Lazy bridge between the MCP surface and the optional RAG package.

This module is intentionally separate from mcp_server so the critical MCP
execution surface keeps importing even when the RAG package is unavailable.
"""

from __future__ import annotations

from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parent.parent


def _ensure_project_root() -> None:
    value = str(ROOT)
    if value not in sys.path:
        sys.path.insert(0, value)


def get_rag_status() -> dict[str, Any]:
    _ensure_project_root()

    from rag.runtime.status import build_rag_status

    return build_rag_status().to_dict()
