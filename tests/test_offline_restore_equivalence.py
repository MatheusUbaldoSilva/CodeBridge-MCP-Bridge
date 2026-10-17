import sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from test_incremental_bundle_e2e import create_bundle
from rag.runtime.offline_fixture_snapshot import capture_fixture
from rag.runtime.offline_fixture_restore import restore_fixture_snapshot
from rag.runtime.offline_restore_equivalence import audit_restored_fixture

class RestoreEquivalenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)/"codebridge-rag-generation-test"
        create_bundle(self.root,[("alpha","file","one"),("beta","note","two")])
        capture_fixture(self.root,"first")
        restore_fixture_snapshot(self.root,"first","recovered")
    def test_two_project_cross_store_roundtrip(self):
        r=audit_restored_fixture(self.root,"first","recovered")
        self.assertTrue(r["same_hashes"]);self.assertTrue(r["same_semantic_content"])
        self.assertEqual(r["state"],"LAB_RESTORE_EQUIVALENCE_UNPROVEN_FOR_PRODUCTION")
        self.assertFalse(r["production_authorized"])
    def test_tampered_restored_manifest_blocks(self):
        p=self.root/"offline-fixture-restores"/"recovered"/"snapshot"/"rag-index-manifest.json"
        p.write_bytes(b"tampered")
        r=audit_restored_fixture(self.root,"first","recovered")
        self.assertEqual(r["state"],"BLOCKED")
        self.assertIn("SNAPSHOT_RESTORE_HASH_MISMATCH",r["issues"])
    def test_tampered_restored_sqlite_blocks(self):
        p=self.root/"offline-fixture-restores"/"recovered"/"snapshot"/"rag_index.sqlite3"
        p.write_bytes(b"corrupt")
        r=audit_restored_fixture(self.root,"first","recovered")
        self.assertEqual(r["state"],"BLOCKED")
    def test_tampered_qdrant_payload_blocks(self):
        root=self.root/"offline-fixture-restores"/"recovered"/"snapshot"/"qdrant"
        target=next(p for p in root.rglob("*") if p.is_file())
        with target.open("ab") as f: f.write(b"synthetic-corruption")
        r=audit_restored_fixture(self.root,"first","recovered")
        self.assertEqual(r["state"],"BLOCKED")
        self.assertFalse(r["same_semantic_content"])
    def test_symlink_in_restored_tree_blocks(self):
        q=self.root/"offline-fixture-restores"/"recovered"/"snapshot"/"qdrant"
        (q/"redirected").symlink_to(self.root.parent,target_is_directory=True)
        result=audit_restored_fixture(self.root,"first","recovered")
        self.assertEqual(result["state"],"BLOCKED")
        self.assertFalse(result["production_authorized"])
    def test_tampered_report_blocks(self):
        import json
        report=self.root/"offline-fixture-backups"/"first"/"report.json"
        data=json.loads(report.read_text(encoding="utf-8"))
        data["production_authorized"]=True
        report.write_text(json.dumps(data),encoding="utf-8")
        result=audit_restored_fixture(self.root,"first","recovered")
        self.assertEqual(result["state"],"BLOCKED")
    def test_changed_during_semantic_validation_blocks(self):
        from unittest.mock import patch
        import rag.runtime.offline_restore_equivalence as audit
        original=audit._hash_tree
        sequence=[0]
        def drifting(root):
            sequence[0]+=1
            values=original(root)
            if sequence[0]>=3:
                values=dict(values,synthetic_drift="0"*64)
            return values
        with patch.object(audit,"_hash_tree",side_effect=drifting):
            result=audit_restored_fixture(self.root,"first","recovered")
        self.assertEqual(result["state"],"BLOCKED")
        self.assertIn("STORES_CHANGED_DURING_VALIDATION",result["issues"])
    def test_unknown_restore_blocks(self):
        r=audit_restored_fixture(self.root,"first","missing")
        self.assertEqual(r["state"],"BLOCKED")
    def test_unsafe_root_blocks(self):
        r=audit_restored_fixture(self.root.parent,"first","recovered")
        self.assertEqual(r["state"],"BLOCKED")
if __name__=="__main__": unittest.main()
