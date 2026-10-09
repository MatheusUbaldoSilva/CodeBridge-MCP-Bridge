import sqlite3
import unittest
from unittest.mock import patch
from rag.contracts import SearchQuery,SearchResult,SourceMetadata,SourceType
from rag.retrieval.cross_route import cross_route_document_rank

def hit(project,path,chunk,rank=1):
 return SearchResult(chunk_id=chunk,document_id="doc:"+path,content="text",
     metadata=SourceMetadata(project_id=project,source_type=SourceType.CODE,path=path),
     score=.5,rank=rank,retrieval_modes=("VECTOR",),stale=False)

class CrossRouteTests(unittest.TestCase):
 def test_code_evidence_rescues_text_route(self):
  conn=sqlite3.connect(":memory:")
  try:
   query=SearchQuery(query="how does git state work",project_id="p",top_k=10)
   original=((hit("p","docs/a.md","a"),),)
   with patch.dict(cross_route_document_rank.__globals__,{"search_code_vector":lambda *args:(hit("p","rag/sources/git_state.py","b"),)}):
    ranked=cross_route_document_rank(conn,object(),query,original,[0.0],top_k=2)
   self.assertEqual({r.metadata.path for r in ranked},{"docs/a.md","rag/sources/git_state.py"})
  finally:conn.close()
 def test_project_mismatch_fails_closed(self):
  conn=sqlite3.connect(":memory:")
  try:
   query=SearchQuery(query="code",project_id="p",top_k=5)
   with self.assertRaises(ValueError):
    cross_route_document_rank(conn,object(),query,((hit("other","a.py","1"),),),[0.0])
  finally:conn.close()
 def test_wrong_vector_project_fails_closed(self):
  conn=sqlite3.connect(":memory:")
  try:
   query=SearchQuery(query="code",project_id="p",top_k=5)
   with patch.dict(cross_route_document_rank.__globals__,{"search_code_vector":lambda *args:(hit("other","x.py","x"),)}):
    with self.assertRaises(ValueError):
     cross_route_document_rank(conn,object(),query,(),[0.0])
  finally:conn.close()
