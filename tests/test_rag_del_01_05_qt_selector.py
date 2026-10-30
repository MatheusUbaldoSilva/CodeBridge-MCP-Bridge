"""Qt selection-only tests for deletion preview; no real index writes."""
import os
import sys
import unittest
from pathlib import Path
os.environ["QT_QPA_PLATFORM"]="offscreen"
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"app_rewrite"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from rag_deletion_selector import KnowledgeRemovalSelector

class KnowledgeRemovalSelectorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])

    def setUp(self):
        self.widget=KnowledgeRemovalSelector()
        self.widget.set_files(["game/src/pvp.cpp","common/types.h","game/src/char.cpp"])
        self.addCleanup(self.widget.close)

    def test_selection_starts_empty(self):
        self.assertEqual(self.widget.selected_paths(),[])
        self.assertFalse(self.widget.preview_button.isEnabled())
        self.assertEqual(self.widget.items.count(),3)

    def test_selected_paths_and_signal_are_exact(self):
        emitted=[]
        self.widget.preview_requested.connect(emitted.append)
        self.widget.items.item(0).setCheckState(Qt.CheckState.Checked)
        self.widget.items.item(2).setCheckState(Qt.CheckState.Checked)
        self.assertEqual(len(self.widget.selected_paths()),2)
        self.assertTrue(self.widget.preview_button.isEnabled())
        self.widget.preview_button.click()
        self.assertEqual(emitted,[self.widget.selected_paths()])

    def test_uncheck_disables_preview(self):
        item=self.widget.items.item(1)
        item.setCheckState(Qt.CheckState.Checked)
        item.setCheckState(Qt.CheckState.Unchecked)
        self.assertFalse(self.widget.preview_button.isEnabled())

    def test_inventory_replacement_clears_selection(self):
        self.widget.items.item(0).setCheckState(Qt.CheckState.Checked)
        self.widget.set_files(["other.cpp"])
        self.assertEqual(self.widget.selected_paths(),[])
        self.assertFalse(self.widget.preview_button.isEnabled())

    def test_duplicate_inventory_rejected(self):
        with self.assertRaises(ValueError):
            self.widget.set_files(["x.cpp","x.cpp"])

if __name__=="__main__":
    unittest.main()
