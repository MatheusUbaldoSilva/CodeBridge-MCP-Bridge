"""RAG-DEL-01.04-DL: existing GUI documents operation uses pinned public helper.

Only synthetic sqlite fixtures and mocked bridge; never installed RAG indexes.
"""
import os
import sqlite3
import sys
import types
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch, Mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app_rewrite"))

from PySide6.QtWidgets import QApplication
import rag_panel
from rag.runtime.production_generation_lock import ProductionGenerationBusy


class PinnedGuiDocumentTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.private = self.root / "private_index.sqlite3"
        with closing(sqlite3.connect(self.private)) as cn:
            cn.execute("CREATE TABLE rag_documents (project_id TEXT,path TEXT,source_type TEXT)")
            cn.executemany(
                "INSERT INTO rag_documents VALUES (?,?,?)",
                [
                    ("private-demo", "game/sword.cpp", "CODE"),
                    ("private-demo", "game/sword.cpp", "CODE"),
                    ("codebridge", "public-do-not-expose", "TEXT"),
                ],
            )
            cn.commit()
        # _rag_operation imports author_mcp.rag_bridge for unrelated operations,
        # even for documents. Stub it without importing or calling a live bridge.
        stub = types.ModuleType("author_mcp.rag_bridge")
        patcher = patch.dict(sys.modules, {"author_mcp.rag_bridge": stub})
        patcher.start()
        self.addCleanup(patcher.stop)

    def request(self, name):
        return rag_panel._rag_operation("documents", {"project": name})

    def test_public_route_calls_pinned_inventory_and_keeps_gui_shape(self):
        rows = [{"path":"README.md","count":2,"type":"TEXT"}]
        with patch(
            "rag.runtime.knowledge_deletion_public_inventory_read."
            "read_pinned_public_document_inventory",
            return_value={
                "state":"PUBLIC_DOCUMENT_INVENTORY_READ_ONLY",
                "documents":rows, "generation":"testgen",
                "activation_authorized":False,
            },
        ) as inventory, patch(
            "rag.runtime.status.resolve_rag_sqlite_path",
            side_effect=AssertionError("public legacy resolver must not run"),
        ):
            got = self.request("codebridge")
        self.assertEqual(got, rows)
        self.assertIsInstance(got, list)
        inventory.assert_called_once_with(project_id="codebridge")

    def test_public_reader_busy_does_not_fallback_to_legacy_index(self):
        with patch(
            "rag.runtime.knowledge_deletion_public_inventory_read."
            "read_pinned_public_document_inventory",
            side_effect=ProductionGenerationBusy("cutover busy"),
        ) as inventory, patch(
            "rag.runtime.status.resolve_rag_sqlite_path",
            side_effect=AssertionError("unsafe fallback"),
        ):
            with self.assertRaises(ProductionGenerationBusy):
                self.request("codebridge")
            inventory.assert_called_once()

    def test_private_route_remains_isolated_from_public_helper(self):
        private = types.SimpleNamespace(sqlite=self.private)
        with patch(
            "rag.runtime.isolated_project_index.resolve_isolated_project",
            return_value=private,
        ) as isolated, patch(
            "rag.runtime.knowledge_deletion_public_inventory_read."
            "read_pinned_public_document_inventory",
            side_effect=AssertionError("private never reads public"),
        ):
            result = self.request("private-demo")
        isolated.assert_called_once_with("private-demo")
        self.assertEqual(
            result, [{"path":"game/sword.cpp","count":2,"type":"CODE"}],
        )

    def test_missing_private_project_never_exposes_public_inventory(self):
        with patch(
            "rag.runtime.isolated_project_index.resolve_isolated_project",
            return_value=None,
        ) as isolated, patch(
            "rag.runtime.knowledge_deletion_public_inventory_read."
            "read_pinned_public_document_inventory",
            side_effect=AssertionError("never enumerate public"),
        ):
            self.assertEqual(self.request("missing-private"), [])
        isolated.assert_called_once_with("missing-private")

    def test_gui_consumes_same_shape_and_public_delete_remains_disabled(self):
        with patch.object(rag_panel.RagPanel, "refresh", return_value=None):
            panel = rag_panel.RagPanel()
        try:
            panel.project_id = "codebridge"
            panel._complete("documents", [
                {"path":"README.md","count":2,"type":"TEXT"},
            ], "")
            self.assertEqual(panel.files.count(),1)
            self.assertEqual(panel.files.item(0).text(),"README.md")
            self.assertFalse(
                panel.deletion_review_panel.selector.preview_button.isEnabled()
            )
        finally:
            panel.close()
    def test_public_gui_route_uses_actual_scratch_versioned_generation(self):
        root = self.root / "CodeBridge" / "rag"
        generation = "v1_delta_1234567890abcd"
        folder = root / "generations" / generation
        folder.mkdir(parents=True)
        dbfile = folder / "rag_index.sqlite3"
        with closing(sqlite3.connect(dbfile)) as con:
            con.execute(
                "CREATE TABLE rag_documents "
                "(project_id TEXT,path TEXT,source_type TEXT)"
            )
            con.executemany("INSERT INTO rag_documents VALUES (?,?,?)", [
                ("codebridge", "docs/official.md", "DOCUMENTATION"),
                ("codebridge", "src/main.py", "CODE"),
                ("private-demo", "private/secret.py", "CODE"),
            ])
            con.commit()
        (folder / "qdrant").mkdir()
        (folder / "rag-index-manifest.json").write_text(
            "{}", encoding="utf-8",
        )
        (root / "active-generation.json").write_text(
            __import__("json").dumps({
                "schema_version":1, "generation":generation,
            }), encoding="utf-8",
        )
        with (
            patch("rag.runtime.production_generation_lock.resolve_rag_sqlite_path",
                  return_value=root / "rag_index.sqlite3"),
            patch("rag.runtime.production_generation_read.resolve_rag_sqlite_path",
                  return_value=root / "rag_index.sqlite3"),
        ):
            rows = self.request("codebridge")
        self.assertEqual(rows, [
            {"path":"docs/official.md","count":1,"type":"DOCUMENTATION"},
            {"path":"src/main.py","count":1,"type":"CODE"},
        ])
        self.assertTrue((root / "production-generation.lock").exists())