"""Final content integrity at synthetic snapshot publication."""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from test_incremental_bundle_e2e import create_bundle
from rag.runtime.offline_fixture_snapshot import capture_fixture, OfflineFixtureError

class SnapshotFinalContentIntegrity(unittest.TestCase):
    def test_source_qdrant_mutation_during_report_write_blocks_publish(self):
        self._run_mutation("source")
    def test_staging_qdrant_mutation_during_report_write_blocks_publish(self):
        self._run_mutation("staging")

    def _run_mutation(self, location):
        with tempfile.TemporaryDirectory(prefix="rag-lab04-snapshot-final-") as tmp:
            root=Path(tmp)/"codebridge-rag-generation-test"
            create_bundle(root,[("lab","mutation","synthetic")])
            original=Path.write_text
            touched=[False]
            def mutate(path,data,*args,**kwargs):
                if Path(path).name=="report.json":
                    if location=="source":
                        target=root/"qdrant"/"late-added-file.bin"
                        target.write_bytes(b"new-after-hash")
                    else:
                        target=Path(path).parent/"snapshot"/"qdrant"/"meta.json"
                        target.write_bytes(target.read_bytes()+b"late-mutation")
                    touched[0]=True
                return original(path,data,*args,**kwargs)
            with patch.object(Path,"write_text",autospec=True,side_effect=mutate):
                with self.assertRaises(OfflineFixtureError):
                    capture_fixture(root,"unsafe")
            self.assertTrue(touched[0])
            self.assertFalse((root/"offline-fixture-backups"/"unsafe").exists())
            self.assertEqual(list((root/"offline-fixture-backups").glob(".fixture-*")),[])

if __name__=="__main__":
    unittest.main()
