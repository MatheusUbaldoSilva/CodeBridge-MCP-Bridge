"""RAG-DEL-01.05: mounted preview-only UI, no destructive command."""
import os,sys
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"app_rewrite"))
from PySide6.QtWidgets import QApplication
import rag_panel

class MountedPreviewTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])
    def setUp(self):
        self.refresh=patch.object(rag_panel.RagPanel,"refresh",lambda self:None)
        self.refresh.start()
        self.addCleanup(self.refresh.stop)
        self.panel=rag_panel.RagPanel()
        self.addCleanup(self.panel.close)
    def test_private_document_inventory_mounted(self):
        self.panel.project_id="demo"
        self.panel._complete("documents",[
            {"path":"game/a.cpp","count":1,"type":"CODE"},
            {"path":"game/b.cpp","count":1,"type":"CODE"}],"")
        selector=self.panel.deletion_review_panel.selector
        self.assertEqual(selector.items.count(),2)
        self.assertEqual(selector.selected_paths(),[])
        self.assertFalse(selector.preview_button.isEnabled())
    def test_public_inventory_not_selectable(self):
        self.panel.project_id="codebridge"
        self.panel._complete("documents",[{"path":"private.txt","count":1,"type":"TEXT"}],"")
        self.assertEqual(self.panel.deletion_review_panel.selector.items.count(),0)
    def test_refresh_clears_prior_selection(self):
        self.panel.project_id="demo"
        self.panel._complete("documents",[{"path":"game/a.cpp","count":1,"type":"CODE"}],"")
        self.panel.deletion_review_panel.selector.items.item(0).setCheckState(
            __import__("PySide6.QtCore",fromlist=["Qt"]).Qt.CheckState.Checked)
        self.panel._complete("documents",[],"")
        self.assertFalse(self.panel.deletion_review_panel.selector.preview_button.isEnabled())
        self.assertEqual(self.panel.deletion_review_panel.selector.selected_paths(),[])
