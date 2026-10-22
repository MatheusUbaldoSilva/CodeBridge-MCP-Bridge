from io import StringIO
import json
import unittest
from unittest.mock import patch

from rag.runtime.incremental_installed_change_discovery_cli import main


class InstalledChangeDiscoveryCliTests(unittest.TestCase):
    def test_default_never_previews_unapproved_sources(self):
        with patch("rag.runtime.incremental_installed_change_discovery_cli.discover_installed_reindex_scope",
                   return_value={"state": "INDEXED_SOURCES_CURRENT"}), patch(
            "rag.runtime.incremental_installed_change_discovery_cli.preview_approved_unindexed_sources",
            side_effect=AssertionError("unexpected approval"),
        ), patch("sys.stdout", new_callable=StringIO) as out:
            status = main([])
        self.assertEqual(status, 0)
        self.assertNotIn("new_source_preview", json.loads(out.getvalue()))

    def test_pending_journal_exits_blocked(self):
        with patch("rag.runtime.incremental_installed_change_discovery_cli.discover_installed_reindex_scope",
                   return_value={"state": "DISCOVERY_BLOCKED", "blockers": ["PUBLIC_TRANSITION_PENDING"]}), patch(
            "sys.stdout", new_callable=StringIO,
        ):
            self.assertEqual(main([]), 2)

    def test_explicit_source_without_time_denies(self):
        with patch("rag.runtime.incremental_installed_change_discovery_cli.discover_installed_reindex_scope",
                   return_value={"state": "INDEXED_SOURCES_CURRENT"}), patch(
            "rag.runtime.incremental_installed_change_discovery_cli.preview_approved_unindexed_sources",
            return_value={"state": "SOURCE_APPROVAL_AND_OBSERVATION_REQUIRED"},
        ) as preview, patch("sys.stdout", new_callable=StringIO):
            self.assertEqual(main(["--approve-source", "sample.py"]), 2)
        self.assertEqual(preview.call_args.kwargs["approved_paths"], ("sample.py",))

    def test_selected_uncommitted_source_fails_closed(self):
        with patch("rag.runtime.incremental_installed_change_discovery_cli.discover_installed_reindex_scope",
                   return_value={"state": "INDEXED_SOURCES_CURRENT"}), patch(
            "rag.runtime.incremental_installed_change_discovery_cli.preview_approved_unindexed_sources",
            return_value={"state": "EXPLICIT_SOURCE_PREVIEW_ONLY",
                          "candidates": [{"state": "SOURCE_NOT_COMMITTED"}]},
        ), patch("sys.stdout", new_callable=StringIO):
            status = main(["--approve-source", "sample.py", "--changed-at-epoch", "123"])
        self.assertEqual(status, 2)

    def test_candidate_awaiting_debounce_fails_closed(self):
        with patch("rag.runtime.incremental_installed_change_discovery_cli.discover_installed_reindex_scope",
                   return_value={"state": "INDEXED_SOURCES_CURRENT"}), patch(
            "rag.runtime.incremental_installed_change_discovery_cli.preview_approved_unindexed_sources",
            return_value={"state": "EXPLICIT_SOURCE_PREVIEW_ONLY",
                          "candidates": [{"state": "AWAITING_STABLE_COMMIT"}]},
        ), patch("sys.stdout", new_callable=StringIO):
            self.assertEqual(main(["--approve-source", "sample.py",
                                   "--changed-at-epoch", "123"]), 2)

    def test_preview_produces_read_only_report(self):
        with patch("rag.runtime.incremental_installed_change_discovery_cli.discover_installed_reindex_scope",
                   return_value={"state": "INDEXED_SOURCES_CURRENT"}), patch(
            "rag.runtime.incremental_installed_change_discovery_cli.preview_approved_unindexed_sources",
            return_value={"state": "EXPLICIT_SOURCE_PREVIEW_ONLY", "queued": False, "candidates": [{"state": "ELIGIBLE_FOR_DURABLE_QUEUE"}]},
        ), patch("sys.stdout", new_callable=StringIO) as out:
            self.assertEqual(main(["--approve-source", "sample.py",
                                   "--changed-at-epoch", "123"]), 0)
            report = json.loads(out.getvalue())
        self.assertFalse(report["queue_updated"])
        self.assertFalse(report["new_source_preview"]["queued"])


if __name__ == "__main__":
    unittest.main()
