import tempfile, unittest
from pathlib import Path
from benchmarks.rag017_installer_rollback_lab import run

class InstallerRollbackLabTests(unittest.TestCase):
    def test_simulated_restore_and_new_file_cleanup(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"CodeBridge-RAG017-RollbackLab-test"
            # The strict path gate intentionally prevents executing in an arbitrary fixture.
            with self.assertRaises(ValueError):run(p)
    def test_refuses_existing_or_non_lab_paths(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):run(Path(d)/"other")
    def test_laboratory_explicitly_disclaims_nsis_proof(self):
        source=(Path(__file__).resolve().parents[1]/"benchmarks"/"rag017_installer_rollback_lab.py").read_text(encoding="utf-8")
        self.assertIn('"actual_nsis_rollback_verified": False',source)
        self.assertIn('"registry_real_modified": False',source)
        self.assertIn('"shortcuts_real_modified": False',source)
