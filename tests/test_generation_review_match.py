"""Isolated end-to-end candidate comparison against preview approval."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from test_incremental_bundle_e2e import create_bundle
from rag.runtime.incremental_preview_confirmation import snapshot_preview
from rag.runtime.incremental_review_contract import build_review_contract
from rag.runtime.generation_review_match import (
    GenerationReviewMismatch, validate_generation_against_review)


class GenerationReviewMatchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "codebridge-rag-generation-test"
        (self.root / "generations").mkdir(parents=True)
        self.previous = [("a", "doc", "hello"), ("b", "other", "keep")]
        create_bundle(self.root / "generations" / "one", self.previous)
        create_bundle(self.root / "generations" / "two",
                      [("a", "doc", "updated"), ("b", "other", "keep")])
        self.inputs = Path(self.temp.name) / "input"
        self.inputs.mkdir()
        (self.inputs / "doc.md").write_text("updated", encoding="utf-8")
        self.snapshot = snapshot_preview(
            "a", self.inputs, [{"path": "doc.md"}])
        self.contract = build_review_contract(self.snapshot, "a", self.inputs)

    def check(self, candidate="two"):
        return validate_generation_against_review(
            self.root, "one", candidate, self.snapshot, "a",
            self.inputs, self.contract)

    def alternative(self, name, documents):
        create_bundle(self.root / "generations" / name, documents)
        return name

    def test_review_matches_candidate_and_preserved_project(self):
        result = self.check()
        self.assertEqual(result["changed_files"], 1)
        self.assertEqual(result["reviewed_files"], 1)
        self.assertIn("NOT_PUBLISHED", result["state"])

    def test_unapproved_extra_file_is_rejected(self):
        candidate = self.alternative("extra", [
            ("a", "doc", "updated"), ("a", "other", "new"),
            ("b", "other", "keep")])
        with self.assertRaisesRegex(GenerationReviewMismatch, "unreviewed"):
            self.check(candidate)

    def test_cross_project_modification_is_rejected(self):
        candidate = self.alternative("cross", [
            ("a", "doc", "updated"), ("b", "other", "changed")])
        with self.assertRaisesRegex(GenerationReviewMismatch, "other project"):
            self.check(candidate)

    def test_candidate_different_from_reviewed_hash_is_rejected(self):
        candidate = self.alternative("wrong", [
            ("a", "doc", "different"), ("b", "other", "keep")])
        with self.assertRaisesRegex(GenerationReviewMismatch, "file hashes"):
            self.check(candidate)

    def test_removal_of_old_document_is_rejected(self):
        candidate = self.alternative("removed", [("a", "doc", "updated")])
        with self.assertRaisesRegex(GenerationReviewMismatch, "removed"):
            self.check(candidate)

    def test_no_effective_change_is_rejected(self):
        candidate = self.alternative("identical", self.previous)
        with self.assertRaisesRegex(GenerationReviewMismatch, "no reviewed changes"):
            self.check(candidate)

    def test_changed_source_file_is_rejected(self):
        (self.inputs / "doc.md").write_text("modified later", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "changed"):
            self.check()


if __name__ == "__main__":
    unittest.main()
