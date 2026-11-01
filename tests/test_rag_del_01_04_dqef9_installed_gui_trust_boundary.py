"""F-9 explicit trust boundary tests: matching lab + process != installed."""
import os,sys
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"app_rewrite"))
import rag_panel
import rag.runtime.knowledge_deletion_public_inventory_read
from PySide6.QtWidgets import QApplication
from rag.runtime.knowledge_deletion_gui_loaded_observer_dev import inspect_gui_loaded_reader_dev
from rag.runtime.knowledge_deletion_gui_boundary_review_dev import review_gui_install_attestation_gap_dev as review
from rag.runtime.knowledge_deletion_gui_process_observer_dev import review_gui_process_topology_dev

def topology():
    launch=str(ROOT.parent/"CodeBridge-Launcher"/"launcher.py")
    return review_gui_process_topology_dev([
        dict(ProcessId=100,ParentProcessId=1,
             CommandLine='"C:/python/pythonw.exe" "'+launch+'"'),
        dict(ProcessId=200,ParentProcessId=100,
             CommandLine='"C:/python/python.exe" "'+
                         str(ROOT/"app_rewrite"/"main.py")+'" --no-elevate'),
        dict(ProcessId=300,ParentProcessId=200,
             CommandLine='"C:/python/python.exe" "'+
                         str(ROOT/"author_mcp"/"mcp_server.py")+'" --host 127.0.0.1 --port 8765'),
    ],ROOT)

class InstalledGuiBoundaryReviewTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])
    def setUp(self):
        with patch.object(rag_panel.RagPanel,"refresh",return_value=None):
            self.gui=rag_panel.RagPanel()
        self.addCleanup(self.gui.close)
        self.lab=inspect_gui_loaded_reader_dev(self.gui,ROOT)
        self.topology=topology()
    def test_both_positive_still_not_installed(self):
        self.assertTrue(self.lab["lab_inprocess_observed"])
        self.assertTrue(self.topology["expected_dev_process_tree_observed"])
        proof=review(self.topology,self.lab)
        self.assertTrue(proof["checks"]["real_gui_process_tree_observed"])
        self.assertTrue(proof["checks"]["offscreen_lab_gui_code_observed"])
        self.assertFalse(proof["installed_gui_attested"])
        self.assertFalse(proof["activation_authorized"])
        self.assertIn("installed_gui_ipc_challenge_response_attested",proof["blockers"])
    def test_untrusted_forced_installed_claim_does_not_advance(self):
        record=self.lab|{"installed_gui_trusted_channel_attested":True}
        self.assertFalse(review(self.topology,record)["checks"]["offscreen_lab_gui_code_observed"])
        self.assertFalse(review(self.topology,record)["installed_gui_attested"])
    def test_unknown_process_topology_blocks(self):
        record=self.topology|{"expected_dev_process_tree_observed":False}
        self.assertFalse(review(record,self.lab)["checks"]["real_gui_process_tree_observed"])
    def test_source_code_mismatch_blocks_lab(self):
        changes=self.lab["checks"]|{"gui_route_loaded_bytecode_matches_dev_file":False}
        record=self.lab|{"checks":changes}
        self.assertFalse(review(self.topology,record)["checks"]["offscreen_lab_gui_code_observed"])
    def test_malformed_objects_rejected(self):
        for x in (None,[],0,"yes"):
            with self.subTest(x=x),self.assertRaises(ValueError):
                review(self.topology,x)
    def test_operational_flag_rejected(self):
        with self.assertRaises(ValueError):
            review(self.topology|{"activation_authorized":True},self.lab)
    def test_only_readonly_evidence_accepted(self):
        with self.assertRaises(ValueError):
            review(self.topology,self.lab|{"read_only":False})
