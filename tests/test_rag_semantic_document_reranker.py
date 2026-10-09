import unittest
from rag.contracts import SearchResult,SourceMetadata,SourceType
from rag.ranking.semantic_document_reranker import rerank_documents
def hit(project,path,chunk,rank):
 return SearchResult(chunk_id=chunk,document_id="doc:"+path,content="content "+chunk,metadata=SourceMetadata(project_id=project,source_type=SourceType.CODE,path=path),score=0.75,rank=rank,retrieval_modes=("VECTOR",),stale=False)
class RerankTests(unittest.TestCase):
 def test_document_fusion(self):
  result=rerank_documents(((hit("p","a.py","a1",1),hit("p","b.py","b1",2)),(hit("p","b.py","b2",1),hit("p","b.py","b3",2))),top_k=2)
  self.assertEqual(len(result),2)
  self.assertEqual(result[0].metadata.path,"b.py")
 def test_namespace(self):
  with self.assertRaises(ValueError):
   rerank_documents(((hit("a","a.py","a",1),),(hit("b","b.py","b",1),)))
 def test_bad_limits(self):
  with self.assertRaises(ValueError):rerank_documents((),top_k=0)
 def test_reproducible(self):
  data=((hit("p","a.py","a",1),),)
  self.assertEqual(rerank_documents(data),rerank_documents(data))
