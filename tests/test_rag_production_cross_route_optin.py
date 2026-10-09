import unittest
from unittest.mock import patch
from rag.contracts import SearchQuery
from rag.runtime.production_search import search_persistent_semantic
from rag.runtime.query_classifier import QueryRoute

class ProductionCrossRouteTests(unittest.TestCase):
 def test_opt_in_not_default(self):
  self.assertFalse(search_persistent_semantic.__kwdefaults__["experimental_cross_route"])
 def test_lexical_only_remains_rejected(self):
  with self.assertRaises(ValueError):
   search_persistent_semantic(SearchQuery(query="test",project_id="p"),QueryRoute.LEXICAL_ONLY,experimental_cross_route=True)
 def test_empty_index_fails_closed(self):
  from types import SimpleNamespace
  with patch.dict(search_persistent_semantic.__globals__,{"build_rag_status":lambda:SimpleNamespace(index={"state":"STALE"})}):
   with self.assertRaises(Exception):
    search_persistent_semantic(SearchQuery(query="test",project_id="p"),QueryRoute.TEXT,experimental_cross_route=True)
