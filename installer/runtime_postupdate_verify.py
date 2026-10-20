"""Fail-closed verification after a supervised offline CodeBridge update."""
from __future__ import annotations
import argparse
import json
from pathlib import Path

from installer.runtime_fingerprints import (
    collect_runtime_fingerprints, compare_runtime_fingerprints,
    compare_saved_public_baseline,
)
from installer.runtime_readiness import inspect_embedded_runtime


def verify_installed_update(install_root: Path, rag_state: Path, before: dict) -> dict:
    current = inspect_embedded_runtime(install_root)
    after = collect_runtime_fingerprints(install_root, rag_state)
    integrity = compare_runtime_fingerprints(before, after)
    ok = bool(current["ready"] and integrity["public_index_intact"])
    return {
        "state": "POST_UPDATE_PREREQUISITES_VERIFIED" if ok else "POST_UPDATE_BLOCKED",
        "installed_runtime_ready": bool(current["ready"]),
        "public_index_intact": bool(integrity["public_index_intact"]),
        "integrity": integrity,
        "does_not_activate_worker": True,
        "writes_performed": False,
        "requires_mcp_handshake": True,
        "requires_isolated_real_jina_worker_test": True,
        "deployment_approved": False,
        "phase_closed": False,
    }


def main() -> int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--install-root", type=Path, required=True)
    parser.add_argument("--rag-state", type=Path, required=True)
    parser.add_argument("--baseline-json", type=Path, required=True)
    args=parser.parse_args()
    try:
        # Historical baselines must carry the documented schema and valid hashes.
        saved_check=compare_saved_public_baseline(
            args.baseline_json,args.install_root,args.rag_state)
        if saved_check.get("state") == "PUBLIC_BASELINE_INVALID":
            raise ValueError("Invalid historical baseline")
        saved=json.loads(args.baseline_json.read_text(encoding="utf-8"))
        baseline={"files":saved["files"]}
        result=verify_installed_update(args.install_root,args.rag_state,baseline)
    except (OSError,ValueError,TypeError):
        result={"state":"POST_UPDATE_BASELINE_INVALID",
                "writes_performed":False,"installed_runtime_ready":False,
                "public_index_intact":False}
    print(json.dumps(result,sort_keys=True))
    return 0 if result["state"] == "POST_UPDATE_PREREQUISITES_VERIFIED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
