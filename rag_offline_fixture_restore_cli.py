"""Standalone isolated restore of synthetic RAG fixture snapshots."""
from __future__ import annotations

import argparse
import json
import sys

from rag.runtime.offline_fixture_restore import restore_fixture_snapshot


def main(argv=None):
    parser = argparse.ArgumentParser(description="Synthetic RAG fixture restore only")
    parser.add_argument("--fixture-root", required=True)
    parser.add_argument("--backup-name", required=True)
    parser.add_argument("--restore-name", required=True)
    parser.add_argument("--lab-only", action="store_true", required=True)
    args = parser.parse_args(argv)
    try:
        outcome = restore_fixture_snapshot(args.fixture_root, args.backup_name, args.restore_name)
    except Exception as exc:
        print(json.dumps({"state": "BLOCKED", "error_type": type(exc).__name__,
                          "production_authorized": False}))
        return 2
    print(json.dumps(outcome, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
