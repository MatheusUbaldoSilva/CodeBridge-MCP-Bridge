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


class ChangedActiveGenerationReportTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="rag-lab04-report-flag-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "codebridge-rag-generation-test"
        create_bundle(self.root, [("lab", "generation-flag", "synthetic")])
        capture_fixture(self.root, "saved")
        self.report = self.root / "offline-fixture-backups" / "saved" / "report.json"

    def change_flag(self):
        report = json.loads(self.report.read_text(encoding="utf-8"))
        self.assertIs(report["active_generation_changed"], False)
        report["active_generation_changed"] = True
        self.report.write_text(json.dumps(report), encoding="utf-8")

    def test_restore_blocks_claim_that_active_generation_was_changed(self):
        self.change_flag()
        with self.assertRaises(OfflineFixtureRestoreError):
            restore_fixture_snapshot(self.root, "saved", "rejected")
        self.assertFalse((self.root / "offline-fixture-restores" / "rejected").exists())
        self.assertFalse((self.root / "active-generation.json").exists())

    def test_independent_audit_blocks_claim_of_active_generation_change(self):
        restore_fixture_snapshot(self.root, "saved", "restored")
        self.change_flag()
        result = audit_restored_fixture(self.root, "saved", "restored")
        self.assertEqual(result["state"], "BLOCKED")
        self.assertFalse(result["same_hashes"])
        self.assertFalse(result["production_authorized"])


if __name__ == "__main__":
    unittest.main()