"""Safe multi-project registry and MCP routes regression tests."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"author_mcp"))

from rag.runtime import isolated_project_index as catalog
from author_mcp import rag_bridge


class IsolatedProjectRegistryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        home=Path(self.tmp.name)
        self.workspace=home/"CodeBridge-RAG-Workspace"
        self.workspace.mkdir()
        self.source=self.workspace/"candidate"/"source"
        self.source.mkdir(parents=True)
        self.stage=self.workspace/"candidate"/"generations"/"revision"
        self.stage.mkdir(parents=True)
        (self.stage/"qdrant").mkdir()
        (self.stage/"rag_index.sqlite3").write_bytes(b"sqlite-test")
        (self.stage/"rag-index-manifest.json").write_bytes(b"manifest-test")
        self.rev="a"*40
        (self.stage/"progress.json").write_text(json.dumps({
            "project_id":"lab-rag", "source_revision":self.rev,
            "state":"INDEXING_NOT_PUBLISHED",
            "total_vectors_done":3,"expected_chunks":3,
            "last_batch_result":"PASS", "published":False,
        }),encoding="utf-8")
        from hashlib import sha256
        self.row={
            "enabled":True,"project_id":"lab-rag",
            "generation_directory":str(self.stage),
            "source_directory":str(self.source),
            "source_revision":self.rev,
            "python_executable":sys.executable,
            "sqlite_sha256":sha256(b"sqlite-test").hexdigest(),
            "manifest_sha256":sha256(b"manifest-test").hexdigest(),
        }
        self.registry=home/"project-indexes.json"
        self.registry.write_text(json.dumps({
            "schema_version":1,"projects":{"lab-rag":self.row}
        }),encoding="utf-8")

    def open_catalog(self):
        stack=[
            patch.object(catalog,"catalog_path",return_value=self.registry),
            patch.object(catalog,"_workspace_root",return_value=self.workspace),
        ]
        for item in stack:
            item.start()
            self.addCleanup(item.stop)

    def test_fingerprinted_candidate_is_accepted(self):
        self.open_catalog()
        result=catalog.resolve_isolated_project("lab-rag")
        self.assertEqual(result.project_id,"lab-rag")
        self.assertEqual(result.generation,"revision")
        self.assertEqual(result.sqlite,self.stage/"rag_index.sqlite3")

    def test_missing_and_disabled_registration_preserves_legacy(self):
        self.open_catalog()
        self.assertIsNone(catalog.resolve_isolated_project("codebridge"))
        self.row["enabled"]=False
        self.registry.write_text(json.dumps({
            "schema_version":1,"projects":{"lab-rag":self.row}
        }),encoding="utf-8")
        self.assertIsNone(catalog.resolve_isolated_project("lab-rag"))
        self.assertEqual(catalog.list_isolated_project_indexes()[0]["state"],"DISABLED")

    def test_candidate_tampering_fails_closed(self):
        self.open_catalog()
        (self.stage/"rag_index.sqlite3").write_bytes(b"tampered!")
        with self.assertRaises(catalog.IsolatedProjectUnavailable):
            catalog.resolve_isolated_project("lab-rag")

    def test_source_escape_fails_closed(self):
        self.open_catalog()
        self.row["source_directory"]=str(self.workspace.parent)
        self.registry.write_text(json.dumps({
            "schema_version":1,"projects":{"lab-rag":self.row}
        }),encoding="utf-8")
        with self.assertRaises(catalog.IsolatedProjectUnavailable):
            catalog.resolve_isolated_project("lab-rag")

    def test_incomplete_index_is_rejected(self):
        self.open_catalog()
        progress=self.stage/"progress.json"
        row=json.loads(progress.read_text(encoding="utf-8"))
        row["total_vectors_done"]=2
        progress.write_text(json.dumps(row),encoding="utf-8")
        with self.assertRaises(catalog.IsolatedProjectUnavailable):
            catalog.resolve_isolated_project("lab-rag")


class IsolatedProjectBridgeTests(unittest.TestCase):
    def test_pinned_source_verification_preserves_crlf_bytes(self):
        import hashlib
        from rag.runtime.isolated_project_search import _verify_pinned_source
        with tempfile.TemporaryDirectory() as td:
            source=Path(td)/"README.md"
            original=b"one\\r\\ntwo\\r\\n".replace(b"\\r",b"\r").replace(b"\\n",b"\n")
            source.write_bytes(original)
            expected=hashlib.sha256(original).hexdigest()
            fresh=_verify_pinned_source(Path(td),"README.md",expected)
            self.assertEqual(fresh["status"],"FRESH")
            source.write_bytes(b"changed")
            changed=_verify_pinned_source(Path(td),"README.md",expected)
            self.assertEqual(changed["status"],"STALE")

    def test_project_search_routes_only_registered_project(self):
        from rag.runtime import isolated_project_search
        with (
            patch.object(catalog,"resolve_isolated_project",return_value=object()),
            patch.object(isolated_project_search,"search_isolated_project",
                         return_value={"results":[{"chunk_id":"test"}]}) as search,
        ):
            result=rag_bridge.search_rag_context(
                query="where is RAG?",project_id="lab-rag",top_k=3,
            )
        self.assertEqual(result["results"][0]["chunk_id"],"test")
        search.assert_called_once()

    def test_project_context_is_pinned(self):
        from rag.runtime import isolated_project_search
        with (
            patch.object(catalog,"resolve_isolated_project",return_value=object()),
            patch.object(isolated_project_search,"get_isolated_project_context",
                         return_value={"items":[{"chunk_id":"test"}]}) as context,
        ):
            result=rag_bridge.get_rag_context(
                project_id="lab-rag",chunk_ids=["test"],
            )
        self.assertEqual(result["items"][0]["chunk_id"],"test")
        context.assert_called_once()

    def test_codebridge_does_not_route_to_an_isolated_project(self):
        from rag.runtime import isolated_project_search
        with (
            patch.object(isolated_project_search,"search_isolated_project") as wrong,
            patch.object(catalog,"resolve_isolated_project") as registry,
            patch("rag.runtime.search_service.search_context") as existing,
            patch.object(rag_bridge,"_v1_legacy_index_missing",return_value=True),
            patch.object(rag_bridge,"_configure_v1_semantic_for_project"),
        ):
            existing.return_value.to_dict.return_value={"legacy":True}
            self.assertEqual(rag_bridge.search_rag_context(query="code",project_id="codebridge"),{"legacy":True})
            wrong.assert_not_called()
            registry.assert_not_called()


if __name__=="__main__":
    unittest.main()
