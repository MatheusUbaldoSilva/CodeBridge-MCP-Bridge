"""DQ-E-F-2 journal review tests (scratch only)."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from hashlib import sha256
from rag.runtime.knowledge_deletion_journal_inventory_dev import inspect_deletion_journals_read_only
from rag.runtime.knowledge_deletion_swap_lab import _journal_payload

class JournalInventoryDevTests(TestCase):
    def setUp(self):
        t=TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.root=Path(t.name)
    def inspect(self):
        return inspect_deletion_journals_read_only(self.root)
    def create(self, state):
        tid="a"*32
        backup=self.root/("rag-del-"+tid+".previous.json")
        backup.write_bytes(b"original")
        j=self.root/("rag-del-"+tid+".journal.json")
        j.write_bytes(_journal_payload(dict(schema_version=1,transaction=tid,
            catalog=str(self.root/"project-indexes.json"),backup=str(backup),
            old_sha256=sha256(b"original").hexdigest(),state=state)))
        return j,backup
    def test_empty_is_clean_but_never_authorized(self):
        r=self.inspect()
        self.assertEqual(r["state"],"DELETION_JOURNAL_INVENTORY_READ_ONLY_CLEAN")
        self.assertFalse(r["activation_authorized"])
    def test_rolled_back_is_clean(self):
        self.create("ROLLED_BACK")
        self.assertEqual(self.inspect()["blockers"],[])
    def test_prepared_blocks(self):
        self.create("PREPARED")
        self.assertIn("UNRESOLVED_TRANSACTION",self.inspect()["blockers"])
    def test_active_blocks(self):
        self.create("ACTIVE")
        self.assertEqual(self.inspect()["unresolved"],1)
    def test_missing_backup_blocks(self):
        _,b=self.create("ROLLED_BACK")
        b.unlink()
        self.assertIn("JOURNAL_BACKUP_MISSING_OR_REDIRECTED",self.inspect()["blockers"])
    def test_tampered_journal_blocks(self):
        j,_=self.create("ROLLED_BACK")
        j.write_text(j.read_text().replace("ROLLED_BACK","ACTIVE"))
        self.assertIn("INVALID_JOURNAL_EVIDENCE",self.inspect()["blockers"])
    def test_orphan_backup_blocks(self):
        (self.root/("rag-del-"+("b"*32)+".previous.json")).write_bytes(b"x")
        self.assertIn("ORPHAN_BACKUP",self.inspect()["blockers"])
    def test_relative_directory_blocks(self):
        self.assertIn("INVALID_CATALOG_DIRECTORY",
            inspect_deletion_journals_read_only(Path("relative"))["blockers"])
