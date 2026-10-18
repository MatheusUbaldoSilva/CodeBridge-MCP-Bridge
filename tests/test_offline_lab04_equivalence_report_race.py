import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from test_incremental_bundle_e2e import create_bundle
from rag.runtime.offline_fixture_snapshot import capture_fixture
from rag.runtime.offline_fixture_restore import restore_fixture_snapshot
from rag.runtime.offline_restore_equivalence import audit_restored_fixture
import rag.runtime.offline_restore_equivalence as audit

class EquivalenceReportRace(unittest.TestCase):
    def test_report_changed_during_semantic_validation_blocks_equivalence(self):
        with tempfile.TemporaryDirectory(prefix="rag-lab04-equivalence-report-") as tmp:
            root = Path(tmp) / "codebridge-rag-generation-test"
            create_bundle(root, [("lab", "metadata", "synthetic")])
            capture_fixture(root, "saved")
            restore_fixture_snapshot(root, "saved", "copy")
            report = root / "offline-fixture-backups" / "saved" / "report.json"
            original = audit.validate_incremental_bundle
            calls = [0]
            def inject(*args, **kwargs):
                result = original(*args, **kwargs)
                calls[0] += 1
                if calls[0] == 2:
                    data = json.loads(report.read_text(encoding="utf-8"))
                    data["production_authorized"] = True
                    report.write_text(json.dumps(data), encoding="utf-8")
                return result
            with patch.object(audit, "validate_incremental_bundle", side_effect=inject):
                verdict = audit_restored_fixture(root, "saved", "copy")
            self.assertEqual(calls[0], 2)
            self.assertEqual(verdict["state"], "BLOCKED")
            self.assertFalse(verdict["same_semantic_content"])
            self.assertFalse(verdict["production_authorized"])

if __name__ == "__main__":
    unittest.main()
