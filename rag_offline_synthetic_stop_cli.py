"""Standalone graceful-stop laboratory drill (synthetic child process only)."""
from __future__ import annotations

import argparse
import json
import sys
from rag.runtime.offline_synthetic_stop_trial import run_synthetic_stop_trial


def main(argv=None):
    parser = argparse.ArgumentParser(description="Synthetic RAG child shutdown drill")
    parser.add_argument("--fixture-root", required=True)
    parser.add_argument("--lab-only", action="store_true", required=True)
    args = parser.parse_args(argv)
    try:
        report = run_synthetic_stop_trial(args.fixture_root)
    except Exception as exc:
        print(json.dumps({"state": "BLOCKED", "error_type": type(exc).__name__,
                          "copy_authorized": False, "production_quiescence_proven": False}))
        return 2
    print(json.dumps(report, sort_keys=True, ensure_ascii=False))
    return 0  # success only for a synthetic lab drill, not for copy authorization


if __name__ == "__main__":
    sys.exit(main())
