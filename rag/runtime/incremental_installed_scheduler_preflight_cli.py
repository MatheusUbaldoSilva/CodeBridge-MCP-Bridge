"""Operator command: inspect installed scheduling without enabling workers."""
from __future__ import annotations

import json
from rag.runtime.incremental_installed_scheduler_preflight import inspect_installed_scheduler_preflight
from rag.runtime.incremental_scheduler_public_pointer import inspect_public_pointer_for_scheduler


def main() -> int:
    report = inspect_installed_scheduler_preflight()
    report['public_pointer'] = inspect_public_pointer_for_scheduler()
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
