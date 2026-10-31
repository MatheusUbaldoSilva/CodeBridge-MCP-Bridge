"""F-7: loaded bytecode must match compiled file, not merely its name."""
import os,sys,types
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"app_rewrite"))
import rag_panel
from rag.runtime import knowledge_deletion_public_inventory_read as reader
from rag.runtime.knowledge_deletion_gui_loaded_code_match_dev import match_loaded_top_level_function_dev as match

class SourceCodeIdentityTests(TestCase):
    def test_rag_panel_loaded_matches_disk(self):
        proof=match(rag_panel._rag_operation,
                    ROOT/"app_rewrite"/"rag_panel.py","_rag_operation")
        self.assertTrue(proof["loaded_code_matches_disk"])
        self.assertFalse(proof["installed_gui_attested"])
    def test_reader_loaded_matches_disk(self):
        proof=match(reader.read_pinned_public_document_inventory,
                    ROOT/"rag"/"runtime"/"knowledge_deletion_public_inventory_read.py",
                    "read_pinned_public_document_inventory")
        self.assertTrue(proof["loaded_code_matches_disk"])
    def test_fake_loaded_code_fails_even_with_same_name(self):
        code=compile("def _rag_operation(x):\n    return 1\n",
                     str(ROOT/"app_rewrite"/"rag_panel.py"),"exec")
        code=next(c for c in code.co_consts if isinstance(c,types.CodeType))
        fake=types.FunctionType(code,{})
        self.assertFalse(match(fake,ROOT/"app_rewrite"/"rag_panel.py",
                               "_rag_operation")["loaded_code_matches_disk"])
    def test_wrong_name_fails_closed(self):
        self.assertFalse(match(rag_panel._rag_operation,ROOT/"app_rewrite"/"rag_panel.py",
                               "refresh")["loaded_code_matches_disk"])
    def test_wrong_path_fails_closed(self):
        self.assertFalse(match(rag_panel._rag_operation,ROOT/"rag"/"runtime"/
                  "knowledge_deletion_public_inventory_read.py",
                  "_rag_operation")["loaded_code_matches_disk"])
    def test_missing_path_fails_closed(self):
        self.assertFalse(match(reader.read_pinned_public_document_inventory,
                               ROOT/"missing.py","read_pinned_public_document_inventory")
                         ["loaded_code_matches_disk"])
    def test_invalid_arguments(self):
        for item in ("relative.py",Path("relative.py")):
            with self.subTest(item=item),self.assertRaises(ValueError):
                match(rag_panel._rag_operation,item,"_rag_operation")
    def test_no_source_execution(self):
        with patch.object(rag_panel,"_rag_operation",
                          side_effect=AssertionError("never execute")):
            proof=match(rag_panel._rag_operation,ROOT/"app_rewrite"/"rag_panel.py",
                        "_rag_operation")
        self.assertFalse(proof["activation_authorized"])


class GuiWitnessAdversarialTests(TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app=QApplication.instance() or QApplication([])

    def setUp(self):
        from unittest.mock import patch
        self.refresh_patch=patch.object(rag_panel.RagPanel,"refresh",return_value=None)
        self.refresh_patch.start()
        self.addCleanup(self.refresh_patch.stop)
        self.panel=rag_panel.RagPanel()
        self.addCleanup(self.panel.close)

    def test_gui_lab_receipt_includes_bytecode_match(self):
        from rag.runtime.knowledge_deletion_gui_loaded_observer_dev import (
            inspect_gui_loaded_reader_dev,
        )
        proof=inspect_gui_loaded_reader_dev(self.panel,ROOT)
        self.assertTrue(proof["checks"]["gui_route_loaded_bytecode_matches_dev_file"])
        self.assertTrue(proof["checks"]["reader_loaded_bytecode_matches_dev_file"])
        self.assertTrue(proof["lab_inprocess_observed"])
        self.assertFalse(proof["installed_gui_trusted_channel_attested"])

    def test_forged_route_names_fail_closed_even_when_old_names_pass(self):
        from rag.runtime.knowledge_deletion_gui_loaded_observer_dev import (
            inspect_gui_loaded_reader_dev,
        )
        raw=(
            "def _rag_operation(x, y):\n"
            "    if x == 'documents':\n"
            "        return read_pinned_public_document_inventory\n"
            "    return []\n"
        )
        code=compile(raw,str(ROOT/"app_rewrite"/"rag_panel.py"),"exec")
        forged=types.FunctionType(
            next(c for c in code.co_consts if isinstance(c,types.CodeType)),{})
        with patch.object(rag_panel,"_rag_operation",forged):
            proof=inspect_gui_loaded_reader_dev(self.panel,ROOT)
        self.assertTrue(proof["checks"]["public_documents_route_present_in_loaded_code"])
        self.assertFalse(proof["checks"]["gui_route_loaded_bytecode_matches_dev_file"])
        self.assertFalse(proof["lab_inprocess_observed"])
