from copy import deepcopy
from unittest import TestCase
from rag.runtime.knowledge_deletion_activation_review import (
    compose_deletion_activation_review,DeletionActivationReviewError,
)

class ActivationReviewContractTests(TestCase):
    def setUp(self):
        self.preview={"mode":"READ_ONLY_REMOVAL_PREVIEW","project_id":"demo",
            "deletion_authorized":False,"selected_paths":["a.cpp"],
            "source_revision":"a"*64,"generation":"baseline",
            "review_sha256":"b"*64,"chunks_to_preserve":2,"documents_to_preserve":1}
        self.preflight={"state":"PRIVATE_DELETION_PREFLIGHT_READ_ONLY","project_id":"demo",
            "expected_revision":"a"*64,"pending_deletion_transactions":0,
            "activation_authorized":False,"old_catalog_sha256":"c"*64,
            "public_pointer_sha256":"d"*64}
        self.audit={"state":"PRIVATE_REMOVAL_AUDIT_ONLY","project_id":"demo",
            "activation_authorized":False,"catalog_modified":False,
            "vectors_verified":2,"documents_verified":1,"lineage_sha256":"e"*64}
        self.row={"index_family":"RAG_DEL_01","project_id":"demo",
                  "source_revision":"f"*64,"generation_receipt_sha256":"1"*64}
        self.snapshot={"state":"SURVIVOR_SNAPSHOT_READ_ONLY_VERIFIED",
            "project_id":"demo","files_verified":1,"sources_modified":False,
            "activation_authorized":False,"snapshot_inventory_sha256":"2"*64}
        self.receipt={"project_id":"demo","source_revision":"f"*64,
            "baseline_generation":"baseline","selection_sha256":"b"*64,
            "vectors_verified":2,"activation_authorized":False}
    def review(self):
        return compose_deletion_activation_review(
            self.preview,self.preflight,self.audit,self.row,self.receipt,self.snapshot)
    def test_matching_review_never_authorizes(self):
        first=self.review()
        self.assertEqual(first,self.review())
        self.assertTrue(first["operator_confirmation_required"])
        self.assertFalse(first["activation_authorized"])
        self.assertFalse(first["catalog_modified"])
    def test_wrong_source_revision_denied(self):
        self.preflight["expected_revision"]="stale"
        with self.assertRaises(DeletionActivationReviewError):self.review()
    def test_changed_selection_denied(self):
        self.receipt["selection_sha256"]="other"
        with self.assertRaises(DeletionActivationReviewError):self.review()
    def test_incomplete_vector_validation_denied(self):
        self.audit["vectors_verified"]=1
        with self.assertRaises(DeletionActivationReviewError):self.review()
    def test_pending_transaction_denied(self):
        self.preflight["pending_deletion_transactions"]=1
        with self.assertRaises(DeletionActivationReviewError):self.review()
    def test_public_namespace_denied(self):
        self.preview["project_id"]="codebridge"
        with self.assertRaises(DeletionActivationReviewError):self.review()
    def test_short_lineage_digest_denied(self):
        self.audit["lineage_sha256"]="short"
        with self.assertRaises(DeletionActivationReviewError):self.review()
    def test_nonhex_catalog_digest_denied(self):
        self.preflight["old_catalog_sha256"]="z"*64
        with self.assertRaises(DeletionActivationReviewError):self.review()
    def test_missing_generation_receipt_digest_denied(self):
        self.row.pop("generation_receipt_sha256")
        with self.assertRaises(DeletionActivationReviewError):self.review()

    def test_stale_snapshot_proof_denied(self):
        self.snapshot["snapshot_inventory_sha256"]="invalid"
        with self.assertRaises(DeletionActivationReviewError):self.review()
    def test_mismatched_snapshot_count_denied(self):
        self.snapshot["files_verified"]=2
        with self.assertRaises(DeletionActivationReviewError):self.review()

    def test_authorized_receipt_denied(self):
        self.receipt["activation_authorized"]=True
        with self.assertRaises(DeletionActivationReviewError):self.review()
