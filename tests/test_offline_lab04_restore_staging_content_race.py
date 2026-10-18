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

class RestoreStagingContentRace(unittest.TestCase):
    def test_staging_artifact_changes_after_validation_block_publication(self):
        with tempfile.TemporaryDirectory(prefix="rag-lab04-staging-content-") as tmp:
            root = Path(tmp) / "codebridge-rag-generation-test"
            create_bundle(root, [("lab", "staging-mutating", "synthetic")])
            capture_fixture(root, "safe")
            original = restore.validate_incremental_bundle
            calls = [0]
            def inject(path, *args, **kwargs):
                result = original(path, *args, **kwargs)
                calls[0] += 1
                if calls[0] == 2:
                    target = Path(path) / "qdrant" / "meta.json"
                    target.write_bytes(target.read_bytes() + b"late-content-tamper")
                return result
            with patch.object(restore, "validate_incremental_bundle", side_effect=inject):
                with self.assertRaises(OfflineFixtureRestoreError):
                    restore_fixture_snapshot(root, "safe", "rejected")
            self.assertEqual(calls[0], 2)
            self.assertFalse((root / "offline-fixture-restores" / "rejected").exists())
            self.assertEqual(list((root / "offline-fixture-restores").glob(".restore-fixture-*")), [])
            self.assertFalse((root / "active-generation.json").exists())
if __name__ == "__main__":
    unittest.main()
