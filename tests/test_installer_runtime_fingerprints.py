import hashlib
import tempfile
import unittest
from pathlib import Path
from installer.runtime_fingerprints import fingerprint, fingerprint_tree, collect_runtime_fingerprints, compare_runtime_fingerprints, compare_saved_public_baseline

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
            "rag_manifest": {"exists": True, "sha256": "a"*64, "bytes": 1},
            "rag_sqlite": {"exists": True, "sha256": "b"*64, "bytes": 2},
            "rag_qdrant": {"exists": True, "sha256": "c"*64, "bytes": 3, "file_count": 2},
            "rag_qdrant": {"exists": True, "sha256": "c"*64, "bytes": 3, "file_count": 2},
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

    def test_truthy_non_boolean_integrity_metadata_is_rejected(self):
        baseline={"files":{
            "rag_manifest":{"exists":True,"sha256":"a"*64,"bytes":1},
            "rag_sqlite":{"exists":True,"sha256":"b"*64,"bytes":2},
            "rag_qdrant":{"exists":True,"sha256":"c"*64,"bytes":3,"file_count":2},
        }}
        for key, field, value in (
            ("rag_manifest","exists",1),
            ("rag_sqlite","exists","true"),
            ("rag_manifest","bytes",True),
            ("rag_sqlite","bytes",2.0),
            ("rag_qdrant","file_count",True),
            ("rag_qdrant","file_count",2.0),
        ):
            with self.subTest(key=key,field=field,value=value):
                forged={"files":{name:dict(data)
                                 for name,data in baseline["files"].items()}}
                forged["files"][key][field]=value
                result=compare_runtime_fingerprints(baseline,forged)
                self.assertFalse(result["public_index_intact"])
                self.assertFalse(result["protected_matches"][key])

    def test_identical_invalid_hashes_never_count_as_integrity_proof(self):
        for malformed in ("a", "z"*64, "A"*64, "", 123):
            with self.subTest(malformed=malformed):
                files={
                    "rag_manifest":{"exists":True,"sha256":malformed,"bytes":1},
                    "rag_sqlite":{"exists":True,"sha256":"b"*64,"bytes":2},
                    "rag_qdrant":{"exists":True,"sha256":"c"*64,"bytes":3,
                                  "file_count":2},
                }
                report=compare_runtime_fingerprints({"files":files},{"files":files})
                self.assertFalse(report["public_index_intact"])
                self.assertFalse(report["protected_matches"]["rag_manifest"])

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
                "rag_manifest":{"exists":True,"sha256":"a"*64,"bytes":1},
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

    def test_qdrant_tree_detects_file_addition_and_rename(self):
        with tempfile.TemporaryDirectory() as temp:
            tree=Path(temp)/"qdrant"
            tree.mkdir()
            original=tree/"a.bin"
            original.write_bytes(b"a")
            baseline=fingerprint_tree(tree)
            added=tree/"b.bin"
            added.write_bytes(b"b")
            after_add=fingerprint_tree(tree)
            self.assertEqual(after_add["file_count"],2)
            self.assertNotEqual(baseline["sha256"],after_add["sha256"])
            added.unlink()
            original.rename(tree/"renamed.bin")
            after_rename=fingerprint_tree(tree)
            self.assertEqual(after_rename["file_count"],1)
            self.assertNotEqual(baseline["sha256"],after_rename["sha256"])

    def test_symlinked_qdrant_file_blocks_fingerprint(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            tree=root/"qdrant"
            tree.mkdir()
            outside=root/"outside.bin"
            outside.write_bytes(b"fixture")
            linked=tree/"redirect.bin"
            try:
                linked.symlink_to(outside)
            except OSError:
                self.skipTest("Windows symlink permission unavailable")
            result=fingerprint_tree(tree)
            self.assertFalse(result["exists"])

    def test_malformed_public_baselines_fail_closed_without_exception(self):
        cases = [None, {}, {"files": None}, {"files": []},
                 {"files": {"rag_manifest": None}},
                 {"files": {"rag_manifest": "bad"}}]
        for before in cases:
            with self.subTest(before=before):
                result = compare_runtime_fingerprints(before, before)
                self.assertEqual(result["state"], "PUBLIC_INDEX_INTEGRITY_BLOCKED")
                self.assertFalse(result["public_index_intact"])

    def test_qdrant_file_disappearing_during_hash_fails_closed(self):
        from unittest.mock import patch
        import installer.runtime_fingerprints as fingerprints
        with tempfile.TemporaryDirectory() as temp:
            tree = Path(temp)/"qdrant"
            tree.mkdir()
            (tree/"vector.bin").write_bytes(b"test")
            with patch.object(fingerprints, "fingerprint",
                              side_effect=FileNotFoundError("vanished")):
                result = fingerprint_tree(tree)
        self.assertFalse(result["exists"])
        self.assertIsNone(result["sha256"])

    def test_junction_path_is_not_traversed(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as temp:
            tree=Path(temp)/"qdrant"
            tree.mkdir()
            (tree/"vector.bin").write_bytes(b"sample")
            with patch.object(Path, "is_junction", autospec=True,
                              side_effect=lambda item: item.name == "vector.bin",
                              create=True):
                result=fingerprint_tree(tree)
            self.assertFalse(result["exists"])
            self.assertIsNone(result["sha256"])

    def test_saved_baseline_detects_historical_drift(self):
        import json
        from unittest.mock import patch
        import installer.runtime_fingerprints as module
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/"saved.json"
            baseline = {"schema_version": 1,
                        "purpose": "rag-public-index-read-only-maintenance-baseline",
                        "files": {
                            "rag_manifest": {"exists":True,"sha256":"a"*64,"bytes":1},
                            "rag_sqlite": {"exists":True,"sha256":"b"*64,"bytes":2},
                            "rag_qdrant": {"exists":True,"sha256":"c"*64,"bytes":3,"file_count":1},
                        }}
            path.write_text(json.dumps(baseline),encoding="utf-8")
            current = {"files":dict(baseline["files"])}
            with patch.object(module,"collect_runtime_fingerprints",return_value=current):
                ok=compare_saved_public_baseline(path,Path(temp),Path(temp))
            self.assertTrue(ok["public_index_intact"])
            self.assertEqual(ok["changed_entries"],[])
            altered={"files": {**baseline["files"],
                              "rag_qdrant":{"exists":True,"sha256":"altered","bytes":3,"file_count":1}}}
            with patch.object(module,"collect_runtime_fingerprints",return_value=altered):
                result=compare_saved_public_baseline(path,Path(temp),Path(temp))
            self.assertFalse(result["public_index_intact"])

    def test_missing_or_invalid_saved_baseline_fails_closed(self):
        import json
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/"missing.json"
            result=compare_saved_public_baseline(path,Path(temp),Path(temp))
            self.assertEqual(result["state"],"PUBLIC_BASELINE_INVALID")
            path.write_text('{"schema_version":1,"purpose":"wrong","files":{}}')
            result=compare_saved_public_baseline(path,Path(temp),Path(temp))
            self.assertFalse(result["public_index_intact"])

    def test_duplicate_json_keys_are_rejected_before_runtime_access(self):
        from unittest.mock import patch
        import installer.runtime_fingerprints as module
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/"saved.json"
            samples=(
                '{"schema_version":1,"schema_version":1}',
                '{"schema_version":1,"purpose":"rag-public-index-read-only-maintenance-baseline","files":{"rag_manifest":{},"rag_manifest":{}}}',
            )
            for raw in samples:
                with self.subTest(raw=raw):
                    path.write_text(raw,encoding="utf-8")
                    with patch.object(module,"collect_runtime_fingerprints",
                                      side_effect=AssertionError("no runtime probing")):
                        report=compare_saved_public_baseline(
                            path,Path(temp),Path(temp))
                    self.assertEqual(report["state"],"PUBLIC_BASELINE_INVALID")
                    self.assertFalse(report["public_index_intact"])

    def test_boolean_schema_version_cannot_claim_public_baseline_v1(self):
        import json
        from unittest.mock import patch
        import installer.runtime_fingerprints as module
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/"saved.json"
            valid={"schema_version":True,
                   "purpose":"rag-public-index-read-only-maintenance-baseline",
                   "files":{
                       "rag_manifest":{"exists":True,"sha256":"a"*64,"bytes":1},
                       "rag_sqlite":{"exists":True,"sha256":"b"*64,"bytes":2},
                       "rag_qdrant":{"exists":True,"sha256":"c"*64,"bytes":3,
                                     "file_count":1},
                   }}
            path.write_text(json.dumps(valid),encoding="utf-8")
            with patch.object(module,"collect_runtime_fingerprints",
                              side_effect=AssertionError("no runtime probing")):
                result=compare_saved_public_baseline(path,Path(temp),Path(temp))
            self.assertEqual(result["state"],"PUBLIC_BASELINE_INVALID")
            self.assertFalse(result["public_index_intact"])

    def test_cli_missing_saved_baseline_returns_error(self):
        import subprocess
        import sys
        with tempfile.TemporaryDirectory() as temp:
            base=Path(temp)
            command=[sys.executable,"-m","installer.runtime_fingerprints",
                     "--install-root",str(base/"install"),
                     "--rag-state",str(base/"rag"),
                     "--compare-baseline",str(base/"missing.json")]
            result=subprocess.run(command,capture_output=True,text=True,
                                  cwd=Path(__file__).resolve().parents[1],timeout=30)
            self.assertEqual(result.returncode,2,result.stderr)
            self.assertIn("PUBLIC_BASELINE_INVALID",result.stdout)
            self.assertFalse((base/"rag").exists())

    def test_symlinked_public_manifest_is_not_accepted(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            external=root/"outside.txt"
            external.write_text("outside")
            manifest=root/"rag-index-manifest.json"
            try:
                manifest.symlink_to(external)
            except OSError:
                self.skipTest("Windows symlink permission unavailable")
            result=fingerprint(manifest)
            self.assertFalse(result["exists"])
            self.assertIsNone(result["sha256"])

    def test_historical_baseline_rejects_malformed_digest_and_counts(self):
        import json
        import installer.runtime_fingerprints as module
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/"baseline.json"
            valid = json.loads((Path(__file__).resolve().parents[1] /
                "tests/fixtures/rag_public_index_baseline_fixture.json").read_text())
            for field, invalid in (("sha256", "not-a-hash"),
                                   ("bytes", -1), ("exists", False)):
                modified = json.loads(json.dumps(valid))
                modified["files"]["rag_manifest"][field] = invalid
                path.write_text(json.dumps(modified), encoding="utf-8")
                with patch.object(module, "collect_runtime_fingerprints") as probe:
                    result = compare_saved_public_baseline(path, Path(temp), Path(temp))
                self.assertEqual(result["state"], "PUBLIC_BASELINE_INVALID")
                probe.assert_not_called()
            modified = json.loads(json.dumps(valid))
            modified["files"]["rag_qdrant"]["file_count"] = 0
            path.write_text(json.dumps(modified), encoding="utf-8")
            self.assertEqual(compare_saved_public_baseline(path, Path(temp), Path(temp))["state"],
                             "PUBLIC_BASELINE_INVALID")

    def test_public_file_vanishes_during_open_fails_closed(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/"rag-index-manifest.json"
            path.write_bytes(b"fixture")
            original=Path.open
            def open_then_vanish(item,*args,**kwargs):
                if item == path:
                    raise FileNotFoundError("file vanished")
                return original(item,*args,**kwargs)
            with patch.object(Path,"open",autospec=True,side_effect=open_then_vanish):
                result=fingerprint(path)
            self.assertEqual(result,{"exists":False,"sha256":None,"bytes":None})
