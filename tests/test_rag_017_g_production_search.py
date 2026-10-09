import unittest
from unittest.mock import patch
from rag.contracts import SearchQuery
from rag.runtime.query_classifier import QueryRoute
from rag.runtime.production_search import search_persistent_semantic, ProductionSearchUnavailable

class ProductionSearchTests(unittest.TestCase):
    def setUp(self):
        self.query=SearchQuery(query="code retriever",project_id="demo",top_k=5)
    def test_lexical_route_rejected(self):
        with self.assertRaises(ValueError):
            search_persistent_semantic(self.query,QueryRoute.LEXICAL_ONLY)
    def test_no_index_fails_closed_without_loading_model(self):
        with patch("rag.runtime.production_search.build_rag_status") as status:
            with patch("rag.runtime.production_search._embed_text") as embedding:
                status.return_value.index={"state":"EMPTY"}
                with self.assertRaises(ProductionSearchUnavailable):
                    search_persistent_semantic(self.query,QueryRoute.TEXT)
                embedding.assert_not_called()
    def test_stale_index_fails_closed(self):
        with patch("rag.runtime.production_search.build_rag_status") as status:
            status.return_value.index={"state":"STALE"}
            with self.assertRaises(ProductionSearchUnavailable):
                search_persistent_semantic(self.query,QueryRoute.HYBRID)
    def test_bad_route_rejected(self):
        with self.assertRaises(ValueError):
            search_persistent_semantic(self.query,"TEXT")
