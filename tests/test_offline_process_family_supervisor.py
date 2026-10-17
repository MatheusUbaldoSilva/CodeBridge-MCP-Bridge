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
 def test_child_spawned_after_parent_exit_blocks(self):
  r=inspect_family_shutdown_samples(10,[shot(row(10,0)),shot(),shot(row(22,10))])
  self.assertIn("LATE_CHILD_OBSERVED",r["issues"])
 def test_descendant_reappearing_blocks(self):
  r=inspect_family_shutdown_samples(10,[shot(row(10,0),row(11,10)),shot(row(11,10)),shot(row(10,0),row(11,10))])
  self.assertIn("FAMILY_PROCESS_REAPPEARED",r["issues"])
 def test_missing_parent_identity_blocks_initial_snapshot(self):
  data=shot(row(10,0))
  data["verified_pids"][0].pop("created_at")
  r=inspect_family_shutdown_samples(10,[data,shot(),shot()])
  self.assertEqual(r["state"],"BLOCKED")
  self.assertFalse(r["copy_authorized"])
 def test_missing_child_identity_blocks_followup(self):
  incomplete=shot(row(11,10))
  incomplete["verified_pids"][0].pop("executable_fingerprint")
  r=inspect_family_shutdown_samples(10,[shot(row(10,0),row(11,10)),incomplete,shot()])
  self.assertEqual(r["state"],"BLOCKED")
  self.assertFalse(r["copy_authorized"])
 def test_unrelated_row_missing_identity_blocks(self):
  invalid=row(999,0);invalid.pop("executable_fingerprint")
  r=inspect_family_shutdown_samples(10,[shot(row(10,0)),shot(invalid),shot()])
  self.assertEqual(r["state"],"BLOCKED")
  self.assertFalse(r["copy_authorized"])
 def test_invalid_pid_type_blocks(self):
  invalid=row(99,0);invalid["pid"]=True
  r=inspect_family_shutdown_samples(10,[shot(row(10,0)),shot(invalid),shot()])
  self.assertEqual(r["state"],"BLOCKED")
 def test_untrusted_snapshot_blocks(self):
  bad=shot();bad["identity_inventory_ok"]=False
  r=inspect_family_shutdown_samples(10,[shot(row(10,0)),bad,shot()])
  self.assertIn("UNTRUSTED_PROCESS_INVENTORY",r["issues"])
if __name__=="__main__":unittest.main()
