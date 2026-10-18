"""Reject a restore source report replaced by external hardlink after validation."""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from test_incremental_bundle_e2e import create_bundle
from rag.runtime.offline_fixture_snapshot import capture_fixture
from rag.runtime.offline_fixture_restore import restore_fixture_snapshot, OfflineFixtureRestoreError
import rag.runtime.offline_fixture_restore as restore

@unittest.skipUnless(sys.platform=="win32","Windows hardlink fixture check")
class RestoreReportHardlinkAfterValidation(unittest.TestCase):
    def test_equal_content_external_hardlink_blocks_publication(self):
        with tempfile.TemporaryDirectory(prefix="rag-lab04-restore-report-link-") as temp:
            root=Path(temp)/"codebridge-rag-generation-test"
            create_bundle(root,[("lab","report-hardlink","synthetic")])
            capture_fixture(root,"saved")
            report=root/"offline-fixture-backups"/"saved"/"report.json"
            external=Path(temp)/"external-report.json"
            original=restore.validate_incremental_bundle
            calls=[0]
            def inject(*args,**kwargs):
                output=original(*args,**kwargs)
                calls[0]+=1
                if calls[0]==2:
                    external.write_bytes(report.read_bytes())
                    report.unlink()
                    os.link(external,report)
                return output
            with patch.object(restore,"validate_incremental_bundle",side_effect=inject):
                with self.assertRaises(OfflineFixtureRestoreError):
                    restore_fixture_snapshot(root,"saved","blocked")
            self.assertEqual(calls[0],2)
            self.assertTrue(external.is_file())
            self.assertFalse((root/"offline-fixture-restores"/"blocked").exists())
            self.assertEqual(list((root/"offline-fixture-restores").glob(".restore-fixture-*")),[])
            self.assertFalse((root/"active-generation.json").exists())

if __name__=="__main__":
    unittest.main()
