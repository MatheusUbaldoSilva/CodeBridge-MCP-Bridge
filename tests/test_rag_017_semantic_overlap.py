import json,tempfile,unittest
from pathlib import Path
from benchmarks.audit_rag017_semantic_overlap import screen

class SemanticOverlapTests(unittest.TestCase):
 def test_paraphrase_like_word_variation_flagged(self):
  with tempfile.TemporaryDirectory() as tmp:
   a=Path(tmp)/"candidate.jsonl";b=Path(tmp)/"known.jsonl"
   a.write_text(json.dumps({"id":"new","query":"How does Git provenance get assigned to source files?"})+"\n")
   b.write_text(json.dumps({"id":"old","query":"How does Git provenance get assigned to code files?"})+"\n")
   result=screen(a,[b])
   self.assertTrue(result["requires_manual_review"])
   self.assertFalse(result["independence_certified"])
 def test_unrelated_queries_do_not_certify_independence(self):
  with tempfile.TemporaryDirectory() as tmp:
   a=Path(tmp)/"candidate.jsonl";b=Path(tmp)/"known.jsonl"
   a.write_text(json.dumps({"id":"new","query":"Where is the code embedding server?"})+"\n")
   b.write_text(json.dumps({"id":"old","query":"How are peaches harvested?"})+"\n")
   result=screen(a,[b])
   self.assertFalse(result["requires_manual_review"])
   self.assertFalse(result["independence_certified"])
 def test_invalid_threshold(self):
  with tempfile.TemporaryDirectory() as tmp:
   a=Path(tmp)/"candidate.jsonl";b=Path(tmp)/"known.jsonl"
   a.write_text(json.dumps({"id":"new","query":"valid query"})+"\n")
   b.write_text(json.dumps({"id":"old","query":"valid query"})+"\n")
   with self.assertRaises(ValueError):screen(a,[b],0)
