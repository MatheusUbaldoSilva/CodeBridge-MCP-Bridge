import unittest

from rag.runtime.production_incremental_candidate_review import inspect_incremental_candidate_review


class IncrementalCandidateReviewTests(unittest.TestCase):
    def setUp(self):
        self.path = "rag/runtime/incremental_scheduler_gate.py"
        self.digest = "6" * 64
        self.review = {
            "state": "CONTENT_COMPARISON_ONLY_NOT_APPROVED",
            "evidence_sha256_not_signature": "a" * 64,
            "added_paths": [self.path], "modified_paths": [],
            "removed_paths": [], "unchanged_count": 210,
            "base_entries": 210, "candidate_entries": 211,
            "details": [{"path": self.path, "action": "ADDED",
                         "candidate_sha256": self.digest}],
        }

    def run_review(self, **overrides):
        args = dict(
            review=self.review, approved_sha256={self.path: self.digest},
            expected_fingerprint="a" * 64,
            baseline_generation="legacy-210", candidate_generation="candidate-merged-211",
        )
        args.update(overrides)
        return inspect_incremental_candidate_review(**args)

    def test_closed_generation_integration_uses_real_review(self):
        from unittest.mock import patch
        from rag.runtime.production_incremental_candidate_review import review_closed_incremental_generations
        report = dict(self.review, baseline="v1_base_test", candidate="v1_delta_test")
        with patch(
            "rag.runtime.production_content_review.summarize_versioned_source_review",
            return_value=report,
        ) as reviewer:
            result = review_closed_incremental_generations(
                "C:/ignored/generations/v1_base_test",
                "C:/ignored/generations/v1_delta_test",
                {self.path: self.digest}, expected_fingerprint="a" * 64,
            )
        reviewer.assert_called_once()
        self.assertEqual(result["state"], "CANDIDATE_SCOPE_VERIFIED_NOT_AUTHORIZED")
        self.assertEqual(result["candidate_generation"], "v1_delta_test")
        self.assertFalse(result["safe_to_publish"])

    def test_closed_generation_integration_propagates_invalid_store(self):
        from unittest.mock import patch
        from rag.runtime.production_incremental_candidate_review import review_closed_incremental_generations
        with patch(
            "rag.runtime.production_content_review.summarize_versioned_source_review",
            side_effect=ValueError("invalid generation"),
        ):
            with self.assertRaisesRegex(ValueError, "invalid generation"):
                review_closed_incremental_generations(
                    "invalid-base", "invalid-candidate",
                    {self.path: self.digest}, expected_fingerprint="a" * 64,
                )
    def test_offline_counts_read_only(self):
        import sqlite3
        import tempfile
        from pathlib import Path
        from rag.runtime.production_incremental_candidate_review import inspect_offline_candidate_counts
        with tempfile.TemporaryDirectory() as temp:
            base, candidate = Path(temp) / "baseline", Path(temp) / "candidate"
            for folder, docs, chunks in ((base, 210, 8761), (candidate, 211, 8763)):
                folder.mkdir()
                db = sqlite3.connect(folder / "rag_index.sqlite3")
                db.execute("CREATE TABLE rag_index_state (project_id TEXT, document_count INT, chunk_count INT, state TEXT)")
                db.execute("INSERT INTO rag_index_state VALUES ('codebridge',?,?, 'READY')", (docs, chunks))
                db.commit()
                db.close()
            good = inspect_offline_candidate_counts(base, candidate)
            self.assertEqual(good["state"], "COUNTS_MATCH_NOT_AUTHORIZED")
            self.assertFalse(good["safe_to_publish"])
            db = sqlite3.connect(candidate / "rag_index.sqlite3")
            db.execute("UPDATE rag_index_state SET chunk_count=8766")
            db.commit()
            db.close()
            self.assertEqual(inspect_offline_candidate_counts(base, candidate)["state"], "BLOCKED")
    def test_real_offline_candidate_scope_passes_read_only(self):
        import os
        from pathlib import Path
        from rag.runtime.production_incremental_candidate_review import inspect_offline_candidate_sources
        root = Path(os.environ["TEMP"]) / "codebridge-rag-p2-closed-baseline"
        if not (root / "legacy" / "rag_index.sqlite3").exists():
            self.skipTest("Real closed bundle not present on this machine")
        result = inspect_offline_candidate_sources(
            root / "legacy", root / "candidate-merged-211",
            "6d0e790e82ee9bea7f163cf0b5244accc794a87bf6032d97144f73ab21c3feed",
        )
        self.assertEqual(result["state"], "OFFLINE_SOURCE_SCOPE_MATCH_NOT_AUTHORIZED")
        self.assertFalse(result["activation_authorized"])
        self.assertFalse(result["safe_to_publish"])

    def test_real_offline_candidate_wrong_sha_blocks(self):
        import os
        from pathlib import Path
        from rag.runtime.production_incremental_candidate_review import inspect_offline_candidate_sources
        root = Path(os.environ["TEMP"]) / "codebridge-rag-p2-closed-baseline"
        if not (root / "legacy" / "rag_index.sqlite3").exists():
            self.skipTest("Real closed bundle not present on this machine")
        result = inspect_offline_candidate_sources(
            root / "legacy", root / "candidate-merged-211", "f" * 64,
        )
        self.assertEqual(result["state"], "BLOCKED")
        self.assertIn("INCREMENTAL_SOURCE_SHA_MISMATCH", result["issues"])
    def test_exact_scope_is_still_not_authorization(self):
        result = self.run_review()
        self.assertEqual(result["state"], "CANDIDATE_SCOPE_VERIFIED_NOT_AUTHORIZED")
        self.assertFalse(result["safe_to_publish"])
        self.assertFalse(result["activation_authorized"])

    def test_different_sha_blocks(self):
        result = self.run_review(approved_sha256={self.path: "f" * 64})
        self.assertEqual(result["state"], "BLOCKED")

    def test_other_added_file_blocks(self):
        self.review["added_paths"] = ["another.py"]
        self.assertEqual(self.run_review()["state"], "BLOCKED")

    def test_changed_baseline_blocks(self):
        self.review["unchanged_count"] = 209
        self.assertEqual(self.run_review()["state"], "BLOCKED")

    def test_wrong_candidate_document_count_blocks(self):
        self.review["candidate_entries"] = 212
        self.assertEqual(self.run_review()["state"], "BLOCKED")

    def test_missing_document_counts_blocks(self):
        del self.review["candidate_entries"]
        self.assertEqual(self.run_review()["state"], "BLOCKED")
    def test_equal_generation_blocks(self):
        result = self.run_review(candidate_generation="legacy-210")
        self.assertEqual(result["state"], "BLOCKED")

    def test_missing_fingerprint_blocks(self):
        self.assertEqual(self.run_review(expected_fingerprint="b" * 64)["state"], "BLOCKED")


if __name__ == "__main__":
    unittest.main()
