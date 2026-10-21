import unittest
from rag.runtime.production_supervised_trial import _matches_incremental_scope

class IncrementalSupervisedPolicyTests(unittest.TestCase):
    def setUp(self):
        self.candidate="v1_delta_3ab9c095605b4a"
        self.validation={"documents":211,"chunks":8774,"vectors":8774,"manifest_entries":211}
        self.content={"added_paths":["rag/runtime/incremental_scheduler_gate.py"],
          "modified_paths":["author_mcp/mcp_server.py","author_mcp/rag_bridge.py",
           "rag/runtime/production_index.py","rag/runtime/production_search.py",
           "rag/runtime/status.py"],"removed_paths":[]}
    def test_correct_exact_generation(self):
        self.assertTrue(_matches_incremental_scope(self.candidate,self.validation,self.content))
        self.assertFalse(_matches_incremental_scope("v1_delta_bebee8b8a49943",self.validation,self.content))
    def test_wrong_counts(self):
        self.validation["chunks"]=8763
        self.assertFalse(_matches_incremental_scope(self.candidate,self.validation,self.content))
    def test_wrong_source(self):
        self.content["added_paths"]=["other.py"]
        self.assertFalse(_matches_incremental_scope(self.candidate,self.validation,self.content))
    def test_removed_source(self):
        self.content["removed_paths"]=["docs/important.md"]
        self.assertFalse(_matches_incremental_scope(self.candidate,self.validation,self.content))
