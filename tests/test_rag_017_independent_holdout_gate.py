import hashlib,json,tempfile,unittest
from pathlib import Path
from benchmarks.rag017_independent_holdout_gate import evaluate_holdout

class IndependentHoldoutGateTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory()
  root=Path(self.tmp.name)
  self.q=root/"questions.jsonl";self.l=root/"labels.jsonl";self.p=root/"results.jsonl"
  self.q.write_text(json.dumps({"id":"new-001","query":"Where is feature X?"})+"\n",encoding="utf8")
  self.l.write_text(json.dumps({"id":"new-001","expected_paths":["src/x.py"],"review_status":"INDEPENDENTLY_REVIEWED","reviewer_id":"reviewer-1"})+"\n",encoding="utf8")
  self.p.write_text(json.dumps({"id":"new-001","paths":["src/x.py"]})+"\n",encoding="utf8")
  self.sha=hashlib.sha256(self.q.read_bytes()).hexdigest()
 def tearDown(self):self.tmp.cleanup()
 def call(self,sha=None):
  return evaluate_holdout(self.q,self.l,self.p,expected_sha256=sha or self.sha)
 def test_passing_metrics_never_promotes_production(self):
  result=self.call()
  self.assertTrue(result["quality_passed"])
  self.assertFalse(result["production_approved"])
 def test_frozen_digest_is_required(self):
  with self.assertRaisesRegex(ValueError,"digest mismatch"):
   self.call("0"*64)
 def test_rejects_unreviewed_labels(self):
  row=json.loads(self.l.read_text())
  row["review_status"]="SEEDED_FROM_SOURCE_LOCATIONS"
  self.l.write_text(json.dumps(row)+"\n")
  with self.assertRaisesRegex(ValueError,"unverified"):
   self.call()
 def test_rejects_missing_predictions(self):
  self.p.write_text("")
  with self.assertRaisesRegex(ValueError,"incomplete"):
   self.call()
 def test_rejects_duplicate_predictions(self):
  self.p.write_text(self.p.read_text()*2)
  with self.assertRaisesRegex(ValueError,"duplicate"):
   self.call()
