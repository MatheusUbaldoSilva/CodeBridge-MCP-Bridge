import json, sys, unittest
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rag.runtime.offline_scoped_cim_observer import observe_scoped_windows_pids
from rag.runtime.offline_process_sample_contract import validate_observation_series

def row(pid, parent=0, born="20261017120000", path="C:/lab/python.exe"):
    return dict(ProcessId=pid, ParentProcessId=parent, CreationDate=born, ExecutablePath=path)
def runner(data):
    return lambda *a, **kw: SimpleNamespace(stdout=json.dumps(data))
class ScopedObserverTests(unittest.TestCase):
    def test_two_known_lab_children_sanitized(self):
        out=observe_scoped_windows_pids([101,100],runner=runner([row(100),row(101,100)]))
        self.assertTrue(out["identity_inventory_ok"])
        self.assertEqual(out["state"],"SCOPED_CIM_OBSERVATION_UNPROVEN")
        self.assertEqual([r["pid"] for r in out["verified_pids"]],[100,101])
        self.assertNotIn("C:/lab",str(out))
        self.assertFalse(out["copy_authorized"])
        self.assertFalse(out["all_handles_closed"])
        from datetime import datetime, timedelta
        later = []
        for step in range(3):
            entry = dict(out)
            entry["observed_start_utc"] = (datetime.fromisoformat(out["observed_start_utc"]) + timedelta(seconds=step)).isoformat()
            entry["observed_end_utc"] = (datetime.fromisoformat(out["observed_end_utc"]) + timedelta(seconds=step)).isoformat()
            later.append(entry)
        chain=validate_observation_series(later)
        self.assertEqual(chain["state"],"TIMED_LAB_OBSERVATIONS_VALID_UNPROVEN")
    def test_unknown_process_is_not_trusted(self):
        out=observe_scoped_windows_pids([100],runner=runner([row(999)]))
        self.assertEqual(out["state"],"BLOCKED")
        self.assertFalse(out["copy_authorized"])
    def test_path_unavailable_blocks(self):
        out=observe_scoped_windows_pids([100],runner=runner([row(100,path=None)]))
        self.assertEqual(out["unverified_count"],1)
        self.assertEqual(out["state"],"BLOCKED")
    def test_duplicates_block(self):
        out=observe_scoped_windows_pids([100],runner=runner([row(100),row(100)]))
        self.assertEqual(out["state"],"BLOCKED")
    def test_empty_sample_is_scoped_only(self):
        out=observe_scoped_windows_pids([100],runner=runner([]))
        self.assertEqual(out["verified_pids"],[])
        self.assertEqual(out["state"],"SCOPED_CIM_OBSERVATION_UNPROVEN")
        self.assertFalse(out["production_quiescence_proven"])
    def test_invalid_lab_scope_blocks(self):
        for scope in ([],[0],[True],[123,123],[-1]):
            with self.subTest(scope=scope):
                self.assertEqual(observe_scoped_windows_pids(scope)["state"],"BLOCKED")
    def test_cim_failure_fails_closed(self):
        def fails(*a,**kw):
            raise OSError("CIM unavailable")
        out=observe_scoped_windows_pids([100],runner=fails)
        self.assertEqual(out["state"],"BLOCKED")
        self.assertEqual(out["issues"],["OSError"])
    def test_does_not_ask_for_command_line(self):
        calls=[]
        def fake(command,**kw):
            calls.append(command)
            return SimpleNamespace(stdout="[]")
        observe_scoped_windows_pids([100],runner=fake)
        self.assertEqual(len(calls),1)
        self.assertNotIn("CommandLine",str(calls))
        self.assertIn("ProcessId = 100",str(calls))
if __name__=="__main__":unittest.main()
