import sys,tempfile,unittest,subprocess,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from test_incremental_bundle_e2e import create_bundle
from rag.runtime.offline_store_handle_probe import inspect_fixture_handles

class MmapLimitTests(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup)
        self.root=Path(t.name)/"codebridge-rag-generation-test"
        create_bundle(self.root,[("lab","note","mmap synthetic")])
    def test_read_only_mmap_survives_descriptor_close_but_never_authorizes(self):
        target=self.root/"rag-index-manifest.json"
        child=("import sys,mmap,time;"
               "f=open(sys.argv[1],'rb');"
               "m=mmap.mmap(f.fileno(),0,access=mmap.ACCESS_READ);"
               "f.close();"
               "print('MMAP_READY',flush=True);"
               "time.sleep(3);"
               "m.close()")
        p=subprocess.Popen([sys.executable,"-c",child,str(target)],
                           stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        try:
            self.assertEqual(p.stdout.readline().strip(),"MMAP_READY")
            result=inspect_fixture_handles(self.root)
            self.assertFalse(result["copy_authorized"])
            self.assertFalse(result["all_handles_closed"])
            self.assertFalse(result["production_quiescence_proven"])
        finally:
            p.communicate(timeout=10)
if __name__=="__main__": unittest.main()
