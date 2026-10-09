"""RAG-017-B general lexical expansion and scope regression."""
import unittest
from rag.contracts import SearchQuery
from rag.index.sqlite_schema import connect_rag_index
from rag.index.fts5 import initialize_fts5
from rag.index.lexical_ranking import search_lexical_ranked, _normalized_fallback_match
from tests.test_rag_lexical_ranking import insert_document,insert_chunk

class LexicalExpansionTests(unittest.TestCase):
    def setUp(self):
        self.db=connect_rag_index(":memory:")
        self.addCleanup(self.db.close)
        for did,pid in (("doc-a","project-a"),("doc-b","project-b")):
            insert_document(self.db,did,project_id=pid)
        insert_chunk(self.db,chunk_id="a",document_id="doc-a",project_id="project-a",content="A deterministic retrieval classifier handles text routing",path="rag/query.py")
        insert_chunk(self.db,chunk_id="b",document_id="doc-b",project_id="project-b",content="A deterministic retrieval classifier handles text routing",path="hidden/project-b.py")
        self.db.commit()
        initialize_fts5(self.db)
    def search(self,query,project_id="project-a"):
        return search_lexical_ranked(self.db,SearchQuery(query=query,project_id=project_id,top_k=10))
    def test_phrase_miss_recovers_by_general_terms(self):
        self.assertEqual([x.chunk_id for x in self.search("Where is deterministic retrieval classifier?")],["a"])
    def test_cross_project_isolation_on_fallback(self):
        self.assertEqual([x.chunk_id for x in self.search("where is deterministic classifier retrieval?")],["a"])
    def test_all_operator_input_remains_literal(self):
        self.assertIsNotNone(_normalized_fallback_match('classifier" OR secret*'))
        self.assertEqual([x.chunk_id for x in self.search('where is retrieval OR secret')],["a"])
    def test_path_filter_still_restricts(self):
        q=SearchQuery(query="where is deterministic classifier",project_id="project-a",top_k=10,path_filter="nonexistent")
        self.assertEqual(search_lexical_ranked(self.db,q),())
    def test_stopword_only_does_not_form_empty_fts(self):
        self.assertIsNone(_normalized_fallback_match("the and for"))

if __name__=="__main__":
    unittest.main()
