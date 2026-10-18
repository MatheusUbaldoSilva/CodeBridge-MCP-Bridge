import sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from test_incremental_bundle_e2e import create_bundle
from rag.runtime.offline_fixture_snapshot import capture_fixture
from rag.runtime.offline_fixture_restore import restore_fixture_snapshot,OfflineFixtureRestoreError
import rag.runtime.offline_fixture_restore as module

class RestoreSourceMutationAfterCopy(unittest.TestCase):
    def test_source_artifact_changes_after_copy_validation_blocks_publish(self):
        with tempfile.TemporaryDirectory(prefix="rag-lab04-source-mutation-") as tmp:
            root=Path(tmp)/"codebridge-rag-generation-test"
            create_bundle(root,[("lab","source-mutating","synthetic")])
            capture_fixture(root,"safe")
            source=root/"offline-fixture-backups"/"safe"/"snapshot"/"qdrant"/"meta.json"
            original=module.validate_incremental_bundle
            calls=[0]
            def inject(*args,**kwargs):
                result=original(*args,**kwargs)
                calls[0]+=1
                if calls[0]==2:
                    source.write_bytes(source.read_bytes()+b"tamper")
                return result
            with patch.object(module,"validate_incremental_bundle",side_effect=inject):
                with self.assertRaises(OfflineFixtureRestoreError):
                    restore_fixture_snapshot(root,"safe","blocked")
            self.assertFalse((root/"offline-fixture-restores"/"blocked").exists())
            self.assertFalse((root/"active-generation.json").exists())
if __name__=="__main__":
    unittest.main()
