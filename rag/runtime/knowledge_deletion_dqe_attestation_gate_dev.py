"""RAG-DEL-01.04-DQ-E-A: source/read-only attestation gate (DEV ONLY).

Static repository evidence is not evidence of an installed MCP worker.
This gate never authorizes a pilot or deletion, even with caller assertions.
"""
from __future__ import annotations

import ast
from pathlib import Path


def _declares_readonly_generation_probe(root: Path) -> bool:
    path = root / "author_mcp" / "mcp_server.py"
    if not path.is_file():
        return False
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeError, OSError):
        return False
    for node in tree.body:
        if not isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)):
            continue
        if node.name != "codebridge_rag_generation_probe":
            continue
        for decor in node.decorator_list:
            if not isinstance(decor,ast.Call) or not isinstance(decor.func,ast.Attribute):
                continue
            if decor.func.attr != "tool":
                continue
            params={kw.arg:kw.value for kw in decor.keywords}
            name=params.get("name")
            annot=params.get("annotations")
            if (not isinstance(name,ast.Constant)
                    or name.value != "codebridge_rag_generation_probe"
                    or not isinstance(annot,ast.Call)):
                continue
            annotation_args={kw.arg:kw.value for kw in annot.keywords}
            read_only=annotation_args.get("read_only_hint")
            return isinstance(read_only,ast.Constant) and read_only.value is True
    return False


def audit_private_deletion_readiness_dev(
    repo_root: Path, *, installed_mcp_probe_exposed: bool = False,
    installed_gui_pinned_reader_attested: bool = False,
    semantic_child_reader_attested: bool = False,
    operational_queue_review_clean: bool = False,
) -> dict:
    """Read only source contract and caller-supplied observations.

    An observation is not permission to enable deletion or production work.
    This preflight intentionally reports non-authorized in every state.
    """
    if any(type(value) is not bool for value in (
        installed_mcp_probe_exposed,installed_gui_pinned_reader_attested,
        semantic_child_reader_attested,operational_queue_review_clean,
    )):
        raise ValueError("attestation observations must be explicit booleans")
    source_probe=_declares_readonly_generation_probe(Path(repo_root))
    observations={
        "mcp_generation_probe_declared_read_only_in_source":source_probe,
        "installed_mcp_generation_probe_exposed":installed_mcp_probe_exposed,
        "installed_gui_pinned_reader_attested":installed_gui_pinned_reader_attested,
        "semantic_child_reader_attested":semantic_child_reader_attested,
        "operational_queue_review_clean":operational_queue_review_clean,
    }
    missing=tuple(key for key,value in observations.items() if value is not True)
    return {
        "state": "DQE_SOURCE_AND_INSTALLATION_GATES_BLOCKED"
                 if missing else "DQE_EVIDENCE_PRESENT_APPROVAL_STILL_REQUIRED",
        "observations":observations,
        "missing_gates":missing,
        "source_only":True,
        "installed_process_verified_by_this_function":False,
        "live_generation_safe_to_cutover":False,
        "ready_for_operational_pilot":False,
        "activation_authorized":False,
        "operational_use_allowed":False,
        "read_only":True,
    }