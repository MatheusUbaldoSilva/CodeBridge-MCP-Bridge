import subprocess
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rag.runtime.offline_scoped_cim_observer import observe_scoped_windows_pids

CHILD = ("import sys;"
         "print('LAB_READY',flush=True);"
         "sys.exit(0 if sys.stdin.readline().strip()=='LAB_STOP' else 3)")

@unittest.skipUnless(sys.platform=="win32","Windows-only scoped identity drill")
class LabScopedCooperativeIdentity(unittest.TestCase):
    def test_known_child_creation_identity_and_consecutive_absence(self):
        child=subprocess.Popen([sys.executable,"-c",CHILD],
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,text=True)
        try:
            self.assertEqual(child.stdout.readline().strip(),"LAB_READY")
            before=observe_scoped_windows_pids([child.pid])
            self.assertEqual(before["state"],"SCOPED_CIM_OBSERVATION_UNPROVEN")
            self.assertEqual(len(before["verified_pids"]),1)
            self.assertEqual(before["verified_pids"][0]["pid"],child.pid)
            child.stdin.write("LAB_STOP\n")
            child.stdin.flush()
            self.assertEqual(child.wait(timeout=8),0)
            absent1=observe_scoped_windows_pids([child.pid])
            absent2=observe_scoped_windows_pids([child.pid])
            self.assertEqual(absent1["state"],"SCOPED_CIM_OBSERVATION_UNPROVEN")
            self.assertEqual(absent2["state"],"SCOPED_CIM_OBSERVATION_UNPROVEN")
            self.assertEqual(absent1["verified_pids"],[])
            self.assertEqual(absent2["verified_pids"],[])
            self.assertFalse(before["copy_authorized"])
            self.assertFalse(absent2["production_quiescence_proven"])
            self.assertFalse(absent2["all_handles_closed"])
        finally:
            if child.poll() is None:
                child.stdin.close()
                child.wait(timeout=8)
            for stream in (child.stdin,child.stdout,child.stderr):
                if stream and not stream.closed:
                    stream.close()

if __name__=="__main__":
    unittest.main()
