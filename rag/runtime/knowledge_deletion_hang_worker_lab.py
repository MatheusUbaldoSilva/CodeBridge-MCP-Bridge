"""DEV-only scratch subprocess that intentionally never answers parent IPC.

No index, model, RAG, SQLite, or Qdrant accesses. Tests bounded parent waits.
"""
from __future__ import annotations

import sys
import time


def main() -> None:
    if len(sys.argv)!=2 or sys.argv[1] not in ("before-ready","after-ready"):
        raise PermissionError("scratch-only synthetic hang mode required")
    if sys.argv[1]=="after-ready":
        print("CHILD_VERIFIED",flush=True)
    time.sleep(45)


if __name__=="__main__":
    main()