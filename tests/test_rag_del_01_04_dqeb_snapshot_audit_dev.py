"""RAG-DEL-01.04-DQ-E-B: source snapshot is not loaded GUI attestation."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from rag.runtime.knowledge_deletion_dqeb_snapshot_audit_dev import (
    audit_rag_reader_snapshots_dev,
)


class SnapshotSourceOnlyAudits(TestCase):
    def setUp(self):
        temp=TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.tmp=Path(temp.name)
        self.dev=self.tmp/"dev"
        self.stable=self.tmp/"stable"
        self.candidate=self.tmp/"candidate"
        for root in (self.dev,self.stable,self.candidate):
            (root/"app_rewrite").mkdir(parents=True)
            (root/"rag"/"runtime").mkdir(parents=True)
            (root/"author_mcp").mkdir(parents=True)

    def audit(self):
        return audit_rag_reader_snapshots_dev(
            dev_root=self.dev,stable_root=self.stable,candidate_root=self.candidate,
        )

    def write(self,root,relative,text):
        p=root/relative
        p.write_text(text,encoding="utf-8")

    def test_missing_helpers_cannot_pass_when_gui_mentions_function(self):
        self.write(self.stable,"app_rewrite/rag_panel.py",
                   "read_pinned_public_document_inventory()")
        row=self.audit()
        self.assertTrue(row["snapshots"]["stable"]["gui"]["declares_marker"])
        self.assertFalse(row["stable_has_complete_pinned_inventory_source"])
        self.assertFalse(row["safe_to_activate"])

    def test_identical_source_snapshots_still_do_not_attest_loaded_process(self):
        for root in (self.dev,self.stable,self.candidate):
            self.write(root,"app_rewrite/rag_panel.py",
                       "read_pinned_public_document_inventory()")
            self.write(root,
                       "rag/runtime/knowledge_deletion_public_inventory_read.py",
                       "def read_pinned_public_document_inventory(): pass")
            self.write(root,"author_mcp/mcp_server.py",
                       "codebridge_rag_generation_probe")
        row=self.audit()
        self.assertTrue(row["stable_has_complete_pinned_inventory_source"])
        self.assertTrue(row["candidate_has_complete_pinned_inventory_source"])
        self.assertEqual(
            row["snapshots"]["stable"]["gui"]["sha256"],
            row["snapshots"]["dev"]["gui"]["sha256"],
        )
        self.assertFalse(row["live_python_modules_attested"])
        self.assertFalse(row["connected_mcp_probe_attested"])
        self.assertFalse(row["operational_use_allowed"])

    def test_candidate_cannot_inherit_dev_evidence(self):
        self.write(self.dev,"app_rewrite/rag_panel.py",
                   "read_pinned_public_document_inventory()")
        self.write(self.dev,
                   "rag/runtime/knowledge_deletion_public_inventory_read.py",
                   "def read_pinned_public_document_inventory(): pass")
        row=self.audit()
        self.assertTrue(row["snapshots"]["dev"]["gui"]["declares_marker"])
        self.assertFalse(row["candidate_has_complete_pinned_inventory_source"])
        self.assertFalse(row["stable_has_complete_pinned_inventory_source"])

    def test_file_content_changes_are_reported_by_hash_not_hidden(self):
        self.write(self.stable,"app_rewrite/rag_panel.py","old")
        self.write(self.candidate,"app_rewrite/rag_panel.py","changed")
        row=self.audit()
        self.assertNotEqual(
            row["snapshots"]["stable"]["gui"]["sha256"],
            row["snapshots"]["candidate"]["gui"]["sha256"],
        )
        self.assertFalse(row["safe_to_activate"])