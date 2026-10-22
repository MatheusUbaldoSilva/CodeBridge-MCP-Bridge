"""Operator command: inspect installed scheduling without enabling workers."""
from __future__ import annotations

import argparse
import json
from rag.runtime.incremental_installed_scheduler_preflight import inspect_installed_scheduler_preflight
from rag.runtime.incremental_scheduler_public_pointer import inspect_public_pointer_for_scheduler
from rag.runtime.incremental_installed_queue_bootstrap_preflight import inspect_installed_queue_bootstrap


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Read-only installed RAG scheduler diagnosis")
    parser.add_argument("--require-ready", action="store_true",
                        help="exit 2 when prerequisites have not been observed")
    parser.add_argument("--show-bootstrap", action="store_true",
                        help="include read-only diagnosis of the installed job storage")
    args = parser.parse_args(argv)
    report = inspect_installed_scheduler_preflight()
    report['public_pointer'] = inspect_public_pointer_for_scheduler()
    if args.show_bootstrap:
        report["bootstrap"] = inspect_installed_queue_bootstrap()
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 2 if (args.require_ready and report["state"] != "PREREQUISITES_OBSERVED_ONLY") else 0


if __name__ == "__main__":
    raise SystemExit(main())
