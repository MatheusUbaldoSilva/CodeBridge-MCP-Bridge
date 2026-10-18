import sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from test_incremental_bundle_e2e import create_bundle
from rag.runtime.offline_fixture_snapshot import capture_fixture
from rag.runtime.offline_fixture_restore import restore_fixture_snapshot, OfflineFixtureRestoreError
import rag.runtime.offline_fixture_restore as restore

class LateSidecarAtRestorePublication(unittest.TestCase):
    def test_internal_qdrant_wal_created_at_final_rename_blocks(self):
        with tempfile.TemporaryDirectory(prefix="rag-lab04-restore-race-") as tmp:
            root=Path(tmp)/"codebridge-rag-generation-test"
            create_bundle(root,[("lab","race","synthetic")])
            capture_fixture(root,"saved")
            payload=root/"offline-fixture-backups"/"saved"/"snapshot"
            sqlite_file=next((payload/"qdrant").rglob("storage.sqlite"))
            wal=Path(str(sqlite_file)+"-wal")
            real=restore.validate_incremental_bundle
            calls=[0]
            def inject(*args,**kwargs):
                result=real(*args,**kwargs)
                calls[0]+=1
                if calls[0]==2:
                    wal.write_bytes(b"synthetic late WAL")
                return result
            with patch.object(restore,"validate_incremental_bundle",side_effect=inject):
                with self.assertRaises(OfflineFixtureRestoreError):
                    restore_fixture_snapshot(root,"saved","denied")
            self.assertFalse((root/"offline-fixture-restores"/"denied").exists())
            self.assertFalse((root/"active-generation.json").exists())
if __name__=="__main__":
    unittest.main()
