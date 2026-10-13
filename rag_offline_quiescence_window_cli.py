"""Read-only synthetic offline quiescence-window CLI; never authorizes copying."""
from __future__ import annotations
import argparse
import json
import sys
from rag.runtime.offline_quiescence_window import inspect_synthetic_quiet_window


def main(argv=None):
    parser = argparse.ArgumentParser(description="Synthetic RAG quiescence audit only")
    parser.add_argument("--fixture-root", required=True)
    parser.add_argument("--lab-only", action="store_true", required=True)
    args = parser.parse_args(argv)
    report = inspect_synthetic_quiet_window(args.fixture_root)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 2  # No outcome is sufficient for real backup authorization.


if __name__ == "__main__":
    sys.exit(main())
