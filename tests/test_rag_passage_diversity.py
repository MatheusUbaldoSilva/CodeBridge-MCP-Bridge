import unittest
from rag.contracts import SearchResult,SourceMetadata,SourceType
from rag.ranking.passage_diversity import select_diverse_passages
def h(cid,text,project="p"):
 return SearchResult(chunk_id=cid,document_id="d",content=text,metadata=SourceMetadata(project_id=project,source_type=SourceType.CODE,path="a.py"),score=.8,rank=1,retrieval_modes=("VECTOR",),stale=False)
class DiversityTests(unittest.TestCase):
 def test_prefers_distinct_evidence(self):
  data=((1.,h("a","alpha beta gamma")),(.9,h("b","alpha beta gamma")),(.8,h("c","different symbols functions")))
  self.assertEqual([x.chunk_id for x in select_diverse_passages(data,2)],["a","c"])
 def test_dedup(self):
  x=h("a","text")
  self.assertEqual(len(select_diverse_passages(((1,x),(.8,x)),3)),1)
 def test_namespace_safety(self):
  with self.assertRaises(ValueError):
   select_diverse_passages(((1,h("a","one")),(1,h("b","two",project="other"))),2)
 def test_limit(self):
  with self.assertRaises(ValueError):select_diverse_passages((),4)
