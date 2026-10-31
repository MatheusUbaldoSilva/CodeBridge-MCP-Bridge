"""G-13 bounded manual scratch soak parameters."""
from unittest import TestCase
from benchmarks.rag_del_mac_pipe_soak_dev import soak

class SoakRunnerDevTests(TestCase):
    def test_reject_zero(self):
        with self.assertRaises(ValueError):soak(0)
    def test_reject_unbounded(self):
        with self.assertRaises(ValueError):soak(501)
    def test_small_soak_never_authorizes(self):
        result=soak(2)
        self.assertEqual(result["iterations"],2)
        self.assertFalse(result["activation_authorized"])

    def test_direct_script_from_repo_root(self):
        import subprocess,sys
        from pathlib import Path
        root=Path(__file__).resolve().parents[1]
        cmd=[sys._base_executable,"-B",
            str(root/"benchmarks"/"rag_del_mac_pipe_soak_dev.py"),
            "--iterations","1"]
        completed=subprocess.run(cmd,cwd=root,capture_output=True,
            text=True,timeout=8,check=True)
        self.assertIn("SCRATCH_REAL_WORKER_SOAK_PASS",completed.stdout)
