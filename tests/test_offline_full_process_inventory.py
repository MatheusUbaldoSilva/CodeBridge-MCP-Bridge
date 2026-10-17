import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rag.runtime.offline_full_process_inventory import inspect_full_process_inventory
from rag.runtime.offline_process_family_audit import audit_known_family

def row(pid, ppid, name="another.exe"):
    return {"ProcessId":pid,"ParentProcessId":ppid,"Name":name,
            "ExecutablePath":"C:\\Test\\program.exe","CreationDate":"20261017114500"}

def fake(items):
    return lambda *a,**k: SimpleNamespace(stdout=json.dumps(items))

class FullProcessInventoryTests(unittest.TestCase):
    def test_descendant_with_unrecognized_name_remains_visible(self):
        report=inspect_full_process_inventory(runner=fake([
            row(100,0,"CodeBridge.exe"),row(101,100,"unrelated-name.exe"),
            row(102,101,"child.exe")]))
        self.assertTrue(report["identity_inventory_ok"])
        family=audit_known_family(100,report)
        self.assertEqual(family["known_descendant_pids"],[101,102])
        self.assertFalse(family["copy_authorized"])
        self.assertFalse(report["production_quiescence_proven"])
        self.assertNotIn("C:\\Test",str(report))
    def test_unreadable_path_fails_closed(self):
        a=row(1,0);a["ExecutablePath"]=None
        report=inspect_full_process_inventory(runner=fake([a]))
        self.assertEqual(report["state"],"BLOCKED")
        self.assertFalse(report["identity_inventory_ok"])
    def test_duplicate_pid_fails_closed(self):
        report=inspect_full_process_inventory(runner=fake([row(1,0),row(1,0)]))
        self.assertEqual(report["state"],"BLOCKED")
    def test_empty_inventory_fails_closed(self):
        report=inspect_full_process_inventory(runner=fake([]))
        self.assertEqual(report["state"],"BLOCKED")
    def test_kernel_idle_pid_zero_is_recorded_not_authorized(self):
        report=inspect_full_process_inventory(runner=fake([
            row(0,0,"System Idle Process"),row(10,0)]))
        self.assertEqual(report["kernel_pid_zero_excluded"],1)
        self.assertEqual([r["pid"] for r in report["verified_pids"]],[10])
        self.assertFalse(report["copy_authorized"])
    def test_no_copy_authorization_even_clean(self):
        report=inspect_full_process_inventory(runner=fake([row(10,0)]))
        self.assertFalse(report["copy_authorized"])
        self.assertFalse(report["all_handles_closed"])
if __name__=="__main__":
    unittest.main()
