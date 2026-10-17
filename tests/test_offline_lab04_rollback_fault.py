import hashlib
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from test_incremental_bundle_e2e import create_bundle
from rag.runtime.offline_fixture_snapshot import capture_fixture
from rag.runtime.offline_fixture_restore import restore_fixture_snapshot
import rag.runtime.offline_fixture_restore as restore_module

class Lab04RollbackFaultTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix="rag-lab04-d-")
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)/"codebridge-rag-generation-test"
        create_bundle(self.root,[("lab","rollback","synthetic")])
        self.pointer=self.root/"active-generation.json"
        self.pointer.write_text('{"generation":"stable"}',encoding="utf-8")
        capture_fixture(self.root,"known_good")
        restore_fixture_snapshot(self.root,"known_good","prior")

    def test_copy_failure_cleans_staging_but_preserves_prior_restore(self):
        restore_parent=self.root/"offline-fixture-restores"
        prior=restore_parent/"prior"/"snapshot"/"rag_index.sqlite3"
        before=hashlib.sha256(prior.read_bytes()).hexdigest()
        pointer_hash=hashlib.sha256(self.pointer.read_bytes()).hexdigest()
        original=restore_module.shutil.copytree
        def interrupted(src,dst,*args,**kwargs):
            output=original(src,dst,*args,**kwargs)
            raise OSError("synthetic interruption after copy")
        with patch.object(restore_module.shutil,"copytree",side_effect=interrupted):
            with self.assertRaises(OSError):
                restore_fixture_snapshot(self.root,"known_good","failed")
        self.assertFalse((restore_parent/"failed").exists())
        self.assertEqual(list(restore_parent.glob(".restore-fixture-*")),[])
        self.assertEqual(hashlib.sha256(prior.read_bytes()).hexdigest(),before)
        self.assertEqual(hashlib.sha256(self.pointer.read_bytes()).hexdigest(),pointer_hash)
        restored=restore_fixture_snapshot(self.root,"known_good","retry")
        self.assertEqual(restored["state"],"LAB_FIXTURE_RESTORED_NOT_ACTIVATED")
        self.assertFalse(restored["production_authorized"])

if __name__=="__main__":
    unittest.main()
