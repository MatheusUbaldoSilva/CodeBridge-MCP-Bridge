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


class ProductionContentReviewTests(unittest.TestCase):
    def _fixture(self, home):
        import hashlib
        import sqlite3
        from rag.index.manifest import (
            IndexManifest, ManifestEntry, ManifestIndexKind,
            save_index_manifest,
        )
        generations = home / "generations"
        old = generations / "v1_base_review"
        new = generations / "v1_delta_review"
        old.mkdir(parents=True)
        new.mkdir(parents=True)

        def make(folder, rows):
            conn = sqlite3.connect(folder / "rag_index.sqlite3")
            conn.execute(
                "CREATE TABLE rag_documents"
                "(path TEXT,content TEXT,sha256 TEXT,project_id TEXT)"
            )
            items = []
            for path, content, chunks in rows:
                digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
                conn.execute(
                    "INSERT INTO rag_documents VALUES(?,?,?,?)",
                    (path, content, digest, "codebridge"),
                )
                items.append(ManifestEntry(
                    project_id="codebridge", index_kind=ManifestIndexKind.CODE,
                    path=path, size=len(content), mtime_ns=1,
                    sha256=digest, chunk_ids=chunks, model_version="model-v1",
                ))
            conn.commit()
            conn.close()
            save_index_manifest(
                folder / "rag-index-manifest.json",
                IndexManifest(entries=tuple(items)),
            )
        make(old, [("old.py", "before\n", ("chunk_old",))])
        make(new, [
            ("old.py", "after\n", ("chunk_new",)),
            ("new.py", "first\nsecond\n", ("chunk_added",)),
        ])
        return old, new

    def test_compares_exact_content_and_never_authenticates_review(self):
        from rag.runtime.production_content_review import (
            summarize_versioned_source_review,
        )
        with tempfile.TemporaryDirectory() as temp:
            old, new = self._fixture(Path(temp))
            original = (new / "rag_index.sqlite3").read_bytes()
            report = summarize_versioned_source_review(old, new)
            self.assertEqual(report["state"], "CONTENT_COMPARISON_ONLY_NOT_APPROVED")
            self.assertEqual(report["added_paths"], ["new.py"])
            self.assertEqual(report["modified_paths"], ["old.py"])
            self.assertEqual(report["removed_paths"], [])
            self.assertEqual(len(report["details"]), 2)
            self.assertFalse(report["operator_content_review_attested"])
            self.assertFalse(report["safe_to_activate"])
            self.assertEqual(len(report["evidence_sha256_not_signature"]), 64)
            self.assertEqual(
                (new / "rag_index.sqlite3").read_bytes(), original,
            )

    def test_refuses_tampered_indexed_content_and_unsafe_generation(self):
        import sqlite3
        from rag.runtime.production_content_review import (
            summarize_versioned_source_review,
        )
        with tempfile.TemporaryDirectory() as temp:
            old, new = self._fixture(Path(temp))
            with __import__("contextlib").closing(sqlite3.connect(new / "rag_index.sqlite3")) as db:
                db.execute(
                    "UPDATE rag_documents SET content=? WHERE path='old.py'",
                    ("tampered",),
                )
                db.commit()
            with self.assertRaisesRegex(ValueError, "source SHA"):
                summarize_versioned_source_review(old, new)
            with self.assertRaises(ValueError):
                summarize_versioned_source_review(old, old)


class ProductionSingleUseTrialReplayTests(unittest.TestCase):
    def test_valid_fresh_evidence_passes_once_then_archived_pointer_blocks_replay(self):
        import hashlib
        from datetime import datetime, timezone
        from unittest.mock import patch
        from rag.runtime.production_supervised_trial import assess_supervised_trial

        candidate = "v1_delta_test"
        baseline = "v1_base_test"
        allowed = {
            "author_mcp/mcp_server.py", "author_mcp/rag_bridge.py",
            "rag/runtime/production_index.py",
            "rag/runtime/production_search.py", "rag/runtime/status.py",
        }
        policy = [
            "PUBLIC_MCP_READERS_RESTART_NOT_ATTESTED",
            "ATOMIC_PRODUCTION_POINTER_WRITER_AND_ROLLBACK_NOT_VALIDATED",
            "CHANGED_SOURCE_CONTENT_REVIEW_NOT_ATTESTED",
        ]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "CodeBridge" / "rag"
            candidate_root = root / "generations" / candidate
            candidate_root.mkdir(parents=True)
            receipt = candidate_root / "generation-receipt.json"
            receipt.write_bytes(b"validated-candidate-receipt")
            candidate_sha = hashlib.sha256(receipt.read_bytes()).hexdigest()
            date = datetime.now(timezone.utc).isoformat()
            proof = {
                "schema_version": 1,
                "operator_authorization": "CODEBRIDGE_RAG_V1_ACTIVATE:" + candidate,
                "authorization_scope":
                    "APPROVED_SOURCE_CHANGES_AND_SUPERVISED_TRIAL_WITH_ROLLBACK",
                "rollback_rehearsal": "REAL_WIN32_GENERATION_TRANSITION_TESTS_PASS",
                "source_review_fingerprint": "a" * 64,
                "candidate_receipt_sha256": candidate_sha,
                "public_mcp_pid": 1304,
                "public_readiness": {
                    "recorded_at_utc": date,
                    "state": "PUBLIC_HYBRID_CONCURRENCY_PASS_READONLY",
                    "candidate": candidate,
                    "candidate_receipt_sha256": candidate_sha,
                    "activation_permitted": False,
                    "public_proof": {
                        "state": "PUBLIC_HYBRID_CONCURRENCY_PASS",
                        "safe_to_activate": False,
                        "index_pointer_updated": False,
                        "public_reader": {
                            "public_server_pid": 1304,
                            "reader_pin_proved": True,
                            "semantic_worker_serialization_loaded": True,
                            "public_runtime_ready_for_hybrid_acceptance": True,
                            "generation": "legacy",
                        },
                        "status": {
                            "generation": "legacy",
                            "documents": 210, "chunks": 8761,
                        },
                        "cross_store_integrity": {
                            "state": "OBSERVED_CONSISTENT",
                            "generation": "legacy",
                            "documents": 210, "chunks": 8761,
                        },
                        "hybrid_concurrent": [
                            {"ok": True, "route": "HYBRID",
                             "results": 3, "error_type": None}
                            for _ in range(3)
                        ],
                    },
                },
            }
            with patch(
                "rag.runtime.production_supervised_trial.resolve_rag_sqlite_path",
                return_value=root / "rag_index.sqlite3",
            ), patch(
                "rag.runtime.production_supervised_trial.assess_real_cutover",
                return_value={
                    "blockers": policy,
                    "state": "BLOCKED",
                    "safe_to_activate": False,
                    "verified": {"candidate": {"validation": {}}},
                },
            ), patch(
                "rag.runtime.production_supervised_trial.summarize_versioned_source_review",
                return_value={
                    "evidence_sha256_not_signature": "a" * 64,
                    "modified_paths": sorted(allowed),
                    "added_paths": ["rag/runtime/live_integrity.py"],
                    "removed_paths": [],
                },
            ):
                initial = assess_supervised_trial(baseline, candidate, proof)
                self.assertEqual(initial["state"], "READY_FOR_SUPERVISED_TRIAL")
                self.assertTrue(initial["safe_to_activate"])
                archive = root / ("recovered-pointer-" + candidate + ".json")
                archive.write_text('{"generation":"v1_delta_test"}', encoding="utf-8")
                rejected = assess_supervised_trial(baseline, candidate, proof)
                self.assertEqual(rejected["state"], "BLOCKED")
                self.assertFalse(rejected["safe_to_activate"])
                self.assertIn("SUPERVISED_TRIAL_ALREADY_CONSUMED", rejected["blockers"])
                self.assertFalse(rejected["supervised_trial"])


class IncrementalPrequeueTests(unittest.TestCase):
    def test_approved_committed_change_debounces_without_enqueuing(self):
        import subprocess
        from rag.chunking.provenance import source_sha256
        from rag.runtime.incremental_job_prequeue import assess_commit_index_event as gate
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp) / "CodeBridge-MCP-Bridge"
            repo.mkdir()
            f = repo / "sample.py"
            f.write_text("def example():\n    return 42\n", encoding="utf-8")
            subprocess.run(["git", "init", "-q", str(repo)], check=True)
            subprocess.run(["git", "-C", str(repo), "add", "sample.py"], check=True)
            subprocess.run(["git", "-C", str(repo), "-c", "user.name=Test",
                            "-c", "user.email=test@example.invalid", "commit",
                            "-q", "-m", "test"], check=True)
            head = subprocess.check_output(
                ["git", "-C", str(repo), "rev-parse", "HEAD"], text=True,
            ).strip()
            options = dict(indexing_enabled=True, approved_paths=("sample.py",),
                           observed_commit=head,
                           observed_sha256=source_sha256(f.read_text(encoding="utf-8")),
                           changed_at_epoch=100, debounce_seconds=30)
            self.assertEqual(gate(repo, "sample.py")["state"], "AUTO_INDEX_DISABLED")
            self.assertEqual(gate(repo, "sample.py", now_epoch=119, **options)["state"],
                             "AWAITING_STABLE_COMMIT")
            ready = gate(repo, "sample.py", now_epoch=135, **options)
            self.assertEqual(ready["state"], "ELIGIBLE_FOR_DURABLE_QUEUE")
            self.assertFalse(ready["queued"])
            self.assertFalse(ready["safe_to_publish"])
            self.assertFalse(ready["worker_available"])
            self.assertEqual(gate(repo, "sample.py", now_epoch=135,
                                  **{**options, "approved_paths": ()})["state"],
                             "SOURCE_NOT_APPROVED")
            self.assertEqual(gate(repo, "sample.py", now_epoch=135,
                                  **{**options, "observed_commit": "0"*40})["state"],
                             "COMMIT_SUPERSEDED")
            f.write_text("def example():\n    return 43\n", encoding="utf-8")
            self.assertEqual(gate(repo, "sample.py", now_epoch=135, **options)["state"],
                             "SOURCE_NOT_COMMITTED")

    def test_parent_traversal_is_rejected(self):
        from rag.runtime.incremental_job_prequeue import assess_commit_index_event
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp) / "CodeBridge-MCP-Bridge"
            repo.mkdir()
            (repo / ".git").mkdir()
            result = assess_commit_index_event(
                repo, "../outside.py", approved_paths=("../outside.py",),
                indexing_enabled=True,
            )
            self.assertEqual(result["state"], "INVALID_SOURCE_PATH")
            self.assertFalse(result["queued"])
