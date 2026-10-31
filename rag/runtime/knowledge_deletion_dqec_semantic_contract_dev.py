"""RAG-DEL-01.04-DQ-E-C: read-only AST audit of private semantic child contract.

No worker launch. Presence of an internal lock + child catalog re-resolution
blocks claiming an end-to-end pinned private semantic read in production.
"""
from __future__ import annotations

import ast
from pathlib import Path


def _find_function(tree: ast.AST, name: str) -> ast.FunctionDef | None:
    for node in ast.walk(tree):
        if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)) and node.name == name:
            return node
    return None


def _calls(node: ast.AST, target: str) -> bool:
    return any(
        isinstance(child,ast.Call)
        and (isinstance(child.func,ast.Name) and child.func.id == target
             or isinstance(child.func,ast.Attribute) and child.func.attr == target)
        for child in ast.walk(node)
    )


def audit_semantic_child_pin_contract_dev(repo_root: Path) -> dict:
    root=Path(repo_root)
    parent=root/"rag"/"runtime"/"isolated_project_search.py"
    child=root/"rag"/"runtime"/"isolated_project_worker.py"
    try:
        parent_ast=ast.parse(parent.read_text(encoding="utf-8"))
        child_ast=ast.parse(child.read_text(encoding="utf-8"))
    except (SyntaxError,UnicodeError,OSError):
        return {
            "state":"DQEC_SOURCE_MISSING_OR_INVALID",
            "parent_internal_semantic_lock":False,
            "child_re_resolves_catalog":False,
            "child_accepts_explicit_pinned_manifest":False,
            "safe_to_activate":False,
            "operational_use_allowed":False,
            "read_only":True,
        }
    semantic=_find_function(parent_ast,"semantic_isolated_project")
    worker=_find_function(child_ast,"main")
    parent_locks=bool(semantic and _calls(semantic,"production_generation_lock"))
    child_resolves=bool(worker and _calls(worker,"resolve_isolated_project"))
    # A handoff can only be considered explicit when the worker reads a
    # fingerprinted manifest field from the IPC request; this simple static
    # check is NEGATIVE evidence only, never positive runtime attestation.
    child_accepts_manifest=bool(worker and any(
        isinstance(n,ast.Constant) and n.value=="pinned_manifest_sha256"
        for n in ast.walk(worker)
    ))
    unresolved=parent_locks or child_resolves or not child_accepts_manifest
    return {
        "state":"DQEC_REAL_SEMANTIC_PIN_REFACTOR_PENDING"
                if unresolved else "DQEC_SOURCE_IMPROVED_RUNTIME_ATTESTATION_PENDING",
        "parent_internal_semantic_lock":parent_locks,
        "child_re_resolves_catalog":child_resolves,
        "child_accepts_explicit_pinned_manifest":child_accepts_manifest,
        "safe_to_activate":False,
        "operational_use_allowed":False,
        "read_only":True,
    }