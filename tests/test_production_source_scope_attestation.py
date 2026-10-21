import unittest

from rag.runtime.production_source_scope_attestation import inspect_approved_source_scope

P = "rag/runtime/incremental_scheduler_gate.py"
SHA = "6d0e790e82ee9bea7f163cf0b5244accc794a87bf6032d97144f73ab21c3feed"
REVIEW_SHA = "a"*64


def review():
    return {
        "state": "CONTENT_COMPARISON_ONLY_NOT_APPROVED",
        "evidence_sha256_not_signature": REVIEW_SHA,
        "added_paths": [P], "modified_paths": [], "removed_paths": [],
        "details": [{"path": P, "action": "ADDED", "candidate_sha256": SHA}],
    }


class ExactSourceScopeReviewTests(unittest.TestCase):
    def test_matching_is_never_an_authorization(self):
        r=inspect_approved_source_scope(review(), {P: SHA}, expected_fingerprint=REVIEW_SHA)
        self.assertEqual(r["state"],"SCOPE_MATCHED_NOT_AUTHORIZED")
        self.assertFalse(r["activation_authorized"])
        self.assertFalse(r["safe_to_publish"])

    def test_wrong_sha_wrong_path_and_fingerprint_all_block(self):
        cases=[({P:"b"*64}, REVIEW_SHA), ({"other.py": SHA}, REVIEW_SHA),
               ({P:SHA}, "b"*64)]
        for approved, fingerprint in cases:
            with self.subTest(approved=approved,fingerprint=fingerprint):
                r=inspect_approved_source_scope(review(), approved,
                    expected_fingerprint=fingerprint)
                self.assertEqual(r["state"],"SCOPE_BLOCKED")

    def test_unreviewed_second_source_blocks(self):
        r=review()
        r["added_paths"].append("unexpected.py")
        r["details"].append({"path":"unexpected.py","action":"ADDED",
                             "candidate_sha256":"b"*64})
        observed=inspect_approved_source_scope(r,{P:SHA},expected_fingerprint=REVIEW_SHA)
        self.assertEqual(observed["state"],"SCOPE_BLOCKED")

    def test_source_removal_and_duplicate_rows_block(self):
        r=review()
        r["removed_paths"]=["existing.py"]
        self.assertEqual(inspect_approved_source_scope(r,{P:SHA},
            expected_fingerprint=REVIEW_SHA)["state"],"SCOPE_BLOCKED")
        r=review()
        r["details"].append(r["details"][0].copy())
        self.assertEqual(inspect_approved_source_scope(r,{P:SHA},
            expected_fingerprint=REVIEW_SHA)["state"],"SCOPE_BLOCKED")

    def test_missing_approval_and_invalid_review_block(self):
        for record, approved in [(review(),{}), ({}, {P:SHA})]:
            self.assertEqual(inspect_approved_source_scope(record,approved,
                expected_fingerprint=REVIEW_SHA)["state"],"SCOPE_BLOCKED")


class MalformedDataTests(unittest.TestCase):
    def test_malformed_path_collections_block_not_crash(self):
        for malformed in (None, "wrong", [1]):
            r=review()
            r["modified_paths"]=malformed
            out=inspect_approved_source_scope(r,{P:SHA},
                                               expected_fingerprint=REVIEW_SHA)
            self.assertEqual(out["state"],"SCOPE_BLOCKED")
            self.assertFalse(out["activation_authorized"])
