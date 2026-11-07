"""AUTO canary journals must not lock the catalog after operator-driven changes."""
from __future__ import annotations

from hashlib import sha256
import json

from rag.runtime.knowledge_deletion_operational import execute_knowledge_removal
from rag.runtime.knowledge_deletion_preview import preview_knowledge_removal
from test_rag_del_close_04_operational import Close04OperationalRemovalTests, PROJECT

JOB = "9" * 32


def _sha(data: bytes) -> str:
    return sha256(data).hexdigest()


class AutoCanaryReconcileTests(Close04OperationalRemovalTests):
    def _journal(self, state, *, new_sha=None):
        catalog = self.catalog.resolve()
        pointer = (self.rag / "active-generation.json").resolve()
        backup = catalog.parent / f"auto-canary-{JOB}.previous.json"
        backup.write_bytes(catalog.read_bytes())
        journal = catalog.parent / f"auto-canary-{JOB}.journal.json"
        journal.write_text(json.dumps({
            "schema_version": 1, "state": state, "job_id": JOB, "project_id": "outro",
            "catalog": str(catalog), "backup": str(backup),
            "public_pointer_sha256": _sha(pointer.read_bytes()),
            "old_sha256": _sha(backup.read_bytes()),
            "new_sha256": new_sha or _sha(catalog.read_bytes()),
        }), encoding="utf-8")
        return journal, backup

    def _remove(self, path):
        sha = preview_knowledge_removal(PROJECT, [path])["review_sha256"]
        return execute_knowledge_removal(PROJECT, [path], sha, PROJECT)

    def _archived(self):
        folder = self.rag / "auto-canary-archive"
        return sorted(p.name for p in folder.glob("*.archived.json")) if folder.is_dir() else []

    def test_two_kept_removals_after_rolled_back_canary(self):
        journal, backup = self._journal("ROLLED_BACK")
        self._remove("alpha.py")
        self.assertFalse(journal.exists() or backup.exists())
        self.assertEqual(len(self._archived()), 1)
        # The bug: a second kept change used to fail "AUTO journal not fully reconciled".
        self._remove("bravo.py")

    def test_current_active_canary_is_accepted_by_next_change(self):
        journal, _ = self._journal("CANARY_ACTIVE")
        self._remove("alpha.py")
        self.assertFalse(journal.exists())
        note = json.loads(next((self.rag / "auto-canary-archive").glob("*.archived.json")).read_text())
        self.assertEqual(note["reason"], "CANARY_ACCEPTED")

    def test_stale_active_canary_still_blocks(self):
        journal, backup = self._journal("CANARY_ACTIVE", new_sha="0" * 64)
        catalog = self.catalog.read_bytes()
        with self.assertRaises(Exception):
            self._remove("alpha.py")
        self.assertEqual(self.catalog.read_bytes(), catalog)
        self.assertTrue(journal.exists() and backup.exists())
        self.assertEqual(self._archived(), [])


del Close04OperationalRemovalTests