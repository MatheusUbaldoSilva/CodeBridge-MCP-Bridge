"""DQ-E-D-3C-E-2: TEMP-only parent owns Win32 locks and child pipe.

Parent launch is solely for subprocess tests. It does not contact an installed
MCP, run models, or authorize generation cutover/deletion.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
from threading import Thread
from unittest.mock import patch

from rag.runtime.knowledge_deletion_bounded_catalog_lab import _validated_scratch_catalog
from rag.runtime.knowledge_deletion_private_read_session_lab import private_read_session_lab
from rag.runtime.knowledge_deletion_pin_ipc_lab import envelope_from_private_lab_pin
from rag.runtime.knowledge_deletion_semantic_request_lab import PinnedSemanticRequestV1
from rag.runtime.knowledge_deletion_vector_tree_receipt_lab import create_vector_tree_receipt_lab
from rag.runtime.production_generation_lock import production_generation_lock


def _read_parent_confirmation_bounded(seconds: float = 6.0) -> str | None:
    lines: list[str] = []
    def read():
        lines.append(sys.stdin.readline(100))
    thread=Thread(target=read,daemon=True)
    thread.start()
    thread.join(seconds)
    if thread.is_alive():
        return None
    return lines[0] if lines else ""


def main() -> None:
    if len(sys.argv)!=2:
        raise PermissionError("only trusted scratch root argument allowed")
    catalog,root=_validated_scratch_catalog(Path(sys.argv[1])/"project-indexes.json")
    db=root/"generations"/"private_liveness"/"rag_index.sqlite3"
    manifest=db.with_name("rag-index-manifest.json")
    child=None
    with patch(
        "rag.runtime.production_generation_lock.resolve_rag_sqlite_path",
        return_value=root/"CodeBridge"/"rag"/"rag_index.sqlite3",
    ):
        with private_read_session_lab(
            "private-lab",catalog_file=catalog,
            sqlite_path=db,manifest_path=manifest,
            generation_guard_factory=lambda:production_generation_lock(
                exclusive=False,channel="generation",
            ),
            semantic_guard_factory=lambda:production_generation_lock(
                exclusive=True,channel="semantic",
            ),
            semantic=True,laboratory_mode=True,operator_approved=True,
        ) as pin:
            envelope=envelope_from_private_lab_pin(
                pin,catalog_file=catalog,laboratory_mode=True,
            )
            request=PinnedSemanticRequestV1.parse({
                "schema_version":1,"pin":envelope.to_payload(),
                "query":"synthetic liveness","route":"CODE","top_k":1,
                "source_types":[],"path_filter":None,"branch":None,
            })
            receipt=create_vector_tree_receipt_lab(
                envelope,catalog_file=catalog,laboratory_mode=True,
            )
            if not receipt.files:
                raise RuntimeError("non-empty vector tree required for liveness test")
            try:
                child=subprocess.Popen(
                    [sys.executable,"-m",
                     "rag.runtime.knowledge_deletion_liveness_child_lab",
                     str(root),str(os.getpid())],
                    cwd=str(Path(__file__).resolve().parents[2]),
                    stdin=subprocess.PIPE,stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,text=True,
                )
                child.stdin.write(json.dumps({
                    "request":request.to_payload(),
                    "tree_sha256":receipt.tree_sha256,
                })+"\n")
                child.stdin.flush()
                first=child.stdout.readline().strip()
                if first!="CHILD_VERIFIED":
                    raise RuntimeError("scratch child failed preflight")
                print("PARENT_READY "+str(child.pid),flush=True)
                command=_read_parent_confirmation_bounded()
                if command!="ACK\n":
                    raise RuntimeError("scratch parent received no ACK")
                child.stdin.write("ACK "+envelope.nonce+"\n")
                child.stdin.flush()
                answer=child.stdout.readline()
                if not answer:
                    raise RuntimeError("scratch child disappeared before response")
                body=json.loads(answer)
                if (body.get("state")!="LAB_CHILD_COMPLETED_WHILE_PARENT_PIPE_OPEN"
                        or body.get("nonce")!=envelope.nonce
                        or body.get("request_sha256")!=request.request_digest()
                        or body.get("tree_sha256")!=receipt.tree_sha256
                        or body.get("operational_use_allowed") is not False):
                    raise RuntimeError("scratch child correlation failed")
                # No locks released until the response has been validated.
                if child.wait(timeout=3)!=0:
                    raise RuntimeError("scratch child completion failed")
                print("PARENT_CONFIRMED",flush=True)
            finally:
                if child is not None:
                    if child.poll() is None:
                        child.kill()
                        child.wait(timeout=3)
                    for stream in (child.stdin,child.stdout,child.stderr):
                        if stream is not None:
                            stream.close()


if __name__=="__main__":
    main()