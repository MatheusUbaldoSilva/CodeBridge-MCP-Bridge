"""Offline process preflight report. Never enables production copying."""
from __future__ import annotations

import json
import sys
from rag.runtime.offline_quiescence_advisory import inspect_processes


def main():
    report = inspect_processes()
    print(json.dumps(report, sort_keys=True, ensure_ascii=False))
    return 2  # Intentionally fail closed: process inventory cannot authorize copying.


if __name__ == "__main__":
    sys.exit(main())
