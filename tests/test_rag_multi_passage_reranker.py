"""Contract tests for bounded multi-passage semantic ranking."""
import unittest
from unittest.mock import patch
from rag.contracts import SearchResult,SourceMetadata,SourceType
from rag.ranking.multi_passage_reranker import rerank_multi_passage

def hit(project,path,chunk,rank):
 return SearchResult(chunk_id=chunk,document_id="doc:"+path,content="text "+chunk,
   metadata=SourceMetadata(project_id=project,source_type=SourceType.CODE,path=path),
   score=0.5,rank=rank,retrieval_modes=("VECTOR",),stale=False)

class MultiPassageContractTests(unittest.TestCase):
 def test_aggregate_multiple_chunks_same_document(self):
  a=hit("p","a.py","a1",1)
  b=hit("p","a.py","a2",2)
  c=hit("p","b.py","b1",3)
  def model(query,passages,**kw):
   self.assertEqual(len(passages),3)
   self.assertEqual({x.metadata.path for x in passages},{"a.py","b.py"})
   scores={"a1":2.0,"a2":1.0,"b1":1.5}
   return tuple(__import__("dataclasses").replace(x,score=scores[x.chunk_id],rank=i+1)
                for i,x in enumerate(passages))
  with patch.dict(rerank_multi_passage.__globals__,{"cross_encoder_rerank":model}):
   results=rerank_multi_passage("query",((a,b,c),),top_k=2)
  self.assertEqual([x.metadata.path for x in results],["a.py","b.py"])
  self.assertEqual([x.rank for x in results],[1,2])
 def test_deduplicates_retrieved_chunks_before_model(self):
  a=hit("p","a.py","x",1)
  calls=[]
  def model(*args,**kwargs):
   calls.append(args)
   return (a,)
  with patch.dict(rerank_multi_passage.__globals__,{"cross_encoder_rerank":model}):
   result=rerank_multi_passage("query",((a,),(a,)),top_k=1)
  self.assertEqual(len(result),1)
  self.assertEqual(len(calls[0][1]),1)
 def test_refuse_mixed_projects_before_model(self):
  with self.assertRaises(ValueError):
   rerank_multi_passage("query",((hit("a","a.py","x",1),),(hit("b","b.py","y",1),)))
 def test_limits(self):
  with self.assertRaises(ValueError):rerank_multi_passage("query",(),documents_limit=21)
  with self.assertRaises(ValueError):rerank_multi_passage("query",(),passages_per_document=4)
  with self.assertRaises(ValueError):rerank_multi_passage("query",(),rrf_k=0)
