"""Fail-closed RAG-AUTO canary interlock for RAG-DEL scratch catalog swaps.

Called only after the existing _lab_paths and canonical catalog mutex have
validated the scratch root. Active/incomplete AUTO journals block ANY shared
catalog modification, even for a different private project. Fully rolled-back
journals must match the *current* old-catalog digest or also block.

This is a guard, not an AUTO canary rollback or lineage migration.
"""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import re

_ID = re.compile(r"[0-9a-f]{32}\Z")


class AutoCanaryInterlockError(RuntimeError):
    pass


def assert_no_auto_canary_catalog_pin_lab(catalog: Path, pointer: Path) -> dict:
    catalog=Path(catalog)
    pointer=Path(pointer)
    root=catalog.parent
    if catalog.name!="project-indexes.json" or pointer.parent!=root:
        raise AutoCanaryInterlockError("scratch catalog and pointer must share directory")
    if (not catalog.is_file() or catalog.is_symlink()
            or not pointer.is_file() or pointer.is_symlink()):
        raise AutoCanaryInterlockError("unsafe scratch shared catalog")
    before=catalog.read_bytes()
    public=pointer.read_bytes()
    if len(before)>1048576 or len(public)>1048576:
        raise AutoCanaryInterlockError("unbounded catalog or pointer")
    catalog_sha=sha256(before).hexdigest()
    pointer_sha=sha256(public).hexdigest()
    journals=list(root.glob("auto-canary-*.journal.json"))
    backups=list(root.glob("auto-canary-*.previous.json"))
    if len(journals)>100 or len(backups)>100:
        raise AutoCanaryInterlockError("unbounded AUTO canary receipts")
    pairs=set()
    for journal in journals:
        name=journal.name
        match=re.fullmatch(r"auto-canary-([0-9a-f]{32})\.journal\.json",name)
        if not match:
            raise AutoCanaryInterlockError("malformed AUTO journal name")
        job_id=match.group(1)
        backup=root/f"auto-canary-{job_id}.previous.json"
        if (not journal.is_file() or journal.is_symlink()
                or not backup.is_file() or backup.is_symlink()
                or journal.stat().st_size>1048576
                or backup.stat().st_size>1048576):
            raise AutoCanaryInterlockError("incomplete or unsafe AUTO receipts")
        try:
            data=json.loads(journal.read_text(encoding="utf-8"))
        except (ValueError,UnicodeError) as exc:
            raise AutoCanaryInterlockError("unreadable AUTO journal") from exc
        if (type(data) is not dict or data.get("schema_version")!=1
                or data.get("job_id")!=job_id
                or data.get("catalog")!=str(catalog)
                or data.get("backup")!=str(backup)
                or data.get("public_pointer_sha256")!=pointer_sha
                or sha256(backup.read_bytes()).hexdigest()!=data.get("old_sha256")):
            raise AutoCanaryInterlockError("AUTO catalog lineage cannot be established")
        state=data.get("state")
        if state in ("PREPARED","CANARY_ACTIVE"):
            # Even a valid unrelated active journal pins the whole catalog.
            raise AutoCanaryInterlockError("AUTO_CANARY_PINS_SHARED_CATALOG")
        if state!="ROLLED_BACK" or catalog_sha!=data.get("old_sha256"):
            raise AutoCanaryInterlockError("AUTO journal not fully reconciled")
        pairs.add(backup)
    if set(backups)!=pairs:
        raise AutoCanaryInterlockError("orphan AUTO backup")
    if sha256(catalog.read_bytes()).hexdigest()!=catalog_sha or sha256(pointer.read_bytes()).hexdigest()!=pointer_sha:
        raise AutoCanaryInterlockError("shared catalog drift during interlock")
    return {
        "state":"SCRATCH_AUTO_CANARY_INTERLOCK_CLEAR",
        "read_only":True,
        "rolled_back_receipts":len(pairs),
        "active_auto_canary_count":0,
        "catalog_sha256":catalog_sha,
        "public_pointer_sha256":pointer_sha,
        "activation_authorized":False,
    }
