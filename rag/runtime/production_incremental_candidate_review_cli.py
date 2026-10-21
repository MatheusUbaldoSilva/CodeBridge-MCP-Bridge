"""CLI for an explicit offline candidate P3 review; no writes or cutover."""
from __future__ import annotations

import argparse
import json

from rag.runtime.production_incremental_candidate_review import assess_offline_incremental_candidate


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Read-only RAG V1 incremental candidate assessment")
    parser.add_argument("--baseline", required=True)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--source-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        report = assess_offline_incremental_candidate(
            args.baseline, args.candidate, args.source_sha256
        )
    except (OSError, ValueError, RuntimeError) as exc:
        report = {
            "state": "BLOCKED", "issues": ["REVIEW_ERROR:" + type(exc).__name__],
            "safe_to_publish": False, "activation_authorized": False,
            "read_only": True,
        }
    print(json.dumps(report, sort_keys=True, ensure_ascii=False))
    return 0 if report["state"] == "P3_OFFLINE_VERIFIED_NOT_AUTHORIZED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
