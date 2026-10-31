"""Manual G-13 DEV scratch IPC soak, never runs real indexing/deletion."""
from __future__ import annotations
import argparse
import json
import time
from rag.runtime.knowledge_deletion_mac_pipe_parent_lab import scratch_mac_pipe_roundtrip

def soak(iterations:int=20)->dict:
    if type(iterations) is not int or not 1<=iterations<=500:
        raise ValueError("iterations must be 1..500")
    started=time.monotonic()
    for _ in range(iterations):
        proof=scratch_mac_pipe_roundtrip(entrypoint="real-worker")
        if not (proof.get("mac_verified") is True
                and proof.get("spawned_pid_matches_response") is True
                and proof.get("win32_birth_matches_response") is True
                and proof.get("activation_authorized") is False
                and proof.get("operational_use_allowed") is False):
            raise RuntimeError("scratch proof failed closed")
    return dict(state="SCRATCH_REAL_WORKER_SOAK_PASS",iterations=iterations,
        elapsed_seconds=round(time.monotonic()-started,3),
        activation_authorized=False,operational_use_allowed=False)

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--iterations",type=int,default=20)
    args=parser.parse_args()
    print(json.dumps(soak(args.iterations),sort_keys=True))
