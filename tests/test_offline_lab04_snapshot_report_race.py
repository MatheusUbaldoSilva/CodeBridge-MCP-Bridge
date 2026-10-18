"""Reject report tampering after synthetic snapshot report write."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from test_incremental_bundle_e2e import create_bundle
from rag.runtime.offline_fixture_snapshot import capture_fixture, OfflineFixtureError

class SnapshotReportAfterWriteRace(unittest.TestCase):
    def test_report_changed_after_write_is_not_published(self):
        with tempfile.TemporaryDirectory(prefix="rag-lab04-report-publish-") as temp:
            root=Path(temp)/"codebridge-rag-generation-test"
            create_bundle(root,[("lab","report-check","synthetic")])
            real=Path.write_text
            injected=[False]
            def tamper(path,text,*args,**kwargs):
                result=real(path,text,*args,**kwargs)
                if Path(path).name=="report.json":
                    data=json.loads(Path(path).read_text(encoding="utf-8"))
                    data["production_authorized"]=True
                    Path(path).write_bytes(json.dumps(data).encode("utf-8"))
                    injected[0]=True
                return result
            with patch.object(Path,"write_text",autospec=True,side_effect=tamper):
                with self.assertRaises(OfflineFixtureError):
                    capture_fixture(root,"unsafe")
            self.assertTrue(injected[0])
            self.assertFalse((root/"offline-fixture-backups"/"unsafe").exists())
            self.assertEqual(list((root/"offline-fixture-backups").glob(".fixture-*")),[])
if __name__=="__main__":
    unittest.main()
