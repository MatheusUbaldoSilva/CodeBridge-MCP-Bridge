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


@unittest.skipUnless(sys.platform == "win32", "Windows reparse lab")
class RestoreSourceParentSwap(unittest.TestCase):
    def test_restore_rejects_saved_source_reparse_before_publication(self):
        with tempfile.TemporaryDirectory(prefix="rag-lab04-restore-source-parent-") as tmp:
            root = Path(tmp) / "codebridge-rag-generation-test"
            create_bundle(root, [("lab", "source-parent", "synthetic")])
            capture_fixture(root, "saved")
            saved = root / "offline-fixture-backups" / "saved"
            outside = Path(tmp) / "redirected-source"
            validate = restore.validate_incremental_bundle
            calls = [0]

            def swap(*args, **kwargs):
                result = validate(*args, **kwargs)
                calls[0] += 1
                if calls[0] == 2:
                    saved.rename(outside)
                    os.symlink(outside, saved, target_is_directory=True)
                return result

            with patch.object(restore, "validate_incremental_bundle", side_effect=swap):
                with self.assertRaises(OfflineFixtureRestoreError):
                    restore_fixture_snapshot(root, "saved", "blocked")
            self.assertEqual(calls[0], 2)
            self.assertTrue(saved.is_symlink())
            self.assertFalse((root / "offline-fixture-restores" / "blocked").exists())
            self.assertFalse((root / "active-generation.json").exists())


if __name__ == "__main__":
    unittest.main()