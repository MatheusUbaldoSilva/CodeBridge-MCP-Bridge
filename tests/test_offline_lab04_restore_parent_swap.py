import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from test_incremental_bundle_e2e import create_bundle
from rag.runtime.offline_fixture_snapshot import capture_fixture
from rag.runtime.offline_fixture_restore import restore_fixture_snapshot, OfflineFixtureRestoreError
import rag.runtime.offline_fixture_restore as restore


@unittest.skipUnless(sys.platform == "win32", "Windows directory reparse lab")
class RestoreParentSwapTests(unittest.TestCase):
    def test_replaced_restores_parent_never_publishes_outside_fixture(self):
        with tempfile.TemporaryDirectory(prefix="rag-lab04-restore-parent-") as tmp:
            root = Path(tmp) / "codebridge-rag-generation-test"
            create_bundle(root, [("lab", "parent-swap", "synthetic")])
            capture_fixture(root, "saved")
            parent = root / "offline-fixture-restores"
            outside = Path(tmp) / "escaped-restores"
            validate = restore.validate_incremental_bundle
            calls = [0]

            def inject(*args, **kwargs):
                result = validate(*args, **kwargs)
                calls[0] += 1
                if calls[0] == 2:
                    parent.rename(outside)
                    os.symlink(outside, parent, target_is_directory=True)
                return result

            with patch.object(restore, "validate_incremental_bundle", side_effect=inject):
                with self.assertRaises(OfflineFixtureRestoreError):
                    restore_fixture_snapshot(root, "saved", "escaped")
            self.assertEqual(calls[0], 2)
            self.assertTrue(parent.is_symlink())
            self.assertFalse((outside / "escaped").exists())
            self.assertEqual(len(list(outside.glob(".restore-fixture-*"))), 1)
            self.assertFalse((root / "active-generation.json").exists())


if __name__ == "__main__":
    unittest.main()