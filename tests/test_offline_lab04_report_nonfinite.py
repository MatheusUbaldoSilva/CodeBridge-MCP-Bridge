import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from test_incremental_bundle_e2e import create_bundle
from rag.runtime.offline_fixture_snapshot import capture_fixture
from rag.runtime.offline_fixture_restore import restore_fixture_snapshot, OfflineFixtureRestoreError
from rag.runtime.offline_restore_equivalence import audit_restored_fixture
from rag.runtime.offline_fixture_report import decode_fixture_report


class NonfiniteReportKeyTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="rag-lab04-nonfinite-report-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "codebridge-rag-generation-test"
        create_bundle(self.root, [("lab", "nonfinite-json", "synthetic")])
        capture_fixture(self.root, "saved")
        self.report = self.root / "offline-fixture-backups" / "saved" / "report.json"

    def append_invalid_number(self):
        original = self.report.read_text(encoding="utf-8")
        prefix, suffix = original.rsplit("}", 1)
        mutated = prefix.rstrip() + ', "untrusted_metric": NaN}' + suffix
        self.report.write_text(mutated, encoding="utf-8")

    def test_strict_decoder_disallows_all_nonfinite_json_numbers(self):
        for token in ("NaN", "Infinity", "-Infinity"):
            with self.subTest(token=token), self.assertRaises(ValueError):
                decode_fixture_report('{"untrusted_metric": ' + token + '}')

    def test_restore_rejects_nonstandard_nan_report(self):
        self.append_invalid_number()
        with self.assertRaises(OfflineFixtureRestoreError):
            restore_fixture_snapshot(self.root, "saved", "copy")
        self.assertFalse((self.root / "offline-fixture-restores" / "copy").exists())

    def test_independent_audit_rejects_nonstandard_nan_report(self):
        restore_fixture_snapshot(self.root, "saved", "copy")
        self.append_invalid_number()
        report = audit_restored_fixture(self.root, "saved", "copy")
        self.assertEqual(report["state"], "BLOCKED")
        self.assertFalse(report["same_hashes"])
        self.assertFalse(report["production_authorized"])


if __name__ == "__main__":
    unittest.main()