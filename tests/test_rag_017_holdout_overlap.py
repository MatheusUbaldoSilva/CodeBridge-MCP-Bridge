import json,tempfile,unittest
from pathlib import Path
from benchmarks.audit_rag017_holdout_overlap import check
class HoldoutOverlapTests(unittest.TestCase):
 def test_rejects_known_question_case_and_whitespace(self):
  with tempfile.TemporaryDirectory() as tmp:
   a=Path(tmp)/"candidate.jsonl";b=Path(tmp)/"known.jsonl"
   a.write_text(json.dumps({"id":"c","query":"  WHERE   is CODE? "})+"\n")
   b.write_text(json.dumps({"id":"b","query":"where is code?"})+"\n")
   result=check(a,[b])
   self.assertFalse(result["exact_overlap_pass"])
   self.assertFalse(result["independence_certified"])
 def test_new_question_passes_exact_only(self):
  with tempfile.TemporaryDirectory() as tmp:
   a=Path(tmp)/"candidate.jsonl";b=Path(tmp)/"known.jsonl"
   a.write_text(json.dumps({"id":"c","query":"Find Qdrant source"})+"\n")
   b.write_text(json.dumps({"id":"b","query":"Find Git source"})+"\n")
   result=check(a,[b])
   self.assertTrue(result["exact_overlap_pass"])
   self.assertFalse(result["independence_certified"])
 def test_rejects_duplicate_questions(self):
  with tempfile.TemporaryDirectory() as tmp:
   a=Path(tmp)/"candidate.jsonl";b=Path(tmp)/"known.jsonl"
   a.write_text(json.dumps({"id":"c","query":"A source"})+"\n"+json.dumps({"id":"d","query":"a SOURCE"})+"\n")
   b.write_text(json.dumps({"id":"b","query":"Different source"})+"\n")
   self.assertFalse(check(a,[b])["exact_overlap_pass"])
