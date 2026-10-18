import sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from test_incremental_bundle_e2e import create_bundle
from rag.runtime.offline_fixture_snapshot import capture_fixture,OfflineFixtureError

class LateMainSQLitePublicationMatrix(unittest.TestCase):
    def test_each_late_sidecar_blocks_publication(self):
        for suffix in ("-wal","-shm","-journal"):
            with self.subTest(suffix=suffix):
                with tempfile.TemporaryDirectory(prefix="rag-lab04-main-publish-") as tmp:
                    root=Path(tmp)/"codebridge-rag-generation-test"
                    create_bundle(root,[("lab","late","synthetic")])
                    injected=root/("rag_index.sqlite3"+suffix)
                    original=Path.write_text
                    def inject(path,data,*args,**kwargs):
                        if Path(path).name=="report.json":
                            injected.write_bytes(b"synthetic pending sidecar")
                        return original(path,data,*args,**kwargs)
                    with patch.object(Path,"write_text",autospec=True,side_effect=inject):
                        with self.assertRaises(OfflineFixtureError):
                            capture_fixture(root,"rejected")
                    self.assertFalse((root/"offline-fixture-backups"/"rejected").exists())
                    self.assertEqual(list((root/"offline-fixture-backups").glob(".fixture-*")),[])
if __name__=="__main__":
    unittest.main()
