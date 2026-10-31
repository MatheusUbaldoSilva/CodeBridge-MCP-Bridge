"""Scratch-only IPC verifier. NOT a semantic inference worker."""
from __future__ import annotations

import json
from pathlib import Path
import sys

from rag.runtime.knowledge_deletion_pin_ipc_lab import (
    PrivateReadPinEnvelopeV1, verify_private_pin_envelope_lab,
)


def main() -> None:
    hold_for_ack=len(sys.argv) == 3 and sys.argv[2] == "--hold-for-ack"
    semantic_request=len(sys.argv) == 3 and sys.argv[2] == "--semantic-request"
    if len(sys.argv) != 2 and not (hold_for_ack or semantic_request):
        raise ValueError("one trusted scratch lab root argument required")
    root=Path(sys.argv[1])
    raw=sys.stdin.readline(8193)
    if len(raw) > 8192:
        raise ValueError("oversized scratch envelope")
    if semantic_request:
        from rag.runtime.knowledge_deletion_semantic_request_lab import (
            PinnedSemanticRequestV1, verify_pinned_semantic_request_lab,
        )
        request=PinnedSemanticRequestV1.parse(json.loads(raw))
        response=verify_pinned_semantic_request_lab(
            request,catalog_file=root/"project-indexes.json",
            laboratory_mode=True,
        )
    else:
        envelope=PrivateReadPinEnvelopeV1.parse(json.loads(raw))
        response=verify_private_pin_envelope_lab(
            envelope,catalog_file=root/"project-indexes.json",
            laboratory_mode=True,
        )
    if hold_for_ack:
        # A test-only handshake holds the CHILD active while another process
        # attempts an exclusive writer lock against the parent's live pin.
        print("LAB_CHILD_VERIFIED",flush=True)
        if sys.stdin.readline(16) != "ACK\n":
            raise ValueError("scratch IPC handshake not acknowledged")
    print(json.dumps(response,sort_keys=True))


if __name__=="__main__":
    main()