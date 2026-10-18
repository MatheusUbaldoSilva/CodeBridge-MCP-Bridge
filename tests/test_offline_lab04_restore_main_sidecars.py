import sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from test_incremental_bundle_e2e import create_bundle
from rag.runtime.offline_fixture_snapshot import capture_fixture
from rag.runtime.offline_fixture_restore import restore_fixture_snapshot,OfflineFixtureRestoreError
import rag.runtime.offline_fixture_restore as module

class LateMainSQLiteRestoreMatrix(unittest.TestCase):
    def test_each_main_sqlite_sidecar_added_during_validation_blocks(self):
        for suffix in ("-wal","-shm","-journal"):
            with self.subTest(suffix=suffix):
                with tempfile.TemporaryDirectory(prefix="rag-lab04-restore-main-") as tmp:
                    root=Path(tmp)/"codebridge-rag-generation-test"
                    create_bundle(root,[("lab","late","synthetic")])
                    capture_fixture(root,"saved")
                    payload=root/"offline-fixture-backups"/"saved"/"snapshot"
                    sidecar=payload/("rag_index.sqlite3"+suffix)
                    original=module.validate_incremental_bundle
                    calls=[0]
                    def inject(*args,**kwargs):
                        result=original(*args,**kwargs)
                        calls[0]+=1
                        if calls[0]==2:
                            sidecar.write_bytes(b"late synthetic sidecar")
                        return result
                    with patch.object(module,"validate_incremental_bundle",side_effect=inject):
                        with self.assertRaises(OfflineFixtureRestoreError):
                            restore_fixture_snapshot(root,"saved","denied")
                    self.assertFalse((root/"offline-fixture-restores"/"denied").exists())
                    self.assertFalse((root/"active-generation.json").exists())
if __name__=="__main__":
    unittest.main()
