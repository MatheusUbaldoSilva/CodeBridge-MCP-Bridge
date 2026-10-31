"""DQ-E-F-6 Qt offscreen local-process reader observer regression."""
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch
import os,sys

os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"app_rewrite"))
from PySide6.QtWidgets import QApplication
import rag_panel
import rag.runtime.knowledge_deletion_public_inventory_read as pinned
from rag.runtime.knowledge_deletion_gui_loaded_observer_dev import inspect_gui_loaded_reader_dev as inspect

class GuiLoadedReaderLabTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])
    def setUp(self):
        patcher=patch.object(rag_panel.RagPanel,"refresh",return_value=None)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.panel=rag_panel.RagPanel()
        self.addCleanup(self.panel.close)
    def test_inprocess_panel_and_reader_observed_without_authority(self):
        result=inspect(self.panel,ROOT)
        self.assertEqual(result["state"],"DEV_GUI_INPROCESS_READER_OBSERVED")
        self.assertTrue(all(result["checks"].values()))
        self.assertEqual(len(result["code_receipt_sha256"]),64)
        self.assertFalse(result["installed_gui_trusted_channel_attested"])
        self.assertFalse(result["gui_runtime_attested_for_operational_deletion"])
        self.assertFalse(result["activation_authorized"])
    def test_wrong_dev_root_not_attested(self):
        r=inspect(self.panel,Path("C:/dev/other"))
        self.assertFalse(r["lab_inprocess_observed"])
    def test_unloaded_helper_not_attested(self):
        with patch.dict(sys.modules,{"rag.runtime.knowledge_deletion_public_inventory_read":None}):
            result=inspect(self.panel,ROOT)
        self.assertFalse(result["checks"]["pinned_reader_module_loaded_from_dev_source"])
        self.assertFalse(result["lab_inprocess_observed"])
    def test_wrong_panel_type_not_attested(self):
        result=inspect(object(),ROOT)
        self.assertFalse(result["lab_inprocess_observed"])
        self.assertFalse(result["activation_authorized"])
    def test_relative_path_rejected(self):
        with self.assertRaises(ValueError):
            inspect(self.panel,Path("relative"))
    def test_no_import_or_reader_execution(self):
        with patch.object(pinned,"production_generation_read",
                          side_effect=AssertionError("observer must never run reader")):
            result=inspect(self.panel,ROOT)
        self.assertTrue(result["lab_inprocess_observed"])
