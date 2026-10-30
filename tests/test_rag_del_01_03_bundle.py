from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch
from rag.runtime.knowledge_deletion_bundle import (
    prepare_deletion_review_bundle,verify_deletion_review_bundle,DeletionBundleError,
)

class ReviewBundleTests(TestCase):
    def setUp(self):
        tmp=TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name)
        (self.root/"qdrant").mkdir()
        (self.root/"qdrant"/"store.bin").write_bytes(b"vectors")
        self.evidence={"project_id":"demo","baseline_generation":"old",
                       "selection_sha256":"a"*64,"receipt_sha256":"b"*64,
                       "activation_authorized":False}
        p=patch("rag.runtime.knowledge_deletion_bundle.inspect_deletion_candidate_evidence",
                return_value=self.evidence)
        p.start()
        self.addCleanup(p.stop)
    def test_bundle_stable_and_no_activation(self):
        bundle=prepare_deletion_review_bundle(self.root)
        self.assertFalse(bundle["operational_use_allowed"])
        self.assertFalse(bundle["activation_authorized"])
        self.assertEqual(verify_deletion_review_bundle(self.root,bundle)["state"],
                         "DELETION_REVIEW_BUNDLE_MATCHED")
    def test_qdrant_tamper_after_review_denied(self):
        bundle=prepare_deletion_review_bundle(self.root)
        (self.root/"qdrant"/"store.bin").write_bytes(b"tampered")
        with self.assertRaises(DeletionBundleError):
            verify_deletion_review_bundle(self.root,bundle)
    def test_sqlite_receipt_tamper_after_review_denied(self):
        bundle=prepare_deletion_review_bundle(self.root)
        self.evidence["receipt_sha256"]="c"*64
        with self.assertRaises(DeletionBundleError):
            verify_deletion_review_bundle(self.root,bundle)
    def test_missing_qdrant_fails(self):
        (self.root/"qdrant"/"store.bin").unlink()
        with self.assertRaises(RuntimeError):
            prepare_deletion_review_bundle(self.root)
    def test_bundle_not_authorized_for_activation(self):
        bundle=prepare_deletion_review_bundle(self.root)
        bundle["activation_authorized"]=True
        with self.assertRaises(DeletionBundleError):
            verify_deletion_review_bundle(self.root,bundle)
