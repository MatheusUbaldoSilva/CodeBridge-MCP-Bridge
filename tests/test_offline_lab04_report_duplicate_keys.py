import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from test_incremental_bundle_e2e import create_bundle
from rag.runtime.offline_fixture_snapshot import capture_fixture
from rag.runtime.offline_fixture_restore import restore_fixture_snapshot, OfflineFixtureRestoreError
from rag.runtime.offline_restore_equivalence import audit_restored_fixture


class DuplicateReportKeyTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="rag-lab04-duplicate-report-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "codebridge-rag-generation-test"
        create_bundle(self.root, [("lab", "duplicate-keys", "synthetic")])
        capture_fixture(self.root, "saved")
        self.report = self.root / "offline-fixture-backups" / "saved" / "report.json"

    def add_duplicate_key(self):
        original = self.report.read_text(encoding="utf-8")
        self.assertTrue(original.rstrip().endswith("}"))
        prefix, ending = original.rsplit("}", 1)
        duplicate = prefix.rstrip() + ', "production_authorized": false}' + ending
        self.assertIs(json.loads(duplicate)["production_authorized"], False)
        self.report.write_text(duplicate, encoding="utf-8")

    def test_strict_decoder_rejects_duplicate_nested_key(self):
        from rag.runtime.offline_fixture_report import decode_fixture_report
        with self.assertRaises(ValueError):
            decode_fixture_report('{ "verification": { "code": "OK", "code": "OK" } }')

    def test_strict_decoder_requires_object_root(self):
        from rag.runtime.offline_fixture_report import decode_fixture_report
        with self.assertRaises(ValueError):
            decode_fixture_report('["LAB_FIXTURE_SNAPSHOT_ONLY"]')

    def test_restore_rejects_duplicate_top_level_report_key(self):
        self.add_duplicate_key()
        with self.assertRaises(OfflineFixtureRestoreError):
            restore_fixture_snapshot(self.root, "saved", "copy")
        self.assertFalse((self.root / "offline-fixture-restores" / "copy").exists())
        self.assertFalse((self.root / "active-generation.json").exists())

    def test_independent_audit_rejects_duplicate_top_level_report_key(self):
        restore_fixture_snapshot(self.root, "saved", "copy")
        self.add_duplicate_key()
        outcome = audit_restored_fixture(self.root, "saved", "copy")
        self.assertEqual(outcome["state"], "BLOCKED")
        self.assertFalse(outcome["same_hashes"])
        self.assertFalse(outcome["production_authorized"])


if __name__ == "__main__":
    unittest.main()