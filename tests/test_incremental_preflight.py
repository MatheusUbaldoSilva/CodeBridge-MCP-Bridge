"""Read-only incremental safety checks, never touching production."""
import sqlite3
import tempfile
import unittest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rag.runtime.incremental_preflight import assess_incremental_plan


class IncrementalPreflightTests(unittest.TestCase):
    def test_new_and_existing_and_no_mutation(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "index.sqlite3"
            con = sqlite3.connect(db)
            try:
                con.execute("CREATE TABLE rag_documents(project_id TEXT, path TEXT, sha256 TEXT)")
                con.execute("INSERT INTO rag_documents VALUES (?, ?, ?)", ("a", "existing.md", None))
                con.commit()
            finally:
                con.close()
            original = db.read_bytes()
            result = assess_incremental_plan({
                "project_id": "a",
                "candidates": [{"path": "existing.md"}, {"path": "new.md"}],
            }, database=db)
            self.assertEqual(result["new_files"], ["new.md"])
            self.assertEqual(result["existing_files"], ["existing.md"])
            self.assertFalse(result["safe_to_publish"])
            gate = result["publication_gate"]
            self.assertEqual(gate["state"], "BLOCKED")
            self.assertIn("PRODUCTION_ATOMIC_GENERATION_WRITER_NOT_WIRED", gate["reasons"])
            self.assertIn("NEW_SOURCES_REQUIRE_INDIVIDUAL_APPROVAL", gate["reasons"])
            self.assertEqual(db.read_bytes(), original)

    def test_modified_unchanged_and_project_isolation(self):
        from rag.chunking.provenance import source_sha256
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'same.md').write_text('original', encoding='utf-8')
            (root / 'changed.md').write_text('new text', encoding='utf-8')
            db = root / 'index.sqlite3'
            con = sqlite3.connect(db)
            try:
                con.execute('CREATE TABLE rag_documents(project_id TEXT, path TEXT, sha256 TEXT)')
                con.executemany('INSERT INTO rag_documents VALUES (?, ?, ?)', [
                    ('a', 'same.md', source_sha256('original')),
                    ('a', 'changed.md', source_sha256('old text')),
                    ('b', 'other.md', source_sha256('else')),
                ])
                con.commit()
            finally:
                con.close()
            before = db.read_bytes()
            result = assess_incremental_plan({
                'project_id': 'a', 'project_root': str(root),
                'candidates': [{'path': 'same.md'}, {'path': 'changed.md'},
                               {'path': 'other.md'}],
            }, database=db)
            self.assertEqual(result['unchanged_files'], ['same.md'])
            self.assertEqual(result['modified_files'], ['changed.md'])
            self.assertEqual(result['new_files'], ['other.md'])
            self.assertFalse(result['safe_to_publish'])
            self.assertEqual(db.read_bytes(), before)

    def test_missing_db_and_bad_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = assess_incremental_plan({
                "project_id": "fresh", "candidates": [{"path": "note.md"}],
            }, database=Path(tmp) / "missing.sqlite3")
            self.assertEqual(result["new_count"], 1)
            with self.assertRaises(ValueError):
                assess_incremental_plan({"project_id": "a", "candidates": ["invalid"]},
                                        database=Path(tmp) / "missing.sqlite3")


    def test_full_inventory_detects_potential_rename_only_when_complete(self):
        from rag.chunking.provenance import source_sha256
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "renamed.md").write_text("same content", encoding="utf-8")
            db = root / "rag.sqlite3"
            conn = sqlite3.connect(db)
            try:
                conn.execute("CREATE TABLE rag_documents(project_id TEXT, path TEXT, sha256 TEXT)")
                conn.execute("INSERT INTO rag_documents VALUES (?, ?, ?)",
                             ("codebridge", "previous.md", source_sha256("same content")))
                conn.commit()
            finally:
                conn.close()
            before = db.read_bytes()
            plan = {
                "project_id": "codebridge", "project_root": str(root),
                "scope": "BOTH", "candidates": [{"path": "renamed.md"}],
            }
            limited = assess_incremental_plan(plan, database=db)
            self.assertEqual(limited["removed_files"], [])
            self.assertEqual(limited["rename_candidates"], [])
            complete = assess_incremental_plan(plan, database=db, full_inventory=True)
            self.assertEqual(complete["removed_files"], ["previous.md"])
            self.assertEqual(
                complete["rename_candidates"][0]["to"], "renamed.md"
            )
            self.assertFalse(complete["safe_to_publish"])
            self.assertEqual(db.read_bytes(), before)
            with self.assertRaises(ValueError):
                assess_incremental_plan(
                    dict(plan, scope="TEXT"), database=db, full_inventory=True
                )


class ProductionSourceFreshnessTests(unittest.TestCase):
    def test_crlf_only_checkout_does_not_trigger_reindex(self):
        import hashlib
        import json
        from rag.runtime.production_source_freshness import (
            assess_generation_source_freshness,
        )
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "CodeBridge-MCP-Bridge"
            root.mkdir()
            (root / ".git").mkdir()
            source = root / "sample.py"
            source.write_bytes(b"line1\r\nline2\r\n")
            other = root / "exact.md"
            other.write_bytes(b"fixed")
            snapshot = Path(temp) / "generation"
            snapshot.mkdir()
            manifest = snapshot / "rag-index-manifest.json"
            contents = {"entries": [
                {"path": "sample.py", "project_id": "codebridge",
                 "sha256": hashlib.sha256(b"line1\nline2\n").hexdigest()},
                {"path": "exact.md", "project_id": "codebridge",
                 "sha256": hashlib.sha256(b"fixed").hexdigest()},
            ]}
            manifest.write_text(json.dumps(contents), encoding="utf-8")
            before = manifest.read_bytes()
            result = assess_generation_source_freshness(snapshot, root)
            self.assertEqual(result["state"], "SOURCE_SNAPSHOT_CURRENT")
            self.assertEqual(result["byte_exact"], 1)
            self.assertEqual(result["newline_only"], 1)
            self.assertEqual(result["content_changed"], 0)
            self.assertFalse(result["safe_to_activate"])
            self.assertEqual(manifest.read_bytes(), before)
            self.assertEqual(source.read_bytes(), b"line1\r\nline2\r\n")

    def test_edited_and_missing_sources_block_current_snapshot(self):
        import hashlib
        import json
        from rag.runtime.production_source_freshness import (
            assess_generation_source_freshness,
        )
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "CodeBridge-MCP-Bridge"
            root.mkdir()
            (root / ".git").mkdir()
            (root / "edited.py").write_text("new version", encoding="utf-8")
            snapshot = Path(temp) / "generation"
            snapshot.mkdir()
            contents = {"entries": [
                {"path": "edited.py", "project_id": "codebridge",
                 "sha256": hashlib.sha256(b"old version").hexdigest()},
                {"path": "missing.md", "project_id": "codebridge",
                 "sha256": hashlib.sha256(b"missing").hexdigest()},
            ]}
            (snapshot / "rag-index-manifest.json").write_text(
                json.dumps(contents), encoding="utf-8",
            )
            result = assess_generation_source_freshness(snapshot, root)
            self.assertEqual(result["state"], "SOURCE_SNAPSHOT_DRIFT")
            self.assertEqual(result["content_changed_paths"], ["edited.py"])
            self.assertEqual(result["missing_paths"], ["missing.md"])
            self.assertEqual(result["content_changed"], 1)
            self.assertEqual(result["missing"], 1)

    def test_rejects_path_escape_and_non_codebridge_root(self):
        import json
        from rag.runtime.production_source_freshness import (
            assess_generation_source_freshness,
        )
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "CodeBridge-MCP-Bridge"
            root.mkdir()
            (root / ".git").mkdir()
            snapshot = Path(temp) / "generation"
            snapshot.mkdir()
            (snapshot / "rag-index-manifest.json").write_text(
                json.dumps({"entries": [
                    {"path": "../secrets.txt", "project_id": "codebridge",
                     "sha256": "a" * 64},
                ]}), encoding="utf-8",
            )
            with self.assertRaises(ValueError):
                assess_generation_source_freshness(snapshot, root)
            with self.assertRaises(ValueError):
                assess_generation_source_freshness(snapshot, Path(temp))


class CutoverManifestDeltaTests(unittest.TestCase):
    def test_added_and_modified_manifest_paths_and_chunk_updates(self):
        from rag.index.manifest import (
            ManifestEntry, ManifestIndexKind, IndexManifest, save_index_manifest,
        )
        from rag.runtime.production_cutover_gate import _summarize_manifest_delta

        def make(path, sha, chunks=("chunk1",)):
            return ManifestEntry(
                project_id="codebridge", index_kind=ManifestIndexKind.CODE,
                path=path, size=20, mtime_ns=1,
                sha256=sha * 64, chunk_ids=chunks, model_version="code-v1",
            )

        with tempfile.TemporaryDirectory() as tmp:
            before = Path(tmp) / "before.json"
            after = Path(tmp) / "after.json"
            save_index_manifest(before, IndexManifest(entries=(
                make("old.py", "a"),
                make("modified.py", "b"),
                make("rechunked.py", "c"),
            )))
            save_index_manifest(after, IndexManifest(entries=(
                make("old.py", "a"),
                make("modified.py", "d"),
                make("rechunked.py", "c", ("chunk_new",)),
                make("new.py", "e"),
            )))
            result = _summarize_manifest_delta(before, after)
            self.assertEqual(result["added_paths"], ["new.py"])
            self.assertEqual(
                result["modified_paths"], ["modified.py", "rechunked.py"],
            )
            self.assertEqual(result["removed_paths"], [])
            self.assertEqual(result["unchanged_count"], 1)
            self.assertFalse(result["operator_content_review_attested"])

    def test_removed_manifest_path_is_not_silently_ignored(self):
        from rag.index.manifest import (
            ManifestEntry, ManifestIndexKind, IndexManifest, save_index_manifest,
        )
        from rag.runtime.production_cutover_gate import _summarize_manifest_delta
        old = ManifestEntry(
            project_id="codebridge", index_kind=ManifestIndexKind.CODE,
            path="removed.py", size=10, mtime_ns=1,
            sha256="a" * 64, chunk_ids=("chunk1",), model_version="code-v1",
        )
        with tempfile.TemporaryDirectory() as tmp:
            a = Path(tmp) / "a.json"
            b = Path(tmp) / "b.json"
            save_index_manifest(a, IndexManifest(entries=(old,)))
            save_index_manifest(b, IndexManifest(entries=()))
            result = _summarize_manifest_delta(a, b)
            self.assertEqual(result["removed_paths"], ["removed.py"])
            self.assertEqual(result["removed_count"], 1)
            self.assertEqual(result["added_count"], 0)
