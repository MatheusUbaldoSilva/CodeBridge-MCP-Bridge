"""Synthetic stale-source Git-to-queue proof using the actual freshness comparator."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from rag.chunking.provenance import source_sha256
from rag.index.manifest import ManifestEntry, ManifestIndexKind
from rag.runtime.incremental_installed_change_discovery import discover_installed_reindex_scope
from rag.runtime.incremental_explicit_source_preview import preview_approved_unindexed_sources
from rag.runtime.incremental_preview_queue_handoff import prepare_preview_queue_handoff
from rag.runtime.incremental_job_queue import (enqueue_source_event, inspect_job_queue, claim_approved_job)


class ChangedIndexedSourceSyntheticTests(unittest.TestCase):
    def test_new_committed_version_is_a_stale_source_reindex_candidate(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            repo = folder / "CodeBridge-MCP-Bridge"
            repo.mkdir()
            source = repo / "sample.py"
            source.write_text("def initial():\n    return 1\n", encoding="utf-8")
            original_hash = source_sha256(source.read_text(encoding="utf-8"))
            subprocess.run(["git", "init", "-q", str(repo)], check=True)
            subprocess.run(["git", "-C", str(repo), "add", "sample.py"], check=True)
            git_commit = ["git", "-C", str(repo), "-c", "user.name=Test",
                          "-c", "user.email=synthetic@test.invalid", "commit", "-q"]
            subprocess.run([*git_commit, "-m", "initial"], check=True)

            installed = folder / "CodeBridge" / "rag"
            installed.mkdir(parents=True)
            (installed / "rag_index.sqlite3").write_bytes(b"synthetic-baseline")
            version = "v1_delta_1ae1d01ea84f4e"
            generation = installed / "generations" / version
            generation.mkdir(parents=True)
            (generation / "rag_index.sqlite3").write_bytes(b"synthetic-generation")
            entry = ManifestEntry(
                project_id="codebridge", index_kind=ManifestIndexKind.CODE,
                path="sample.py", size=20, mtime_ns=1,
                sha256=original_hash, chunk_ids=("test-chunk",), model_version="synthetic",
            )
            (generation / "rag-index-manifest.json").write_text(json.dumps(
                {"schema_version": 1, "entries": [entry.to_dict()]}
            ), encoding="utf-8")

            source.write_text("def improved():\n    return 2\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(repo), "add", "sample.py"], check=True)
            subprocess.run([*git_commit, "-m", "improved"], check=True)

            pointer = {"state": "PUBLIC_POINTER_OBSERVED", "generation": version}
            with patch(
                "rag.runtime.incremental_installed_change_discovery.resolve_rag_sqlite_path",
                return_value=installed / "rag_index.sqlite3",
            ), patch(
                "rag.runtime.incremental_installed_change_discovery.inspect_public_pointer_for_scheduler",
                return_value=pointer,
            ), patch(
                "rag.runtime.incremental_explicit_source_preview.resolve_rag_sqlite_path",
                return_value=installed / "rag_index.sqlite3",
            ), patch(
                "rag.runtime.incremental_explicit_source_preview.inspect_public_pointer_for_scheduler",
                return_value=pointer,
            ):
                observed = discover_installed_reindex_scope(repo)
                self.assertEqual(observed["state"], "INDEXED_SOURCES_DRIFT_FOUND")
                self.assertEqual(observed["content_changed_paths"], ["sample.py"])
                preview = preview_approved_unindexed_sources(
                    repo, approved_paths=("sample.py",),
                    changed_at_epoch=100, now_epoch=200, debounce_seconds=10,
                )
                self.assertEqual(preview["state"], "EXPLICIT_SOURCE_PREVIEW_ONLY")
                candidate = preview["candidates"][0]
                self.assertEqual(candidate["intent"], "REINDEX_CHANGED")
                self.assertEqual(candidate["state"], "ELIGIBLE_FOR_DURABLE_QUEUE")

            intent = prepare_preview_queue_handoff(
                preview, approved_paths=("sample.py",),
            )
            self.assertEqual(intent["state"], "ADVISORY_QUEUE_INTENTS_PREPARED")
            item = intent["intents"][0]
            self.assertEqual(item["purpose"], "REINDEX_CHANGED")
            queue = folder / "isolated" / "jobs" / "incremental_jobs.sqlite3"
            queued = enqueue_source_event(
                queue, repo, item["source_path"],
                approved_paths=("sample.py",),
                observed_commit=item["observed_commit"],
                observed_sha256=item["observed_sha256"],
                changed_at_epoch=100, now_epoch=200,
                debounce_seconds=10, queue_enabled=True,
            )
            self.assertEqual(queued["state"], "QUEUED_DURABLY")
            self.assertEqual(queued["job_id"], item["prospective_job_id"])
            self.assertEqual(inspect_job_queue(queue)["total"], 1)
            claimed = claim_approved_job(
                queue, repo, approved_paths=("sample.py",),
                now_epoch=201, queue_enabled=True,
            )
            self.assertEqual(claimed["state"], "CLAIMED_FOR_OFFLINE_STAGING")
            self.assertEqual(claimed["job_id"], item["prospective_job_id"])
            second = claim_approved_job(
                queue, repo, approved_paths=("sample.py",),
                now_epoch=202, queue_enabled=True,
            )
            self.assertEqual(second["state"], "QUEUE_EMPTY")
            self.assertEqual(inspect_job_queue(queue)["by_state"], {"CLAIMED": 1})
            self.assertFalse((installed / "jobs" / "incremental_jobs.sqlite3").exists())


if __name__ == "__main__":
    unittest.main()
