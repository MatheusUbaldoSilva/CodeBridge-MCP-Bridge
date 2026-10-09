"""RAG-017-G explicit registration preserves existing MCP fallback defaults."""
import sys
import unittest
from pathlib import Path
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/"author_mcp"))
import rag_bridge

class RegistrationTests(unittest.TestCase):
    def setUp(self):
        self.index=rag_bridge._RAG_INDEX_EXECUTOR
        self.search=rag_bridge._RAG_SEARCH_EXECUTOR
        rag_bridge.register_rag_index_executor(None)
        rag_bridge.register_rag_search_executor(None)
    def tearDown(self):
        rag_bridge.register_rag_index_executor(self.index)
        rag_bridge.register_rag_search_executor(self.search)
    def test_unconfigured_default_remains_unregistered(self):
        self.assertIsNone(rag_bridge._RAG_INDEX_EXECUTOR)
        self.assertIsNone(rag_bridge._RAG_SEARCH_EXECUTOR)
    def test_explicit_activation_wires_both_real_adapters(self):
        result=rag_bridge.configure_production_rag_executors(staged_index=True,semantic_search=True)
        self.assertTrue(result["staged_index_registered"])
        self.assertTrue(result["semantic_search_registered"])
        self.assertEqual(rag_bridge._RAG_INDEX_EXECUTOR.__name__,"build_staged_index")
        self.assertEqual(rag_bridge._RAG_SEARCH_EXECUTOR.__name__,"search_persistent_semantic")
    def test_registering_one_does_not_activate_other(self):
        result=rag_bridge.configure_production_rag_executors(staged_index=True)
        self.assertTrue(result["staged_index_registered"])
        self.assertFalse(result["semantic_search_registered"])
