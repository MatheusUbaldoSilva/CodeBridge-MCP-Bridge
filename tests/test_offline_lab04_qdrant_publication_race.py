import sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from test_incremental_bundle_e2e import create_bundle
from rag.runtime.offline_fixture_snapshot import capture_fixture, OfflineFixtureError
import rag.runtime.offline_fixture_snapshot as snapshot

class QdrantPublicationRace(unittest.TestCase):
    def test_qdrant_wal_created_at_report_write_blocks_publication(self):
        with tempfile.TemporaryDirectory(prefix="rag-lab04-publish-") as temp:
            root=Path(temp)/"codebridge-rag-generation-test"
            create_bundle(root,[("lab","publish","synthetic")])
            storage=next((root/"qdrant").rglob("storage.sqlite"))
            wal=Path(str(storage)+"-wal")
            real=Path.write_text
            def inject(path,data,*args,**kwargs):
                if Path(path).name=="report.json":
                    wal.write_bytes(b"late synthetic WAL")
                return real(path,data,*args,**kwargs)
            with patch.object(Path,"write_text",autospec=True,side_effect=inject):
                with self.assertRaises(OfflineFixtureError):
                    capture_fixture(root,"blocked")
            self.assertFalse((root/"offline-fixture-backups"/"blocked").exists())
            self.assertEqual(list((root/"offline-fixture-backups").glob(".fixture-*")),[])

if __name__=="__main__":
    unittest.main()
