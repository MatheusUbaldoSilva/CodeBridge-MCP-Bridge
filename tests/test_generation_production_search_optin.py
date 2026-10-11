import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rag.contracts import SearchQuery
from rag.runtime.query_classifier import QueryRoute
from rag.runtime.production_search import search_persistent_semantic
from rag.runtime.generation_activation import activate_test_generation
from test_generation_read_session import create_generation

class GenerationSearchOptInTests(unittest.TestCase):
    def test_optin_pins_sqlite_and_qdrant_during_search(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "codebridge-rag-generation-test"
            root.mkdir()
            create_generation(root, "one")
            create_generation(root, "two")
            activate_test_generation(root, "one")
            seen = []
            def lexical(connection, query):
                seen.append(connection.execute("SELECT generation FROM marker").fetchone()[0])
                activate_test_generation(root, "two")
                return []
            def vector_open(path):
                seen.append(path.parent.name)
                return object()
            with patch("rag.runtime.production_search.build_rag_status") as status, \
                 patch("rag.runtime.production_search._embed_text", return_value=[0.1]), \
                 patch("rag.runtime.production_search.search_lexical_ranked", side_effect=lexical), \
                 patch("rag.runtime.production_search.open_qdrant_local", side_effect=vector_open), \
                 patch("rag.runtime.production_search.close_qdrant_local"), \
                 patch("rag.runtime.production_search.search_text_vector", return_value=[]):
                search_persistent_semantic(
                    SearchQuery(query="test", project_id="demo", top_k=3),
                    QueryRoute.TEXT, experimental_generation_root=root)
                status.assert_not_called()
            self.assertEqual(seen, ["one", "one"])

if __name__ == "__main__":
    unittest.main()
