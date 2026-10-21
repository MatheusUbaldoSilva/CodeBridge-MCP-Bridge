"""Real closed-bundle content review + independent exact source scope, isolated."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parent))
from test_incremental_bundle_e2e import create_bundle
from rag.runtime.production_content_review import summarize_versioned_source_review
from rag.runtime.production_source_scope_attestation import inspect_approved_source_scope
from rag.chunking.provenance import source_sha256


class RealClosedBundleReviewTests(unittest.TestCase):
    def test_approved_added_source_matches_closed_bundle_review_without_activation(self):
        with tempfile.TemporaryDirectory(prefix="codebridge-p3-source-") as temp:
            root=Path(temp)/"generations"
            root.mkdir()
            old=root/"v1_base_test"
            new=root/"v1_delta_test"
            create_bundle(old,[("codebridge","same","stable text")])
            create_bundle(new,[("codebridge","same","stable text"),
                               ("codebridge","new","new code text")])
            review=summarize_versioned_source_review(old,new)
            self.assertEqual(review["added_paths"],["new.md"])
            self.assertFalse(review["safe_to_activate"])
            exact=inspect_approved_source_scope(review,{
                "new.md":source_sha256("new code text"),
            },expected_fingerprint=review["evidence_sha256_not_signature"])
            self.assertEqual(exact["state"],"SCOPE_MATCHED_NOT_AUTHORIZED")
            self.assertFalse(exact["safe_to_publish"])
            bad=inspect_approved_source_scope(review,{
                "new.md":source_sha256("different content"),
            },expected_fingerprint=review["evidence_sha256_not_signature"])
            self.assertEqual(bad["state"],"SCOPE_BLOCKED")

    def test_changed_existing_source_not_covered_by_only_new_source_approval(self):
        with tempfile.TemporaryDirectory(prefix="codebridge-p3-source-") as temp:
            root=Path(temp)/"generations"
            root.mkdir()
            old=root/"v1_base_test"
            new=root/"v1_delta_test"
            create_bundle(old,[("codebridge","same","stable text")])
            create_bundle(new,[("codebridge","same","changed text"),
                               ("codebridge","new","new code text")])
            review=summarize_versioned_source_review(old,new)
            self.assertEqual(review["modified_paths"],["same.md"])
            exact=inspect_approved_source_scope(review,{
                "new.md":source_sha256("new code text"),
            },expected_fingerprint=review["evidence_sha256_not_signature"])
            self.assertEqual(exact["state"],"SCOPE_BLOCKED")
            self.assertIn("SOURCE_PATH_SCOPE_MISMATCH",exact["issues"])
