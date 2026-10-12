"""Read-only Windows process inventory for offline RAG preflight.

This is advisory: process names cannot prove that file handles are closed.
No outcome from this module authorizes a production copy.
"""
from __future__ import annotations

import csv
import io
import subprocess


WATCHED = ("codebridge", "qdrant", "python", "uvicorn", "indexer")


def inspect_processes(*, runner=None):
    runner = runner or subprocess.run
    try:
        result = runner(["tasklist", "/fo", "csv", "/nh"],
                        capture_output=True, text=True, timeout=10, check=True)
        names = []
        for row in csv.reader(io.StringIO(result.stdout)):
            if not row:
                continue
            name = row[0].strip().casefold()
            if not name or name.startswith("info:"):
                continue
            names.append(name)
        if not names:
            raise ValueError("empty process inventory")
        blockers = sorted({name for name in names if any(w in name for w in WATCHED)})
        return {"state": "BLOCKED" if blockers else "UNPROVEN_QUIESCENCE",
                "processes_seen": len(names), "suspect_names": blockers,
                "process_listing_ok": True,
                "handles_verified": False, "copy_authorized": False,
                "publication_authorized": False}
    except (OSError, ValueError, subprocess.SubprocessError, UnicodeError) as exc:
        return {"state": "BLOCKED", "processes_seen": None,
                "suspect_names": [], "process_listing_ok": False,
                "error_type": type(exc).__name__,
                "handles_verified": False, "copy_authorized": False,
                "publication_authorized": False}
