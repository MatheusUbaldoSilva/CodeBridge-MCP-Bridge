import unittest
from unittest.mock import patch
from pathlib import Path
from tempfile import TemporaryDirectory
from rag.contracts import SearchQuery
from rag.runtime.query_classifier import QueryRoute
from rag.runtime.production_search import search_persistent_semantic

class PipelineTest(unittest.TestCase):
    def test_code_route_isolates_model(self):
        with TemporaryDirectory() as td:
            db=Path(td)/"idx.db"; db.touch()
            path=Path(td)/"vector"; path.mkdir()
            query=SearchQuery(query="retriever", project_id="demo", top_k=5)
            with patch("rag.runtime.production_search.build_rag_status") as st, patch("rag.runtime.production_search.resolve_rag_sqlite_path",return_value=db), patch("rag.runtime.production_search.resolve_qdrant_local_path",return_value=path), patch("rag.runtime.production_search._embed_code",return_value=(0.1,)) as code, patch("rag.runtime.production_search._embed_text") as text, patch("rag.runtime.production_search.open_qdrant_local") as v, patch("rag.runtime.production_search.close_qdrant_local") as close, patch("rag.runtime.production_search.search_lexical_ranked",return_value=()), patch("rag.runtime.production_search.search_code_vector",return_value=()) as search:
                st.return_value.index={"state":"READY"}
                result=search_persistent_semantic(query,QueryRoute.CODE)
                self.assertEqual(result,())
                code.assert_called_once()
                text.assert_not_called()
                search.assert_called_once()
                close.assert_called_once_with(v.return_value)
