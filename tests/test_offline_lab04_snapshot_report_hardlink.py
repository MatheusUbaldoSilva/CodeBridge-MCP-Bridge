"""Reject a synthetic snapshot report replaced by an external hardlink."""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from test_incremental_bundle_e2e import create_bundle
from rag.runtime.offline_fixture_snapshot import capture_fixture, OfflineFixtureError

@unittest.skipUnless(sys.platform=="win32","Hardlink fixture test for Windows filesystem")
class SnapshotReportHardlinkBoundary(unittest.TestCase):
    def test_equal_text_hardlinked_report_is_not_published(self):
        with tempfile.TemporaryDirectory(prefix="rag-lab04-report-link-") as tmp:
            root=Path(tmp)/"codebridge-rag-generation-test"
            create_bundle(root,[("lab","hardlink","synthetic")])
            outside=Path(tmp)/"external-report.json"
            real=Path.write_text
            linked=[False]
            def replace(path,text,*args,**kwargs):
                n=real(path,text,*args,**kwargs)
                if Path(path).name=="report.json":
                    outside.write_bytes(Path(path).read_bytes())
                    Path(path).unlink()
                    os.link(outside,path)
                    linked[0]=True
                return n
            with patch.object(Path,"write_text",autospec=True,side_effect=replace):
                with self.assertRaises(OfflineFixtureError):
                    capture_fixture(root,"rejected")
            self.assertTrue(linked[0])
            self.assertTrue(outside.is_file())
            self.assertFalse((root/"offline-fixture-backups"/"rejected").exists())
            self.assertEqual(list((root/"offline-fixture-backups").glob(".fixture-*")),[])
if __name__=="__main__":
    unittest.main()
