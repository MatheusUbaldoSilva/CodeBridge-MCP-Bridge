import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from rag.runtime.incremental_explicit_source_preview import preview_approved_unindexed_sources


class ExplicitSourcePreviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        base = Path(self.temp.name)
        self.repo = base / "CodeBridge-MCP-Bridge"
        self.repo.mkdir()
        (self.repo / "sample.py").write_text("def stable():\n    return 42\n", encoding="utf-8")
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)
        subprocess.run(["git", "-C", str(self.repo), "add", "sample.py"], check=True)
        subprocess.run(["git", "-C", str(self.repo), "-c", "user.name=Test",
                        "-c", "user.email=example@test.invalid", "commit",
                        "-q", "-m", "fixture"], check=True)
        self.public = base / "CodeBridge" / "rag"
        self.public.mkdir(parents=True)
        (self.public / "rag_index.sqlite3").write_bytes(b"baseline")
        folder = self.public / "generations" / "v1_delta_1ae1d01ea84f4e"
        folder.mkdir(parents=True)
        (folder / "rag_index.sqlite3").write_bytes(b"candidate")
        self.manifest = folder / "rag-index-manifest.json"
        self.manifest.write_text(json.dumps({"schema_version": 1, "entries": []}), encoding="utf-8")
        self.pointer = {"state": "PUBLIC_POINTER_OBSERVED",
                        "generation": "v1_delta_1ae1d01ea84f4e"}

    def evaluate(self, *, observed=None, **kwargs):
        with patch(
            "rag.runtime.incremental_explicit_source_preview.resolve_rag_sqlite_path",
            return_value=self.public / "rag_index.sqlite3",
        ), patch(
            "rag.runtime.incremental_explicit_source_preview.inspect_public_pointer_for_scheduler",
            return_value=self.pointer,
        ), patch(
            "rag.runtime.incremental_explicit_source_preview.discover_installed_reindex_scope",
            return_value=observed or {"state": "INDEXED_SOURCES_CURRENT"},
        ):
            return preview_approved_unindexed_sources(self.repo, **kwargs)

    def test_no_explicit_approval_never_scans(self):
        value = self.evaluate()
        self.assertEqual(value["state"], "SOURCE_APPROVAL_AND_OBSERVATION_REQUIRED")
        self.assertFalse(value["queued"])

    def test_committed_unindexed_source_can_be_previewed_only(self):
        value = self.evaluate(approved_paths=("sample.py",),
                              changed_at_epoch=0, debounce_seconds=0, now_epoch=1000)
        self.assertEqual(value["state"], "EXPLICIT_SOURCE_PREVIEW_ONLY")
        self.assertEqual(value["candidates"][0]["state"], "ELIGIBLE_FOR_DURABLE_QUEUE")
        self.assertFalse(value["queued"])
        self.assertFalse(value["safe_to_publish"])

    def test_uncommitted_content_refused(self):
        (self.repo / "sample.py").write_text("def changed():\n    return 43\n", encoding="utf-8")
        value = self.evaluate(approved_paths=("sample.py",),
                              changed_at_epoch=0, debounce_seconds=0, now_epoch=1000)
        self.assertEqual(value["candidates"][0]["state"], "SOURCE_NOT_COMMITTED")

    def test_already_indexed_source_not_previewed(self):
        from rag.index.manifest import ManifestEntry, ManifestIndexKind
        entry = ManifestEntry(project_id="codebridge", index_kind=ManifestIndexKind.CODE,
                              path="sample.py", size=10, mtime_ns=1, sha256="a" * 64,
                              chunk_ids=("chunk-1",), model_version="test")
        self.manifest.write_text(json.dumps({"schema_version": 1, "entries": [
            entry.to_dict()
        ]}), encoding="utf-8")
        value = self.evaluate(approved_paths=("sample.py",), changed_at_epoch=0)
        self.assertEqual(value["candidates"][0]["state"], "ALREADY_INDEXED")

    def test_committed_stale_indexed_source_is_reviewed_for_reindex(self):
        from rag.index.manifest import ManifestEntry, ManifestIndexKind
        entry = ManifestEntry(project_id="codebridge", index_kind=ManifestIndexKind.CODE,
                              path="sample.py", size=10, mtime_ns=1, sha256="a" * 64,
                              chunk_ids=("chunk-1",), model_version="test")
        self.manifest.write_text(json.dumps({"schema_version": 1, "entries": [
            entry.to_dict()
        ]}), encoding="utf-8")
        report = self.evaluate(
            approved_paths=("sample.py",), changed_at_epoch=0, now_epoch=1000,
            observed={"state": "INDEXED_SOURCES_DRIFT_FOUND",
                      "indexed_entries_checked": 1,
                      "content_changed_paths": ["sample.py"], "missing_paths": []},
        )
        self.assertEqual(report["candidates"][0]["intent"], "REINDEX_CHANGED")
        self.assertEqual(report["candidates"][0]["state"], "ELIGIBLE_FOR_DURABLE_QUEUE")
        self.assertFalse(report["queued"])

    def test_missing_indexed_source_is_not_enqueued(self):
        from rag.index.manifest import ManifestEntry, ManifestIndexKind
        entry = ManifestEntry(project_id="codebridge", index_kind=ManifestIndexKind.CODE,
                              path="sample.py", size=10, mtime_ns=1, sha256="a" * 64,
                              chunk_ids=("chunk-1",), model_version="test")
        self.manifest.write_text(json.dumps({"schema_version": 1, "entries": [
            entry.to_dict()
        ]}), encoding="utf-8")
        report = self.evaluate(
            approved_paths=("sample.py",), changed_at_epoch=0,
            observed={"state": "INDEXED_SOURCES_DRIFT_FOUND",
                      "indexed_entries_checked": 1,
                      "content_changed_paths": [], "missing_paths": ["sample.py"]},
        )
        self.assertEqual(report["candidates"][0]["state"], "INDEXED_SOURCE_MISSING_NEEDS_REVIEW")
        self.assertFalse(report["queued"])

    def test_manifest_entry_count_changed_during_discovery_denies_preview(self):
        with patch(
            "rag.runtime.incremental_explicit_source_preview.discover_installed_reindex_scope",
            return_value={"state": "INDEXED_SOURCES_CURRENT",
                          "indexed_entries_checked": 211},
        ), patch(
            "rag.runtime.incremental_explicit_source_preview.resolve_rag_sqlite_path",
            return_value=self.public / "rag_index.sqlite3",
        ), patch(
            "rag.runtime.incremental_explicit_source_preview.inspect_public_pointer_for_scheduler",
            return_value=self.pointer,
        ):
            value = preview_approved_unindexed_sources(
                self.repo, approved_paths=("sample.py",), changed_at_epoch=0,
            )
        self.assertEqual(value["state"], "PUBLIC_MANIFEST_SNAPSHOT_MISMATCH")
        self.assertFalse(value["queued"])

    def test_invalid_public_manifest_fails_closed(self):
        self.manifest.write_text('{"entries":[]}', encoding="utf-8")
        value = self.evaluate(approved_paths=("sample.py",), changed_at_epoch=0)
        self.assertEqual(value["state"], "SOURCE_PREVIEW_FAILED")
        self.assertFalse(value["queued"])

    def test_nonfinite_observation_refused(self):
        value = self.evaluate(approved_paths=("sample.py",), changed_at_epoch=float("nan"))
        self.assertEqual(value["state"], "INVALID_OBSERVATION_TIME")


if __name__ == "__main__":
    unittest.main()
