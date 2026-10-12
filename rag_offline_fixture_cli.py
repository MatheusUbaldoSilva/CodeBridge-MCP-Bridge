"""Standalone test-fixture offline capture CLI. Never accepts production roots."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from rag.runtime.offline_fixture_snapshot import capture_fixture, OfflineFixtureError


def main(argv=None):
    parser = argparse.ArgumentParser(description="Offline synthetic RAG fixture snapshot only")
    parser.add_argument("--fixture-root", required=True)
    parser.add_argument("--backup-name", required=True)
    parser.add_argument("--lab-only", action="store_true", required=True)
    args = parser.parse_args(argv)
    if not args.lab_only:
        parser.error("explicit laboratory flag required")
    try:
        result = capture_fixture(Path(args.fixture_root), args.backup_name)
    except (OfflineFixtureError, OSError, ValueError) as exc:
        print(json.dumps({"state": "BLOCKED", "error": str(exc),
                          "production_authorized": False}, ensure_ascii=False))
        return 2
    print(json.dumps(result, sort_keys=True, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
