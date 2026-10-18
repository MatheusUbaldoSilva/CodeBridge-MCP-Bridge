import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from test_incremental_bundle_e2e import create_bundle
from rag.runtime.offline_fixture_snapshot import capture_fixture, OfflineFixtureError
import rag.runtime.offline_fixture_snapshot as snapshot


@unittest.skipUnless(sys.platform == "win32", "Windows directory reparse lab")
class SnapshotParentSwapTests(unittest.TestCase):
    def test_replaced_backups_parent_never_publishes_outside_fixture(self):
        with tempfile.TemporaryDirectory(prefix="rag-lab04-snapshot-parent-") as tmp:
            root = Path(tmp) / "codebridge-rag-generation-test"
            create_bundle(root, [("lab", "snapshot-parent", "synthetic")])
            backups = root / "offline-fixture-backups"
            outside = Path(tmp) / "escaped-backups"
            validate = snapshot.validate_incremental_bundle
            calls = [0]

            def inject(*args, **kwargs):
                result = validate(*args, **kwargs)
                calls[0] += 1
                if calls[0] == 1:
                    backups.rename(outside)
                    os.symlink(outside, backups, target_is_directory=True)
                return result

            with patch.object(snapshot, "validate_incremental_bundle", side_effect=inject):
                with self.assertRaises(OfflineFixtureError):
                    capture_fixture(root, "escaped")
            self.assertEqual(calls[0], 1)
            self.assertTrue(backups.is_symlink())
            self.assertFalse((outside / "escaped").exists())
            self.assertEqual(len(list(outside.glob(".fixture-*"))), 1)
            self.assertFalse((root / "active-generation.json").exists())


if __name__ == "__main__":
    unittest.main()