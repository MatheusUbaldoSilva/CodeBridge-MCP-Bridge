"""End-to-end synthetic snapshot -> restore -> independent audit, across processes."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from test_incremental_bundle_e2e import create_bundle

REPO=Path(__file__).resolve().parents[1]

def execute(*args):
    return subprocess.run([sys.executable,*map(str,args)],cwd=str(REPO),
                          capture_output=True,text=True,timeout=40)

class OfflinePipelineExternalTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)/"codebridge-rag-generation-test"
        create_bundle(self.root,[("proj1","a","one"),("proj2","b","two")])
    def capture(self):
        return execute(REPO/"rag_offline_fixture_cli.py",
                       "--fixture-root",self.root,"--backup-name","first","--lab-only")
    def restore(self):
        return execute(REPO/"rag_offline_fixture_restore_cli.py",
                       "--fixture-root",self.root,"--backup-name","first",
                       "--restore-name","recovered","--lab-only")
    def audit(self):
        code=("import json,sys;"
              "from rag.runtime.offline_restore_equivalence import audit_restored_fixture;"
              "print(json.dumps(audit_restored_fixture(sys.argv[1],sys.argv[2],sys.argv[3])))")
        return execute("-c",code,self.root,"first","recovered")
    def test_full_pipeline_remains_unactivated(self):
        c=self.capture()
        self.assertEqual(c.returncode,0,c.stderr)
        self.assertFalse(json.loads(c.stdout)["production_authorized"])
        r=self.restore()
        self.assertEqual(r.returncode,0,r.stderr)
        self.assertFalse(json.loads(r.stdout)["production_authorized"])
        a=self.audit()
        self.assertEqual(a.returncode,0,a.stderr)
        report=json.loads(a.stdout)
        self.assertTrue(report["same_semantic_content"])
        self.assertFalse(report["production_authorized"])
        self.assertFalse(report["publication_authorized"])
        self.assertFalse((self.root/"active-generation.json").exists())
    def test_tampered_backup_cannot_restore(self):
        self.assertEqual(self.capture().returncode,0)
        manifest=self.root/"offline-fixture-backups"/"first"/"snapshot"/"rag-index-manifest.json"
        manifest.write_bytes(b"tampered")
        result=self.restore()
        self.assertNotEqual(result.returncode,0)
        self.assertEqual(json.loads(result.stdout)["state"],"BLOCKED")
        self.assertFalse((self.root/"offline-fixture-restores"/"recovered").exists())
if __name__=="__main__": unittest.main()
