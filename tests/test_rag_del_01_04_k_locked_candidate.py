"""RAG-DEL-01.04-K: verify candidate again while catalog CAS mutex is held."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from rag.runtime.knowledge_deletion_generation import DeletionGenerationUnavailable
from rag.runtime.knowledge_deletion_swap_lab import laboratory_swap
from rag.runtime.knowledge_deletion_verified_swap_lab import laboratory_verified_swap


class ClosedCandidateGateTests(TestCase):
    def setUp(self):
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.cat = self.root / "project-indexes.json"
        self.pointer = self.root / "active-generation.json"
        self.cat.write_text(json.dumps({"schema_version": 1, "projects": {
            "demo": {"project_id": "demo", "enabled": True,
                     "source_revision": "old", "generation_directory": "old"}
        }}), encoding="utf-8")
        self.pointer.write_text('{"schema_version":1,"generation":"public"}',
                                encoding="utf-8")
        self.before = self.cat.read_bytes()
        self.public = self.pointer.read_bytes()
        self.candidate = {"project_id": "demo", "index_family": "RAG_DEL_01",
                          "enabled": True, "source_revision": "new",
                          "generation_directory": str(self.root / "candidate"),
                          "source_directory": str(self.root / "snapshot")}

    def assert_unchanged(self):
        self.assertEqual(self.cat.read_bytes(), self.before)
        self.assertEqual(self.pointer.read_bytes(), self.public)
        self.assertFalse(list(self.root.glob("rag-del-*.journal.json")))
        self.assertFalse(list(self.root.glob("rag-del-*.previous.json")))

    @patch("rag.runtime.knowledge_deletion_verified_swap_lab.verify_deletion_generation")
    def test_candidate_mutates_after_initial_validation(self, verify):
        verify.side_effect = [None, DeletionGenerationUnavailable("candidate changed")]
        with self.assertRaises(DeletionGenerationUnavailable):
            laboratory_verified_swap(
                "demo", "old", self.candidate, catalog_file=self.cat,
                public_pointer=self.pointer,
                operator_approved=True, laboratory_mode=True)
        self.assertEqual(verify.call_count, 2)
        self.assert_unchanged()

    def test_failed_locked_validator_prevents_journal_and_write(self):
        seen = []
        def verify_under_lock():
            seen.append(self.cat.read_bytes())
            raise ValueError("generation verification failed under mutex")
        with self.assertRaises(ValueError):
            laboratory_swap("demo", "old", self.candidate, catalog_file=self.cat,
                            public_pointer=self.pointer, operator_approved=True,
                            laboratory_mode=True, _locked_validation=verify_under_lock)
        self.assertEqual(seen, [self.before])
        self.assert_unchanged()

    def test_noncallable_locked_validator_is_rejected(self):
        with self.assertRaises(Exception):
            laboratory_swap("demo", "old", self.candidate, catalog_file=self.cat,
                            public_pointer=self.pointer, operator_approved=True,
                            laboratory_mode=True, _locked_validation="fake")
        self.assert_unchanged()