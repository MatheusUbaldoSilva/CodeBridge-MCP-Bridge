import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from rag.runtime.incremental_installed_change_discovery import discover_installed_reindex_scope


class InstalledReindexDiscoveryTests(unittest.TestCase):
    def make_store(self, temp):
        root = Path(temp) / "CodeBridge" / "rag"
        root.mkdir(parents=True)
        (root / "rag_index.sqlite3").write_bytes(b"legacy")
        selected = root / "generations" / "v1_delta_1ae1d01ea84f4e"
        selected.mkdir(parents=True)
        (selected / "rag_index.sqlite3").write_bytes(b"selected")
        return root, selected

    def evaluate(self, root, fresh, pointer=None):
        if pointer is None:
            pointer = {"state": "PUBLIC_POINTER_OBSERVED",
                       "generation": "v1_delta_1ae1d01ea84f4e"}
        with patch(
            "rag.runtime.incremental_installed_change_discovery.resolve_rag_sqlite_path",
            return_value=root / "rag_index.sqlite3",
        ), patch(
            "rag.runtime.incremental_installed_change_discovery.inspect_public_pointer_for_scheduler",
            side_effect=[pointer, pointer],
        ), patch(
            "rag.runtime.incremental_installed_change_discovery.assess_generation_source_freshness",
            return_value=fresh,
        ):
            return discover_installed_reindex_scope("ignored")

    def test_current_public_snapshot_never_authorizes_enqueue(self):
        with tempfile.TemporaryDirectory() as temp:
            root, _ = self.make_store(temp)
            result = self.evaluate(root, {
                "state": "SOURCE_SNAPSHOT_CURRENT",
                "indexed_entries_checked": 211,
                "content_changed_paths": [], "missing_paths": [],
            })
            self.assertEqual(result["state"], "INDEXED_SOURCES_CURRENT")
            self.assertFalse(result["enqueue_authorized"])
            self.assertFalse(result["queue_updated"])

    def test_stale_sources_reported_without_scheduling(self):
        with tempfile.TemporaryDirectory() as temp:
            root, _ = self.make_store(temp)
            result = self.evaluate(root, {
                "state": "SOURCE_SNAPSHOT_DRIFT",
                "indexed_entries_checked": 211,
                "content_changed_paths": ["rag/runtime/status.py"],
                "missing_paths": ["docs/obsolete.md"],
            })
            self.assertEqual(result["state"], "INDEXED_SOURCES_DRIFT_FOUND")
            self.assertEqual(result["content_changed_paths"], ["rag/runtime/status.py"])
            self.assertFalse(result["worker_started"])

    def test_pending_journal_blocks(self):
        with tempfile.TemporaryDirectory() as temp:
            root, _ = self.make_store(temp)
            (root / "production-generation-transition.json").write_text("{}")
            result = self.evaluate(root, {})
            self.assertEqual(result["state"], "DISCOVERY_BLOCKED")
            self.assertIn("PUBLIC_TRANSITION_PENDING", result["blockers"])

    def test_missing_public_generation_blocks(self):
        with tempfile.TemporaryDirectory() as temp:
            root, selected = self.make_store(temp)
            (selected / "rag_index.sqlite3").unlink()
            result = self.evaluate(root, {})
            self.assertIn("SELECTED_PUBLIC_INDEX_MISSING", result["blockers"])


if __name__ == "__main__":
    unittest.main()
