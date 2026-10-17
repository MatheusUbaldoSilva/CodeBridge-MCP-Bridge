import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rag.runtime.offline_lab_coverage_report import summarize_lab_coverage

class LabCoverageTests(unittest.TestCase):
    def test_empty_evidence_is_incomplete(self):
        report = summarize_lab_coverage({}, {})
        self.assertFalse(report["copy_authorized"])
        self.assertFalse(report["all_handles_closed"])
        self.assertIn("CATALOG_NOT_VERIFIED", report["issues"])

    def test_known_released_handle_never_proves_global_release(self):
        report = summarize_lab_coverage(
            {"files": ["rag_index.sqlite3", "qdrant/segment"]},
            {"state": "LAB_HANDLES_READABLE_UNPROVEN"},
            observed_handles=("fixture-h1",), released_handles=("fixture-h1",))
        self.assertEqual(report["verified_file_paths"], ["qdrant/segment", "rag_index.sqlite3"])
        self.assertEqual(report["unreleased_handles"], [])
        self.assertTrue(report["unobservable_groups"])
        self.assertFalse(report["all_handles_closed"])
        self.assertFalse(report["production_quiescence_proven"])

    def test_unreleased_and_unknown_are_explicit(self):
        report = summarize_lab_coverage(
            {"files": ["rag-index-manifest.json"]},
            {"state": "BLOCKED"},
            observed_handles=("one", "two"), released_handles=("one",),
            unknown=("mmap-worker",))
        self.assertEqual(report["unreleased_handles"], ["two"])
        self.assertEqual(report["unknown_objects"], ["mmap-worker"])
        self.assertIn("UNKNOWN_OBJECTS_PRESENT", report["issues"])
        self.assertIn("HANDLE_PROBE_NOT_CLEAR", report["issues"])
        self.assertFalse(report["copy_authorized"])

if __name__ == "__main__":
    unittest.main()
