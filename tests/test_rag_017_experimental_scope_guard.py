import unittest
from rag.contracts import SearchQuery,SearchResult,SourceMetadata,SourceType
from rag.runtime.experimental_scope_guard import validate_scoped_results

class ExperimentalScopeGuardTests(unittest.TestCase):
 def item(self,project="p",branch="main",source=SourceType.CODE,path="src/a.py"):
  return SearchResult(chunk_id="c",document_id="d",content="x",metadata=SourceMetadata(project_id=project,git_branch=branch,source_type=source,path=path),score=1,rank=1)
 def query(self,**kwargs):
  return SearchQuery(query="locate code",project_id="p",branch="main",source_types=(SourceType.CODE,),path_filter="src/",**kwargs)
 def test_good_result(self):
  result=self.item()
  self.assertEqual(validate_scoped_results(self.query(),(result,)),(result,))
 def test_other_project(self):
  with self.assertRaisesRegex(ValueError,"cross-project"):
   validate_scoped_results(self.query(),(self.item(project="other"),))
 def test_other_branch(self):
  with self.assertRaisesRegex(ValueError,"cross-branch"):
   validate_scoped_results(self.query(),(self.item(branch="other"),))
 def test_other_source_type(self):
  with self.assertRaisesRegex(ValueError,"cross-source-type"):
   validate_scoped_results(self.query(),(self.item(source=SourceType.DOCUMENTATION),))
 def test_other_path(self):
  with self.assertRaisesRegex(ValueError,"out-of-path"):
   validate_scoped_results(self.query(),(self.item(path="else/a.py"),))
 def test_missing_path(self):
  with self.assertRaisesRegex(ValueError,"out-of-path"):
   validate_scoped_results(self.query(),(self.item(path=None),))
