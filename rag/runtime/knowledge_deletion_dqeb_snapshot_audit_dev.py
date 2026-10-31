"""RAG-DEL-01.04-DQ-E-B: compare GUI/MCP source snapshots read-only.

No process memory inspection: matching files do NOT attest loaded modules.
This source-only helper is never an authorization or deployment procedure.
"""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path


_GUI = Path("app_rewrite/rag_panel.py")
_HELPER = Path("rag/runtime/knowledge_deletion_public_inventory_read.py")
_MCP = Path("author_mcp/mcp_server.py")


def _file_evidence(root: Path, relative: Path, marker: str) -> dict:
    file=root / relative
    if not file.is_file() or file.is_symlink() or (
        hasattr(file,"is_junction") and file.is_junction()
    ):
        return {"exists":False,"sha256":None,"declares_marker":False}
    data=file.read_bytes()
    return {
        "exists":True,
        "sha256":sha256(data).hexdigest(),
        "declares_marker":marker in data.decode("utf-8-sig",errors="replace"),
    }


def audit_rag_reader_snapshots_dev(
    *, dev_root: Path, stable_root: Path, candidate_root: Path,
) -> dict:
    """Report observable source differences, not live runtime assurance."""
    records={}
    for name, root in (
        ("dev",Path(dev_root)),("stable",Path(stable_root)),
        ("candidate",Path(candidate_root)),
    ):
        records[name]={
            "gui":_file_evidence(root,_GUI,"read_pinned_public_document_inventory"),
            "inventory_helper":_file_evidence(
                root,_HELPER,"def read_pinned_public_document_inventory",
            ),
            "mcp":_file_evidence(root,_MCP,"codebridge_rag_generation_probe"),
        }
    return {
        "state":"DQEB_SNAPSHOT_SOURCE_ONLY_UNATTESTED",
        "snapshots":records,
        "stable_has_complete_pinned_inventory_source": (
            records["stable"]["gui"]["declares_marker"]
            and records["stable"]["inventory_helper"]["declares_marker"]
        ),
        "candidate_has_complete_pinned_inventory_source": (
            records["candidate"]["gui"]["declares_marker"]
            and records["candidate"]["inventory_helper"]["declares_marker"]
        ),
        "live_python_modules_attested":False,
        "connected_mcp_probe_attested":False,
        "safe_to_activate":False,
        "operational_use_allowed":False,
        "read_only":True,
    }