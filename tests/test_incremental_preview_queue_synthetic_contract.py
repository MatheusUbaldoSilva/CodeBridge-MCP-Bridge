"""Synthetic Git-to-preview-to-queue integration; never writes installed RAG."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from rag.runtime.incremental_explicit_source_preview import preview_approved_unindexed_sources
from rag.runtime.incremental_preview_queue_handoff import prepare_preview_queue_handoff
from rag.runtime.incremental_job_queue import enqueue_source_event, inspect_job_queue


class SyntheticApprovedQueueContractTests(unittest.TestCase):
    def test_approved_commit_matches_durable_queue_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "CodeBridge-MCP-Bridge"
            root.mkdir()
            source = root / "sample.py"
            source.write_text("def approved():\n    return 42\n", encoding="utf-8")
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            subprocess.run(["git", "-C", str(root), "add", "sample.py"], check=True)
            subprocess.run(["git", "-C", str(root), "-c", "user.name=Test",
                            "-c", "user.email=test@example.invalid", "commit",
                            "-q", "-m", "safe source"], check=True)
            installed = base / "CodeBridge" / "rag"
            installed.mkdir(parents=True)
            (installed / "rag_index.sqlite3").write_bytes(b"synthetic")
            public = installed / "generations" / "v1_delta_1ae1d01ea84f4e"
            public.mkdir(parents=True)
            (public / "rag_index.sqlite3").write_bytes(b"synthetic")
            (public / "rag-index-manifest.json").write_text(
                json.dumps({"schema_version": 1, "entries": []}), encoding="utf-8",
            )
            pointer = {"state": "PUBLIC_POINTER_OBSERVED",
                       "generation": "v1_delta_1ae1d01ea84f4e"}
            with patch(
                "rag.runtime.incremental_explicit_source_preview.resolve_rag_sqlite_path",
                return_value=installed / "rag_index.sqlite3",
            ), patch(
                "rag.runtime.incremental_explicit_source_preview.inspect_public_pointer_for_scheduler",
                return_value=pointer,
            ), patch(
                "rag.runtime.incremental_explicit_source_preview.discover_installed_reindex_scope",
                return_value={"state": "INDEXED_SOURCES_CURRENT",
                              "indexed_entries_checked": 0},
            ):
                preview = preview_approved_unindexed_sources(
                    root, approved_paths=("sample.py",),
                    changed_at_epoch=100.0, debounce_seconds=30.0,
                    now_epoch=200.0,
                )
            self.assertEqual(preview["state"], "EXPLICIT_SOURCE_PREVIEW_ONLY")
            self.assertEqual(preview["candidates"][0]["state"], "ELIGIBLE_FOR_DURABLE_QUEUE")
            plan = prepare_preview_queue_handoff(preview, approved_paths=("sample.py",))
            self.assertEqual(plan["state"], "ADVISORY_QUEUE_INTENTS_PREPARED")
            self.assertFalse(plan["queued"])
            item = plan["intents"][0]
            synthetic_queue = base / "isolated" / "jobs" / "incremental_jobs.sqlite3"
            self.assertFalse(synthetic_queue.exists())
            queued = enqueue_source_event(
                synthetic_queue, root, item["source_path"],
                approved_paths=("sample.py",),
                observed_commit=item["observed_commit"],
                observed_sha256=item["observed_sha256"],
                changed_at_epoch=100.0, debounce_seconds=30.0,
                now_epoch=200.0, queue_enabled=True,
            )
            self.assertEqual(queued["state"], "QUEUED_DURABLY")
            self.assertEqual(queued["job_id"], item["prospective_job_id"])
            self.assertEqual(inspect_job_queue(synthetic_queue)["total"], 1)
            self.assertFalse(queued["active_index_updated"])
            self.assertFalse((installed / "jobs" / "incremental_jobs.sqlite3").exists())
            # The advisory preview can NEVER replace the real queue's
            # fresh Git/content checks. A dirty checkout must not create a DB.
            source.write_text("def edited_after_review():\n    return -1\n", encoding="utf-8")
            denied_db = base / "denied" / "jobs" / "incremental_jobs.sqlite3"
            dirty = enqueue_source_event(
                denied_db, root, item["source_path"],
                approved_paths=("sample.py",),
                observed_commit=item["observed_commit"],
                observed_sha256=item["observed_sha256"],
                changed_at_epoch=100.0, debounce_seconds=30.0,
                now_epoch=201.0, queue_enabled=True,
            )
            self.assertEqual(dirty["state"], "SOURCE_NOT_COMMITTED")
            self.assertFalse(denied_db.exists())

            # Even when the original file is clean again, changing HEAD
            # invalidates the old source-review intent.
            source.write_text("def approved():\n    return 42\n", encoding="utf-8")
            (root / "new-doc.md").write_text("later commit\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(root), "add", "new-doc.md"], check=True)
            subprocess.run(["git", "-C", str(root), "-c", "user.name=Test",
                            "-c", "user.email=test@example.invalid", "commit",
                            "-q", "-m", "move HEAD"], check=True)
            superseded = enqueue_source_event(
                denied_db, root, item["source_path"],
                approved_paths=("sample.py",),
                observed_commit=item["observed_commit"],
                observed_sha256=item["observed_sha256"],
                changed_at_epoch=100.0, debounce_seconds=30.0,
                now_epoch=202.0, queue_enabled=True,
            )
            self.assertEqual(superseded["state"], "COMMIT_SUPERSEDED")
            self.assertFalse(denied_db.exists())


if __name__ == "__main__":
    unittest.main()
