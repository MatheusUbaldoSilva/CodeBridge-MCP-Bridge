import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rag.runtime.offline_process_family_audit import audit_known_family

def record(pid, parent):
    return {"pid":pid, "parent_pid":parent, "created_at":"20261017100000",
            "executable_fingerprint":"a"*64}
def snapshot(rows, ok=True):
    return {"identity_inventory_ok":ok, "unverified_count":0, "verified_pids":rows}

class FamilyAuditTests(unittest.TestCase):
    def test_descendants_are_transitive_and_never_authorized(self):
        result = audit_known_family(100, snapshot([
            record(100, 0), record(200,100), record(300,200), record(400,500)]))
        self.assertEqual(result["known_descendant_pids"],[200,300])
        self.assertEqual(result["unresolved_parent_pids"],[500])
        self.assertFalse(result["copy_authorized"])
        self.assertFalse(result["all_processes_known"])
    def test_root_missing_blocks(self):
        self.assertEqual(audit_known_family(100,snapshot([record(200,100)]))["state"],"BLOCKED")
    def test_duplicate_pid_blocks(self):
        self.assertEqual(audit_known_family(100,snapshot([record(100,0),record(100,0)]))["state"],"BLOCKED")
    def test_untrusted_inventory_blocks(self):
        self.assertEqual(audit_known_family(100,snapshot([record(100,0)],False))["state"],"BLOCKED")
    def test_cyclic_parent_relationship_blocks(self):
        self.assertEqual(audit_known_family(100,snapshot([
            record(100,200), record(200,100)]))["state"],"BLOCKED")
    def test_self_parent_blocks(self):
        self.assertEqual(audit_known_family(100,snapshot([
            record(100,100)]))["state"],"BLOCKED")
    def test_unknown_identity_blocks(self):
        r=record(100,0);r["created_at"]=None
        self.assertEqual(audit_known_family(100,snapshot([r]))["state"],"BLOCKED")
if __name__=="__main__":
    unittest.main()
