"""RAG-017 installed MCP bridge safety invariants (no production activation)."""
import inspect
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"author_mcp"))
import rag_bridge
from rag.runtime.production_search import search_persistent_semantic

class InstalledBridgeSafetyTests(unittest.TestCase):
 def setUp(self):
  self.previous=(rag_bridge._RAG_INDEX_EXECUTOR,rag_bridge._RAG_SEARCH_EXECUTOR)
  rag_bridge.register_rag_index_executor(None)
  rag_bridge.register_rag_search_executor(None)
 def tearDown(self):
  rag_bridge.register_rag_index_executor(self.previous[0])
  rag_bridge.register_rag_search_executor(self.previous[1])
 def test_experimental_flags_default_off(self):
  params=inspect.signature(search_persistent_semantic).parameters
  self.assertIs(params["experimental_cross_route"].default,False)
  self.assertIs(params["experimental_resident_models"].default,False)
 def test_mcp_search_does_not_activate_semantic_executor(self):
  with patch("rag.runtime.search_service.search_context") as search:
   search.return_value.to_dict.return_value={"status":"TEST"}
   self.assertEqual(rag_bridge.search_rag_context(query="code",project_id="codebridge"),{"status":"TEST"})
   self.assertIsNone(search.call_args.kwargs["semantic_executor"])
   self.assertIsNone(rag_bridge._RAG_SEARCH_EXECUTOR)
 def test_explicit_registration_keeps_experimental_parameters_off(self):
  result=rag_bridge.configure_production_rag_executors(semantic_search=True)
  self.assertTrue(result["semantic_search_registered"])
  executor=rag_bridge._RAG_SEARCH_EXECUTOR
  self.assertIs(executor,search_persistent_semantic)
  self.assertIs(inspect.signature(executor).parameters["experimental_cross_route"].default,False)
 def test_index_only_registration_cannot_enable_semantic(self):
  result=rag_bridge.configure_production_rag_executors(staged_index=True)
  self.assertTrue(result["staged_index_registered"])
  self.assertFalse(result["semantic_search_registered"])
