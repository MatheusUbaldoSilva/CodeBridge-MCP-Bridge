"""Archive AUTO canary journals that no longer pin the shared catalog.

The interlock (knowledge_deletion_auto_canary_interlock_lab) refuses any
catalog change while an AUTO journal exists that is not ROLLED_BACK *and*
byte-identical to the current catalog. Without this step, the first kept
deletion/merge would block every later change, and a kept new-project canary
would pin the catalog forever.

Called under the catalog mutex right before the interlock:
  * ROLLED_BACK and current catalog == journal old_sha256 -> archived;
  * CANARY_ACTIVE and current catalog == journal new_sha256 -> accepted
    (the new project is kept, like committing a removal) and archived.
Anything else is left in place, so the interlock still fails closed.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import re

ARCHIVE_DIR = "auto-canary-archive"
_NAME = re.compile(r"auto-canary-([0-9a-f]{32})\.journal\.json\Z")


def _sha(data: bytes) -> str:
    return sha256(data).hexdigest()


def archive_reconciled_auto_canaries(catalog: Path, pointer: Path) -> list[dict]:
    catalog, pointer = Path(catalog), Path(pointer)
    root = catalog.parent
    if catalog.name != "project-indexes.json" or pointer.parent != root:
        return []
    if not catalog.is_file() or not pointer.is_file():
        return []
    catalog_sha = _sha(catalog.read_bytes())
    pointer_sha = _sha(pointer.read_bytes())
    archived = []
    for journal in sorted(root.glob("auto-canary-*.journal.json")):
        match = _NAME.fullmatch(journal.name)
        if not match or journal.is_symlink() or not journal.is_file():
            continue
        job_id = match.group(1)
        backup = root / f"auto-canary-{job_id}.previous.json"
        if not backup.is_file() or backup.is_symlink():
            continue
        try:
            data = json.loads(journal.read_text(encoding="utf-8"))
        except (OSError, ValueError, UnicodeError):
            continue
        if (type(data) is not dict or data.get("schema_version") != 1
                or data.get("job_id") != job_id
                or data.get("catalog") != str(catalog)
                or data.get("backup") != str(backup)
                or data.get("public_pointer_sha256") != pointer_sha
                or _sha(backup.read_bytes()) != data.get("old_sha256")):
            continue
        state = data.get("state")
        if state == "ROLLED_BACK" and catalog_sha == data.get("old_sha256"):
            reason = "ROLLED_BACK_RECONCILED"
        elif state == "CANARY_ACTIVE" and catalog_sha == data.get("new_sha256"):
            reason = "CANARY_ACCEPTED"
        else:
            continue
        archive = root / ARCHIVE_DIR
        archive.mkdir(exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        note = {"job_id": job_id, "state_before": state, "reason": reason,
                "catalog_sha256": catalog_sha, "archived_at": stamp}
        (archive / f"auto-canary-{job_id}.{stamp}.archived.json").write_text(
            json.dumps(note, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(backup, archive / f"auto-canary-{job_id}.{stamp}.previous.json")
        os.replace(journal, archive / f"auto-canary-{job_id}.{stamp}.journal.json")
        archived.append(note)
    return archived