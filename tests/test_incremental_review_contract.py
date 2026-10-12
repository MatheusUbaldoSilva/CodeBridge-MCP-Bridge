"""Test that the review fingerprint binds scope and the full file inventory."""
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rag.runtime.incremental_preview_confirmation import snapshot_preview
from rag.runtime.incremental_review_contract import (
    build_review_contract, verify_review_contract)


class ReviewContractTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name) / "files"
        self.folder.mkdir()
        (self.folder / "a.md").write_text("a", encoding="utf-8")
        (self.folder / "b.cpp").write_text("b", encoding="utf-8")
        self.snapshot = snapshot_preview(
            "demo", self.folder, [{"path": "a.md"}, {"path": "b.cpp"}])
        self.contract = build_review_contract(self.snapshot, "demo", self.folder)

    def test_deterministic_and_order_independent(self):
        self.assertEqual(self.contract["files_checked"], 2)
        self.assertEqual(self.contract, verify_review_contract(
            self.snapshot, "demo", self.folder, self.contract))
        reversed_snapshot = snapshot_preview(
            "demo", self.folder, [{"path": "b.cpp"}, {"path": "a.md"}])
        self.assertEqual(self.contract,
                         build_review_contract(reversed_snapshot, "demo", self.folder))

    def test_project_folder_and_fingerprint_mismatch_refused(self):
        with self.assertRaisesRegex(ValueError, "project changed"):
            verify_review_contract(self.snapshot, "other", self.folder, self.contract)
        alternate = self.folder.parent / "other"
        alternate.mkdir()
        with self.assertRaisesRegex(ValueError, "folder changed"):
            verify_review_contract(self.snapshot, "demo", alternate, self.contract)
        tampered = dict(self.contract, review_sha256="0" * 64)
        with self.assertRaisesRegex(ValueError, "fingerprint"):
            verify_review_contract(self.snapshot, "demo", self.folder, tampered)

    def test_changed_file_refused(self):
        (self.folder / "a.md").write_text("updated", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "changed"):
            verify_review_contract(self.snapshot, "demo", self.folder, self.contract)

    def test_added_or_removed_file_changes_contract_identity(self):
        only_a = snapshot_preview("demo", self.folder, [{"path": "a.md"}])
        with self.assertRaisesRegex(ValueError, "scope"):
            verify_review_contract(only_a, "demo", self.folder, self.contract)

    def test_missing_and_extra_fields_refused(self):
        for candidate in (None, {}, {**self.contract, "unexpected": True}):
            with self.assertRaises(ValueError):
                verify_review_contract(self.snapshot, "demo", self.folder, candidate)


if __name__ == "__main__":
    unittest.main()
