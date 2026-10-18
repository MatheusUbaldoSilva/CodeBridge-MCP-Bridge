import os
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


@unittest.skipUnless(sys.platform == "win32", "Windows reparse test")
class EquivalenceSavedParentSwap(unittest.TestCase):
    def test_independent_audit_blocks_saved_parent_reparse_swap(self):
        with tempfile.TemporaryDirectory(prefix="rag-lab04-audit-parent-") as tmp:
            root = Path(tmp) / "codebridge-rag-generation-test"
            create_bundle(root, [("lab", "audit-parent", "synthetic")])
            capture_fixture(root, "saved")
            restore_fixture_snapshot(root, "saved", "copy")
            saved = root / "offline-fixture-backups" / "saved"
            outside = Path(tmp) / "outside-saved"
            validate = audit.validate_incremental_bundle
            calls = [0]

            def swap(*args, **kwargs):
                result = validate(*args, **kwargs)
                calls[0] += 1
                if calls[0] == 2:
                    saved.rename(outside)
                    os.symlink(outside, saved, target_is_directory=True)
                return result

            with patch.object(audit, "validate_incremental_bundle", side_effect=swap):
                verdict = audit_restored_fixture(root, "saved", "copy")
            self.assertEqual(calls[0], 2)
            self.assertTrue(saved.is_symlink())
            self.assertEqual(verdict["state"], "BLOCKED")
            self.assertFalse(verdict["same_hashes"])
            self.assertFalse(verdict["production_authorized"])
            self.assertFalse((root / "active-generation.json").exists())


if __name__ == "__main__":
    unittest.main()