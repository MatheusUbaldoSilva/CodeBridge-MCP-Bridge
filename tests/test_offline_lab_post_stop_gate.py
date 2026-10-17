import sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from test_incremental_bundle_e2e import create_bundle
from rag.runtime.offline_lab_post_stop_gate import inspect_synthetic_after_stop

class LabPostStopGateTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory(prefix="rag-lab03-f-")
        self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name)/"codebridge-rag-generation-test"
        create_bundle(self.root,[("lab","store","synthetic")])
    def test_cooperative_exit_and_store_read_still_unproven(self):
        report=inspect_synthetic_after_stop(self.root)
        self.assertEqual(report["state"],"LAB_POST_STOP_STORES_READABLE_UNPROVEN")
        self.assertGreaterEqual(report["lab_files_checked"],3)
        self.assertFalse(report["copy_authorized"])
        self.assertFalse(report["all_handles_closed"])
        self.assertFalse(report["production_quiescence_proven"])
    def test_late_sqlite_sidecar_rejects_post_stop_gate(self):
        (self.root/"rag_index.sqlite3-wal").write_bytes(b"synthetic WAL")
        report=inspect_synthetic_after_stop(self.root)
        self.assertEqual(report["state"],"BLOCKED")
        self.assertFalse(report["copy_authorized"])
    def test_missing_vector_store_rejects_gate(self):
        import shutil
        shutil.rmtree(self.root/"qdrant")
        report=inspect_synthetic_after_stop(self.root)
        self.assertEqual(report["state"],"BLOCKED")
        self.assertFalse(report["production_quiescence_proven"])

if __name__=="__main__":
    unittest.main()
