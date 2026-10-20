import hashlib
import tempfile
import unittest
from pathlib import Path
from installer.runtime_fingerprints import fingerprint, fingerprint_tree, collect_runtime_fingerprints, compare_runtime_fingerprints

class RuntimeFingerprintTests(unittest.TestCase):
    def test_binary_sha256_exact_and_read_only(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/"binary.bin"
            payload=b"\x00AB\xff\x00"
            path.write_bytes(payload)
            before=path.stat().st_mtime_ns
            value=fingerprint(path)
            self.assertEqual(value["sha256"],hashlib.sha256(payload).hexdigest())
            self.assertEqual(value["bytes"],len(payload))
            self.assertEqual(path.stat().st_mtime_ns,before)

    def test_missing_files_not_created(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/"not-installed"
            state=Path(temp)/"rag-not-created"
            result=collect_runtime_fingerprints(root,state)
            self.assertEqual(result["state"],"READ_ONLY_RUNTIME_FINGERPRINTS")
            self.assertFalse(any(x["exists"] for x in result["files"].values()))
            self.assertFalse(root.exists())
            self.assertFalse(state.exists())
            self.assertFalse(result["writes_performed"])

    def test_protected_index_hashes_must_match(self):
        baseline = {"files": {
            "rag_manifest": {"exists": True, "sha256": "a", "bytes": 1},
            "rag_sqlite": {"exists": True, "sha256": "b", "bytes": 2},
            "rag_qdrant": {"exists": True, "sha256": "q", "bytes": 3, "file_count": 2},
            "rag_qdrant": {"exists": True, "sha256": "q", "bytes": 3, "file_count": 2},
            "python_path": {"exists": True, "sha256": "c", "bytes": 3},
        }}
        updated = {"files": {
            **baseline["files"],
            "python_path": {"exists": True, "sha256": "d", "bytes": 4},
        }}
        accepted = compare_runtime_fingerprints(baseline,updated)
        self.assertEqual(accepted["state"],"PUBLIC_INDEX_UNCHANGED")
        self.assertEqual(accepted["changed_entries"],["python_path"])
        updated["files"]["rag_sqlite"] = {"exists": True, "sha256": "different", "bytes": 2}
        rejected = compare_runtime_fingerprints(baseline,updated)
        self.assertEqual(rejected["state"],"PUBLIC_INDEX_INTEGRITY_BLOCKED")
        self.assertFalse(rejected["public_index_intact"])

    def test_missing_public_hash_fails_closed(self):
        baseline={"files":{"rag_sqlite":{"exists":True,"sha256":"x","bytes":1}}}
        result=compare_runtime_fingerprints(baseline,baseline)
        self.assertFalse(result["public_index_intact"])

    def test_qdrant_tree_hash_detects_vector_file_mutation(self):
        with tempfile.TemporaryDirectory() as temp:
            tree=Path(temp)/"qdrant"
            tree.mkdir()
            vector=tree/"storage.bin"
            vector.write_bytes(b"original")
            first=fingerprint_tree(tree)
            self.assertEqual(first["file_count"],1)
            vector.write_bytes(b"modified")
            second=fingerprint_tree(tree)
            self.assertNotEqual(first["sha256"],second["sha256"])
            baseline={"files":{
                "rag_manifest":{"exists":True,"sha256":"m","bytes":1},
                "rag_sqlite":{"exists":True,"sha256":"s","bytes":1},
                "rag_qdrant":first,
            }}
            current={"files":{**baseline["files"],"rag_qdrant":second}}
            result=compare_runtime_fingerprints(baseline,current)
            self.assertFalse(result["public_index_intact"])
            self.assertFalse(result["protected_matches"]["rag_qdrant"])

    def test_empty_qdrant_tree_blocks_baseline(self):
        with tempfile.TemporaryDirectory() as temp:
            tree=Path(temp)/"qdrant"
            tree.mkdir()
            self.assertFalse(fingerprint_tree(tree)["exists"])
