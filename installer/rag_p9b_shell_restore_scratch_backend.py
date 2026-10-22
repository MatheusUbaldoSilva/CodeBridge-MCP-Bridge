"""Synthetic backend for a shell recovery rehearsal in a disposable tree.

It is not suitable for production: no registry writes or live shell links.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from zipfile import ZipFile


class ScratchShellBackend:
    def __init__(self, root):
        self.root=Path(root).absolute()
        self.root.mkdir(parents=True,exist_ok=True)
        self._used=False

    def apply(self, plan, snapshot):
        if self._used:
            raise RuntimeError("BACKEND_NOT_REUSABLE")
        self._used=True
        if plan.get("state")!="SHELL_RESTORE_PLAN_ONLY":
            raise ValueError("PLAN_NOT_VERIFIED")
        with ZipFile(snapshot) as z:
            meta=json.loads(z.read("manifest.json"))
            entries=plan["shortcut_actions"]
            if len(entries)!=5:
                raise ValueError("SLOT_COUNT_UNEXPECTED")
            for slot,entry in enumerate(entries):
                if entry.get("slot")!=slot:
                    raise ValueError("SLOT_IDENTITY_MISMATCH")
                file=self.root/f"shortcut_{slot}.bin"
                if entry["action"]=="RESTORE_PREVIOUS_FILE":
                    data=z.read(f"links/{slot}.bin")
                    if hashlib.sha256(data).hexdigest()!=meta["shortcuts"][slot]["sha256"]:
                        raise ValueError("PAYLOAD_MISMATCH")
                    file.write_bytes(data)
                elif entry["action"]=="REMOVE_NSIS_CREATED_FILE_IF_PRESENT":
                    if file.exists():
                        file.unlink()
                else:
                    raise ValueError("UNEXPECTED_ACTION")
            (self.root/"registry.json").write_text(
                json.dumps(meta["registry"],sort_keys=True),encoding="utf-8")
        return {"verified":True,"registry_modified":False,"shortcuts_modified":False}

    def verify(self, plan, snapshot):
        with ZipFile(snapshot) as z:
            meta=json.loads(z.read("manifest.json"))
            for slot,entry in enumerate(plan["shortcut_actions"]):
                file=self.root/f"shortcut_{slot}.bin"
                if entry["action"]=="RESTORE_PREVIOUS_FILE":
                    if not file.is_file() or hashlib.sha256(file.read_bytes()).hexdigest()!=meta["shortcuts"][slot]["sha256"]:
                        return {"verified":False}
                elif file.exists():
                    return {"verified":False}
            registry=json.loads((self.root/"registry.json").read_text(encoding="utf-8"))
            return {"verified":registry==meta["registry"]}
