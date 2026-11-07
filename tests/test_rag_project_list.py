"""Lista de projetos sem o 'codebridge' vazio e selo RAG por projeto."""
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app_rewrite"))
sys.path.insert(0, str(ROOT))
from rag_project_list import visible_projects, status_text, project_counts, SEP

STABLE = {"project_id": "codebridge-stable", "state": "ISOLATED_READ_ONLY",
          "document_count": 969}
EMPTY_MAIN = {"index": {"state": "EMPTY"}, "projects": [],
              "isolated_project_indexes": [STABLE]}


class ProjectListTests(unittest.TestCase):
    def test_empty_main_project_is_hidden(self):
        self.assertEqual(visible_projects(EMPTY_MAIN, ["codebridge-stable"]),
                         ["codebridge-stable"])

    def test_main_project_with_documents_is_shown(self):
        data = dict(EMPTY_MAIN, index={"state": "READY"},
                    projects=[{"project_id": "codebridge", "document_count": 5}])
        self.assertEqual(visible_projects(data, []),
                         ["codebridge", "codebridge-stable"])

    def test_main_project_kept_when_nothing_else(self):
        self.assertEqual(visible_projects({"projects": []}, []), ["codebridge"])
        self.assertEqual(visible_projects(None, []), ["codebridge"])

    def test_registered_empty_projects_stay_visible(self):
        self.assertEqual(visible_projects(EMPTY_MAIN, ["new-world"]),
                         ["codebridge-stable", "new-world"])

    def test_non_ready_isolated_does_not_count(self):
        data = {"isolated_project_indexes": [dict(STABLE, state="BUILDING")]}
        self.assertEqual(project_counts(data), {})

    def test_status_follows_selected_project(self):
        self.assertEqual(status_text(EMPTY_MAIN, "codebridge-stable"),
                         "RAG: ONLINE" + SEP + "codebridge-stable" + SEP + "969 documentos")
        self.assertEqual(status_text(EMPTY_MAIN, "new-world"),
                         "RAG: VAZIO" + SEP + "new-world ainda sem documentos")
        self.assertEqual(status_text(EMPTY_MAIN, "codebridge"),
                         "RAG: VAZIO" + SEP + "codebridge ainda sem documentos")

    def test_status_offline_cases(self):
        self.assertEqual(status_text(None, "codebridge-stable"), "RAG: OFFLINE")
        broken = dict(EMPTY_MAIN, index={"state": "CORRUPT"})
        self.assertEqual(status_text(broken, "codebridge"), "RAG: OFFLINE")
        one = {"index": {"state": "READY"},
               "projects": [{"project_id": "codebridge", "document_count": 1}]}
        self.assertEqual(status_text(one, "codebridge"),
                         "RAG: ONLINE" + SEP + "codebridge" + SEP + "1 documento")


class PanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def make_panel(self):
        from rag_panel import RagPanel
        with patch.object(RagPanel, "_run"):
            return RagPanel()

    def picker_items(self, panel):
        return [panel.project_picker.itemText(i)
                for i in range(panel.project_picker.count())]

    def test_panel_hides_empty_main_and_switches(self):
        panel = self.make_panel()
        with patch("rag_panel.list_projects", return_value=["codebridge-stable"]), \
             patch.object(panel, "_run"):
            panel._complete("status", EMPTY_MAIN, "")
        self.assertEqual(self.picker_items(panel), ["codebridge-stable"])
        self.assertEqual(panel.project_id, "codebridge-stable")
        self.assertTrue(panel.rag_status.text().startswith("RAG: ONLINE"))
        self.assertIn("969 documentos", panel.rag_status.text())
        panel.close()

    def test_panel_status_updates_on_project_change(self):
        panel = self.make_panel()
        with patch("rag_panel.list_projects", return_value=["codebridge-stable", "new-world"]), \
             patch.object(panel, "_run"):
            panel._complete("status", EMPTY_MAIN, "")
            panel.project_picker.setCurrentText("new-world")
        self.assertEqual(panel.project_id, "new-world")
        self.assertTrue(panel.rag_status.text().startswith("RAG: VAZIO"))
        panel._complete("status", {}, "unavailable")
        self.assertEqual(panel.rag_status.text(), "RAG: OFFLINE")
        panel.close()


if __name__ == "__main__":
    unittest.main()