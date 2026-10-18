import sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from test_incremental_bundle_e2e import create_bundle
from rag.runtime.offline_fixture_snapshot import capture_fixture
from rag.runtime.offline_fixture_restore import restore_fixture_snapshot, OfflineFixtureRestoreError
import rag.runtime.offline_fixture_restore as module

class StagingMainSQLiteLateSidecars(unittest.TestCase):
    def test_main_sqlite_sidecars_created_in_staging_after_verification_block(self):
        for suffix in ("-wal","-shm","-journal"):
            with self.subTest(suffix=suffix):
                with tempfile.TemporaryDirectory(prefix="rag-lab04-main-stage-") as tmp:
                    root=Path(tmp)/"codebridge-rag-generation-test"
                    create_bundle(root,[("lab","stage-main","synthetic")])
                    capture_fixture(root,"safe")
                    original=module.validate_incremental_bundle
                    count=[0]
                    def inject(path,*args,**kwargs):
                        result=original(path,*args,**kwargs)
                        count[0]+=1
                        if count[0]==2:
                            (Path(path)/("rag_index.sqlite3"+suffix)).write_bytes(b"synthetic")
                        return result
                    with patch.object(module,"validate_incremental_bundle",side_effect=inject):
                        with self.assertRaises(OfflineFixtureRestoreError):
                            restore_fixture_snapshot(root,"safe","denied")
                    self.assertFalse((root/"offline-fixture-restores"/"denied").exists())
                    self.assertFalse((root/"active-generation.json").exists())
if __name__=="__main__":
    unittest.main()
