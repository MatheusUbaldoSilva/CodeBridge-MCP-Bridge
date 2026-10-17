import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from rag.runtime.offline_process_family_supervisor import inspect_family_shutdown_samples
def row(pid,ppid):
 return {"pid":pid,"parent_pid":ppid,"created_at":"20261017100000","executable_fingerprint":"a"*64}
def shot(*rows):
 return {"identity_inventory_ok":True,"unverified_count":0,"verified_pids":list(rows)}
class FamilySupervisorTests(unittest.TestCase):
 def test_known_family_exits(self):
  r=inspect_family_shutdown_samples(10,[shot(row(10,0),row(11,10)),shot(),shot()])
  self.assertEqual(r["state"],"LAB_FAMILY_ABSENT_UNPROVEN")
  self.assertFalse(r["copy_authorized"])
 def test_late_child_blocks(self):
  r=inspect_family_shutdown_samples(10,[shot(row(10,0)),shot(row(10,0),row(12,10)),shot()])
  self.assertIn("LATE_CHILD_OBSERVED",r["issues"])
 def test_parent_exits_child_remains(self):
  r=inspect_family_shutdown_samples(10,[shot(row(10,0),row(11,10)),shot(row(11,10)),shot(row(11,10))])
  self.assertEqual(r["state"],"BLOCKED")
 def test_reused_descendant_pid_blocks(self):
  child=row(11,10)
  changed=dict(child,created_at="20261018103000")
  r=inspect_family_shutdown_samples(10,[shot(row(10,0),child),shot(changed),shot()])
  self.assertIn("FAMILY_PID_IDENTITY_CHANGED",r["issues"])
  self.assertFalse(r["copy_authorized"])
 def test_untrusted_snapshot_blocks(self):
  bad=shot();bad["identity_inventory_ok"]=False
  r=inspect_family_shutdown_samples(10,[shot(row(10,0)),bad,shot()])
  self.assertIn("UNTRUSTED_PROCESS_INVENTORY",r["issues"])
if __name__=="__main__":unittest.main()
