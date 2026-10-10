import unittest
from rag.contracts import SearchResult,SourceMetadata,SourceType
from rag.ranking.semantic_document_reranker import rerank_documents

def hit(project,branch,chunk,path):
 return SearchResult(chunk_id=chunk,document_id="doc-shared",content="a",metadata=SourceMetadata(project_id=project,source_type=SourceType.CODE,path=path,git_branch=branch),score=1.0,rank=1,retrieval_modes=("code",))

class CrossRouteScopeTests(unittest.TestCase):
 def test_fusion_rejects_different_projects(self):
  with self.assertRaisesRegex(ValueError,"cross-project"):
   rerank_documents([[hit("one","main","c1","src/a.py")],[hit("two","main","c2","src/a.py")]])
 def test_branch_boundaries_preserved(self):
  output=rerank_documents([[hit("one","main","c1","src/a.py")],[hit("one","release","c2","src/a.py")]])
  self.assertEqual(len(output),2)
  self.assertEqual({x.metadata.git_branch for x in output},{"main","release"})
 def test_paths_are_not_merged(self):
  output=rerank_documents([[hit("one","main","c1","src/a.py")],[hit("one","main","c2","src/b.py")]])
  self.assertEqual(len(output),2)
 def test_duplicate_chunk_id_different_projects_must_reject(self):
  with self.assertRaisesRegex(ValueError,"cross-project"):
   rerank_documents([[hit("one","main","duplicate","src/a.py"),hit("two","main","duplicate","src/a.py")]])
