from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from rag.runtime.knowledge_deletion_evidence import seal_deletion_candidate, inspect_deletion_candidate_evidence
from rag.runtime.auto_index_incremental_plan import IncrementalPlanError

class CandidateEvidenceTests(TestCase):
    def setUp(self):
        tmp=TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.stage=Path(tmp.name)
        (self.stage/"rag_index.sqlite3").write_bytes(b"sqlite-demo")
        (self.stage/"rag-index-manifest.json").write_bytes(b"manifest-demo")
        self.preview={"mode":"READ_ONLY_REMOVAL_PREVIEW","deletion_authorized":False,
                      "review_sha256":"a"*64,"selected_paths":["a.cpp"],"project_id":"demo",
                      "generation":"old","source_revision":"f"*64,
                      "documents_to_preserve":1,"chunks_to_preserve":2}
        self.verified={"state":"DELETION_STAGING_STRUCTURALLY_VALID",
                       "activation_authorized":False,"project_id":"demo",
                       "documents":1,"chunks":2,"vectors_verified":2}

    def seal(self, approved=True):
        return seal_deletion_candidate(self.stage,self.preview,self.verified,operator_approved=approved)

    def test_seal_and_readback_preserve_source(self):
        original=(self.stage/"rag_index.sqlite3").read_bytes()
        record=self.seal()
        inspected=inspect_deletion_candidate_evidence(self.stage)
        self.assertEqual(record["receipt_sha256"],inspected["receipt_sha256"])
        self.assertFalse(inspected["activation_authorized"])
        self.assertEqual(original,(self.stage/"rag_index.sqlite3").read_bytes())

    def test_no_approval_no_receipt(self):
        with self.assertRaises(PermissionError):
            self.seal(False)
        self.assertFalse((self.stage/"deletion-candidate-evidence.json").exists())

    def test_duplicate_receipt_refused(self):
        self.seal()
        with self.assertRaises(IncrementalPlanError):
            self.seal()

    def test_modified_sqlite_fails_inspection(self):
        self.seal()
        (self.stage/"rag_index.sqlite3").write_bytes(b"tampered")
        with self.assertRaises(IncrementalPlanError):
            inspect_deletion_candidate_evidence(self.stage)

    def test_modified_receipt_fails_inspection(self):
        self.seal()
        p=self.stage/"deletion-candidate-evidence.json"
        p.write_text(p.read_text().replace("demo","other"))
        with self.assertRaises(IncrementalPlanError):
            inspect_deletion_candidate_evidence(self.stage)

    def test_stale_verified_counts_refused(self):
        self.verified["vectors_verified"]=1
        with self.assertRaises(IncrementalPlanError):
            self.seal()

    def test_redirected_sqlite_refused(self):
        (self.stage/"rag_index.sqlite3").unlink()
        try:
            (self.stage/"rag_index.sqlite3").symlink_to(self.stage/"rag-index-manifest.json")
        except OSError:
            self.skipTest("symlink unavailable")
        with self.assertRaises(IncrementalPlanError):
            self.seal()
