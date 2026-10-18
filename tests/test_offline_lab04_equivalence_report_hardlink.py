import os,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from test_incremental_bundle_e2e import create_bundle
from rag.runtime.offline_fixture_snapshot import capture_fixture
from rag.runtime.offline_fixture_restore import restore_fixture_snapshot
from rag.runtime.offline_restore_equivalence import audit_restored_fixture
import rag.runtime.offline_restore_equivalence as audit

@unittest.skipUnless(sys.platform=="win32","Windows hardlink lab fixture")
class EquivalenceReportLinkRace(unittest.TestCase):
    def test_external_equal_report_link_blocks_equivalence(self):
        with tempfile.TemporaryDirectory(prefix="rag-lab04-audit-report-link-") as tmp:
            root=Path(tmp)/"codebridge-rag-generation-test"
            create_bundle(root,[("lab","auditlink","synthetic")])
            capture_fixture(root,"saved")
            restore_fixture_snapshot(root,"saved","copy")
            report=root/"offline-fixture-backups"/"saved"/"report.json"
            outside=Path(tmp)/"external-report.json"
            original=audit.validate_incremental_bundle
            calls=[0]
            def inject(*args,**kwargs):
                result=original(*args,**kwargs)
                calls[0]+=1
                if calls[0]==2:
                    outside.write_bytes(report.read_bytes())
                    report.unlink()
                    os.link(outside,report)
                return result
            with patch.object(audit,"validate_incremental_bundle",side_effect=inject):
                verdict=audit_restored_fixture(root,"saved","copy")
            self.assertEqual(calls[0],2)
            self.assertEqual(verdict["state"],"BLOCKED")
            self.assertFalse(verdict["same_hashes"])
            self.assertFalse(verdict["production_authorized"])
if __name__=="__main__":
    unittest.main()
