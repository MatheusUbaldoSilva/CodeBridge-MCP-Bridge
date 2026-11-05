"""RAG-DEL scratch atomic swap must preserve unrelated RAG-AUTO rollback receipts."""
from __future__ import annotations
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from rag.runtime.knowledge_deletion_swap_lab import (
    laboratory_swap, laboratory_rollback, DeletionSwapError,
)
from rag.runtime.knowledge_deletion_auto_canary_interlock_lab import (
    assert_no_auto_canary_catalog_pin_lab, AutoCanaryInterlockError,
)


def digest(raw: bytes) -> str:
    return sha256(raw).hexdigest()


class AutoCanaryInterlockLabTests(unittest.TestCase):
    def setUp(self):
        temp=TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root=Path(temp.name).resolve()
        self.catalog=self.root/"project-indexes.json"
        self.pointer=self.root/"active-generation.json"
        self.baseline={
            "schema_version":1,
            "projects":{
                "demo":{"project_id":"demo","enabled":True,
                        "source_revision":"old","generation_directory":"generation-old"},
                "newworldpvp":{"project_id":"newworldpvp","enabled":True,
                       "source_revision":"other","generation_directory":"generation-other"}
            }
        }
        self.catalog.write_text(json.dumps(self.baseline),encoding="utf-8")
        self.pointer.write_text(json.dumps(dict(schema_version=1,generation="public")),encoding="utf-8")
        self.candidate=dict(project_id="demo",enabled=True,
                            source_revision="new",generation_directory="generation-new")
        self.job="b"*32
        self.journal=self.root/f"auto-canary-{self.job}.journal.json"
        self.backup=self.root/f"auto-canary-{self.job}.previous.json"

    def _auto(self,state="CANARY_ACTIVE"):
        old=self.catalog.read_bytes()
        self.backup.write_bytes(old)
        record=dict(schema_version=1,state=state,job_id=self.job,
                    project_id="newworldpvp",catalog=str(self.catalog),
                    backup=str(self.backup),old_sha256=digest(old),
                    new_sha256=digest(old),
                    public_pointer_sha256=digest(self.pointer.read_bytes()))
        self.journal.write_text(json.dumps(record),encoding="utf-8")
        return record

    def _swap(self,**kwargs):
        return laboratory_swap("demo","old",self.candidate,
                               catalog_file=self.catalog,public_pointer=self.pointer,
                               operator_approved=True,laboratory_mode=True,**kwargs)

    def _assert_no_deletion_artifacts(self):
        self.assertFalse(list(self.root.glob("rag-del-*.journal.json")))
        self.assertFalse(list(self.root.glob("rag-del-*.previous.json")))

    def test_active_unrelated_canary_blocks_even_when_catalog_matches(self):
        self._auto()
        tracked=[self.catalog,self.pointer,self.journal,self.backup]
        before=[digest(p.read_bytes()) for p in tracked]
        with self.assertRaisesRegex(DeletionSwapError,"AUTO canary catalog interlock"):
            self._swap()
        self.assertEqual(before,[digest(p.read_bytes()) for p in tracked])
        self._assert_no_deletion_artifacts()

    def test_prepared_auto_canary_blocks(self):
        self._auto("PREPARED")
        with self.assertRaises(DeletionSwapError):
            self._swap()
        self._assert_no_deletion_artifacts()

    def test_orphan_auto_backup_blocks(self):
        self.backup.write_bytes(b"orphan")
        with self.assertRaises(DeletionSwapError):
            self._swap()
        self._assert_no_deletion_artifacts()

    def test_malformed_auto_journal_blocks(self):
        self._auto()
        self.journal.write_text("{bad json",encoding="utf-8")
        with self.assertRaises(DeletionSwapError):
            self._swap()
        self._assert_no_deletion_artifacts()

    def test_rolled_back_with_current_exact_old_catalog_allows_lab_swap_and_undo(self):
        self._auto("ROLLED_BACK")
        start=self.catalog.read_bytes()
        original_pointer=self.pointer.read_bytes()
        result=self._swap()
        self.assertEqual(result["state"],"LAB_SWAP_ACTIVE")
        self.assertEqual(json.loads(self.catalog.read_text())["projects"]["newworldpvp"],
                         self.baseline["projects"]["newworldpvp"])
        self.assertEqual(self.pointer.read_bytes(),original_pointer)
        restored=laboratory_rollback(
            result["transaction"],catalog_file=self.catalog,public_pointer=self.pointer,
            operator_approved=True,laboratory_mode=True)
        self.assertEqual(restored["state"],"LAB_ROLLBACK_COMPLETE")
        self.assertEqual(self.catalog.read_bytes(),start)
        self.assertEqual(self.pointer.read_bytes(),original_pointer)

    def test_rolled_back_with_changed_catalog_hash_blocks(self):
        self._auto("ROLLED_BACK")
        record=json.loads(self.journal.read_text())
        record["old_sha256"]="0"*64
        self.journal.write_text(json.dumps(record),encoding="utf-8")
        with self.assertRaises(DeletionSwapError):
            self._swap()
        self._assert_no_deletion_artifacts()

    def test_pointer_changed_since_auto_journal_blocks(self):
        self._auto("ROLLED_BACK")
        self.pointer.write_text(json.dumps(dict(schema_version=1,generation="changed")),
                                encoding="utf-8")
        with self.assertRaises(DeletionSwapError):
            self._swap()
        self._assert_no_deletion_artifacts()

    def test_without_auto_receipts_existing_lab_swap_and_rollback_work(self):
        start=self.catalog.read_bytes()
        result=self._swap()
        self.assertEqual(result["state"],"LAB_SWAP_ACTIVE")
        self.assertEqual(laboratory_rollback(
            result["transaction"],catalog_file=self.catalog,public_pointer=self.pointer,
            operator_approved=True,laboratory_mode=True)["state"],
            "LAB_ROLLBACK_COMPLETE")
        self.assertEqual(self.catalog.read_bytes(),start)

    def test_canary_created_by_locked_validation_is_rechecked_before_write(self):
        original=self.catalog.read_bytes()
        def add_auto_canary_inside_lock():
            self._auto("CANARY_ACTIVE")
        with self.assertRaisesRegex(DeletionSwapError,"AUTO canary catalog interlock"):
            self._swap(_locked_validation=add_auto_canary_inside_lock)
        self._assert_no_deletion_artifacts()
        self.assertEqual(self.catalog.read_bytes(),original)
        self.assertTrue(self.journal.is_file())

    def test_rolled_back_auto_canary_and_interrupted_deletion_restore(self):
        self._auto("ROLLED_BACK")
        before=self.catalog.read_bytes()
        sha=digest(self.journal.read_bytes())
        with self.assertRaisesRegex(DeletionSwapError,"injected post-switch failure"):
            self._swap(_fail_at="after")
        self.assertEqual(len(list(self.root.glob("rag-del-*.journal.json"))),1)
        self.assertEqual(digest(self.journal.read_bytes()),sha)
        job=next(self.root.glob("rag-del-*.journal.json"))
        tid=job.name[len("rag-del-"):-len(".journal.json")]
        result=laboratory_rollback(
            tid,catalog_file=self.catalog,public_pointer=self.pointer,
            operator_approved=True,laboratory_mode=True)
        self.assertEqual(result["state"],"LAB_ROLLBACK_COMPLETE")
        self.assertEqual(self.catalog.read_bytes(),before)
        self.assertEqual(digest(self.journal.read_bytes()),sha)

    def test_interlock_disallows_symlinked_journal_if_supported(self):
        self._auto()
        target=self.root/"outside.json"
        target.write_text(self.journal.read_text(),encoding="utf-8")
        self.journal.unlink()
        try:
            self.journal.symlink_to(target)
        except (OSError,NotImplementedError):
            self.skipTest("symlinks not supported")
        with self.assertRaises(DeletionSwapError):
            self._swap()
        self._assert_no_deletion_artifacts()
