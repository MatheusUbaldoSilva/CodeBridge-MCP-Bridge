"""Real RAG-AUTO canary -> RAG-DEL lab interlock integration; temp only."""
from __future__ import annotations
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import test_rag_auto_03_canary as auto_fixture
from rag.runtime.knowledge_deletion_swap_lab import (
    laboratory_swap, laboratory_rollback, DeletionSwapError
)


class AutoToDeletionInterlockIntegration(unittest.TestCase):
    prepare=auto_fixture.AutoCanaryTests.prepare
    activate=auto_fixture.AutoCanaryTests.activate
    rollback=auto_fixture.AutoCanaryTests.rollback

    def setUp(self):
        # Existing AUTO real scratch queue/generation/vector fixture.
        auto_fixture.AutoCanaryTests.setUp(self)
        scratch=TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.catalog_root=Path(scratch.name).resolve()
        self.catalog=self.catalog_root/"project-indexes.json"
        self.pointer=self.catalog_root/"active-generation.json"
        before={
            "schema_version":1,
            "projects":{"demo":{
                "enabled":True,"project_id":"demo",
                "source_revision":"old",
                "generation_directory":"demo-generation-old",
            }}
        }
        self.catalog.write_text(json.dumps(before),encoding="utf-8")
        self.pointer.write_text(
            json.dumps(dict(schema_version=1,generation="public-untouched")),
            encoding="utf-8"
        )
        self.before=self.catalog.read_bytes()
        self.public=self.pointer.read_bytes()
        self.candidate={
            "enabled":True,"project_id":"demo",
            "source_revision":"new",
            "generation_directory":"demo-generation-new",
        }

    def _del_swap(self):
        return laboratory_swap(
            "demo","old",self.candidate,catalog_file=self.catalog,
            public_pointer=self.pointer,operator_approved=True,
            laboratory_mode=True
        )

    def test_actual_auto_canary_interlock_then_explicit_rollback_and_del_recovery(self):
        activated=self.activate()
        self.assertEqual(activated["state"],"ISOLATED_CANARY_ACTIVE")
        self.assertEqual(self.pointer.read_bytes(),self.public)
        live_catalog=self.catalog.read_bytes()
        auto_journal=Path(activated["journal"])
        auto_before=auto_journal.read_bytes()
        with self.assertRaisesRegex(DeletionSwapError,"AUTO canary catalog interlock"):
            self._del_swap()
        self.assertEqual(self.catalog.read_bytes(),live_catalog)
        self.assertEqual(auto_journal.read_bytes(),auto_before)
        self.assertFalse(list(self.catalog_root.glob("rag-del-*.journal.json")))
        # Actual AUTO rollback, with its exact job confirmation, in scratch.
        restored=self.rollback()
        self.assertEqual(restored["state"],"RESTORED_PREVIOUS_CATALOG")
        self.assertEqual(self.catalog.read_bytes(),self.before)
        auto_rolled_back=auto_journal.read_bytes()
        # Now RAG-DEL works, and its own journaled rollback is intact.
        deletion=self._del_swap()
        self.assertEqual(deletion["state"],"LAB_SWAP_ACTIVE")
        self.assertEqual(self.pointer.read_bytes(),self.public)
        self.assertEqual(
            json.loads(self.catalog.read_text())["projects"]["demo"],
            self.candidate,
        )
        self.assertEqual(auto_journal.read_bytes(),auto_rolled_back)
        ended=laboratory_rollback(
            deletion["transaction"],catalog_file=self.catalog,
            public_pointer=self.pointer,operator_approved=True,
            laboratory_mode=True,
        )
        self.assertEqual(ended["state"],"LAB_ROLLBACK_COMPLETE")
        self.assertEqual(self.catalog.read_bytes(),self.before)
        self.assertEqual(self.pointer.read_bytes(),self.public)
        self.assertEqual(auto_journal.read_bytes(),auto_rolled_back)
        # AUTO canary can be activated again AFTER full rollback.
        again=self.activate()
        self.assertEqual(again["state"],"ISOLATED_CANARY_ACTIVE")
        self.assertEqual(self.rollback()["state"],"RESTORED_PREVIOUS_CATALOG")
        self.assertEqual(self.catalog.read_bytes(),self.before)


if __name__=="__main__":
    unittest.main()
